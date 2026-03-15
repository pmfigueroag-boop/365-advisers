"""
src/engines/idea_generation/universe_discovery.py
──────────────────────────────────────────────────────────────────────────────
Universe Discovery system for the IDEA module.

Autonomous ticker universe construction — the engine discovers *what*
to scan instead of requiring manual ticker input.

Pluggable provider architecture:
  - StaticIndexProvider   — S&P500, NASDAQ100, Dow30 constituents
  - PortfolioProvider     — tickers from saved portfolios
  - IdeaHistoryProvider   — re-scan tickers from recent high-quality ideas
  - ScreenerProvider      — programmatic screener (market cap / volume)
  - SectorRotationProvider — macro-aligned sector selection
  - CustomProvider        — explicit watchlist pass-through

Usage::

    from src.engines.idea_generation.universe_discovery import (
        default_universe_service,
        UniverseRequest,
        UniverseSource,
    )

    result = default_universe_service.discover(
        UniverseRequest(sources=[UniverseSource.STATIC_INDEX])
    )
    tickers = result.tickers
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Protocol, runtime_checkable

logger = logging.getLogger("365advisers.idea_generation.universe_discovery")


# ── Enumerations ────────────────────────────────────────────────────────────


class UniverseSource(str, Enum):
    """Available universe discovery sources."""
    STATIC_INDEX = "static_index"
    PORTFOLIO = "portfolio"
    IDEA_HISTORY = "idea_history"
    SCREENER = "screener"
    SECTOR_ROTATION = "sector_rotation"
    CUSTOM = "custom"


# ── Data Models ─────────────────────────────────────────────────────────────


@dataclass
class TickerEntry:
    """A single ticker discovered by a universe provider."""
    ticker: str
    source: UniverseSource
    score: float = 1.0
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "source": self.source.value,
            "score": self.score,
            "reason": self.reason,
        }


@dataclass
class UniverseRequest:
    """Configuration for a universe discovery run."""
    sources: list[UniverseSource] = field(
        default_factory=lambda: [UniverseSource.STATIC_INDEX]
    )
    max_tickers: int = 200
    max_per_source: int = 300
    strategy_profile: str | None = None
    custom_tickers: list[str] = field(default_factory=list)

    # Filters for screener
    min_market_cap: float = 1_000_000_000  # $1B
    min_volume: int = 500_000

    # Filters for idea history
    history_days: int = 7
    min_signal_strength: float = 0.5

    # Index selection for static
    index_name: str = "sp500"


@dataclass
class UniverseResult:
    """Output of a universe discovery run."""
    tickers: list[str] = field(default_factory=list)
    total_discovered: int = 0
    total_after_dedup: int = 0
    total_after_cap: int = 0
    source_breakdown: dict[str, int] = field(default_factory=dict)
    entries: list[TickerEntry] = field(default_factory=list)
    discovery_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "tickers": self.tickers,
            "total_discovered": self.total_discovered,
            "total_after_dedup": self.total_after_dedup,
            "total_after_cap": self.total_after_cap,
            "source_breakdown": self.source_breakdown,
            "entries": [e.to_dict() for e in self.entries],
            "discovery_ms": self.discovery_ms,
        }


# ── Provider Protocol ───────────────────────────────────────────────────────


@runtime_checkable
class UniverseProvider(Protocol):
    """Interface for pluggable universe providers."""
    name: str
    source: UniverseSource
    description: str

    def discover(self, request: UniverseRequest) -> list[TickerEntry]:
        """Discover tickers from this source."""
        ...


# ── Static Index Provider ────────────────────────────────────────────────────

# Representative US equity indices (top constituents by market cap)
_SP500_TOP = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "LLY",
    "AVGO", "JPM", "TSLA", "UNH", "V", "XOM", "MA", "PG", "JNJ",
    "COST", "HD", "ABBV", "MRK", "WMT", "NFLX", "KO", "CVX", "BAC",
    "PEP", "CRM", "AMD", "TMO", "LIN", "CSCO", "ACN", "MCD", "ADBE",
    "ABT", "WFC", "IBM", "PM", "GE", "DHR", "TXN", "QCOM", "INTU",
    "ISRG", "AMGN", "CAT", "AMAT", "VZ", "CMCSA", "NEE", "RTX", "NOW",
    "GS", "PFE", "T", "LOW", "SPGI", "BLK", "SYK", "BKNG", "HON",
    "UNP", "AXP", "COP", "ELV", "DE", "BA", "MDLZ", "ADI", "TJX",
    "GILD", "SBUX", "LRCX", "MMC", "VRTX", "CI", "PLD", "BDX", "PANW",
    "MO", "CB", "SCHW", "BMY", "KLAC", "TMUS", "SO", "DUK", "ZTS",
    "SNPS", "CDNS", "FI", "CME", "SHW", "MSI", "PYPL", "ICE", "ORLY",
    "MCO", "USB", "PNC", "REGN", "GD", "MMM", "NOC", "CL", "EOG",
    "TGT", "ABNB", "AON", "WM", "ITW", "APD", "CSX", "MAR", "NXPI",
    "EMR", "CARR", "OXY", "SLB", "WELL", "GM", "HUM", "FTNT", "ROP",
    "MCHP", "PSX", "AJG", "F", "AEP", "TFC", "MPC", "AIG", "D",
    "SPG", "AFL", "ROST", "KMB", "PCAR", "VLO", "NSC", "DXCM", "MET",
    "MNST", "AMP", "FIS", "HCA", "KMI", "O", "SRE", "CCI", "FCX",
    "PRU", "CTAS", "PCG", "TRV", "GWW", "DVN", "DLR", "ALL", "KHC",
    "EW", "BK", "OKE", "PSA", "PAYX", "FAST", "CTSH", "PEG", "MSCI",
    "A", "AZO", "VRSK", "CMI", "ODFL", "YUM", "CPRT", "IDXX", "DAL",
]

_NASDAQ100_TOP = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "AVGO", "GOOGL", "TSLA",
    "COST", "NFLX", "AMD", "ADBE", "PEP", "CSCO", "QCOM", "INTU",
    "TMUS", "ISRG", "AMGN", "AMAT", "TXN", "BKNG", "CMCSA", "HON",
    "LRCX", "VRTX", "PANW", "KLAC", "SNPS", "CDNS", "GILD", "ADI",
    "MELI", "SBUX", "PYPL", "MDLZ", "REGN", "FTNT", "CRWD", "ABNB",
    "MCHP", "CSX", "NXPI", "MNST", "MAR", "ORLY", "CTAS", "ADP",
    "DXCM", "PCAR", "ROP", "WDAY", "FAST", "CPRT", "IDXX", "ODFL",
    "KDP", "AEP", "PAYX", "MRVL", "EA", "KHC", "CTSH", "LULU",
    "VRSK", "GEHC", "EXC", "TEAM", "FANG", "ON", "DDOG", "BIIB",
    "BKR", "ANSS", "CDW", "CEG", "ZS", "TTD", "GFS", "MRNA",
    "DASH", "ILMN", "WBD", "CSGP", "SIRI", "LCID", "RIVN", "ALGN",
    "ENPH", "JD", "PDD", "DLTR", "PTON", "ZM", "DOCU", "WBA",
]

_DOW30 = [
    "AAPL", "AMGN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS",
    "DOW", "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO",
    "MCD", "MMM", "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "V",
    "VZ", "WBA", "WMT",
]

_INDEX_CATALOG = {
    "sp500": _SP500_TOP,
    "nasdaq100": _NASDAQ100_TOP,
    "dow30": _DOW30,
}

# Convenience aliases for combined indices
_INDEX_ALIASES = {
    "all": ["sp500", "nasdaq100", "dow30"],
    "us_full": ["sp500", "nasdaq100", "dow30"],
}


def _resolve_index_names(index_name: str) -> list[str]:
    """Resolve an index_name into a list of concrete index keys.

    Supports:
      - Single index:  "sp500"
      - Combined:      "sp500+nasdaq100+dow30"
      - Aliases:       "all", "us_full"
    """
    key = index_name.lower().strip()
    if key in _INDEX_ALIASES:
        return _INDEX_ALIASES[key]
    if "+" in key:
        return [k.strip() for k in key.split("+") if k.strip()]
    return [key]


class StaticIndexProvider:
    """Provides tickers from well-known equity indices.

    Supports combined indices via ``+`` separator or the ``all`` alias::

        index_name="sp500"                    # single index
        index_name="sp500+nasdaq100+dow30"    # combined
        index_name="all"                      # alias for all three
    """
    name = "static_index"
    source = UniverseSource.STATIC_INDEX
    description = "S&P 500, NASDAQ 100, and Dow 30 constituents (combinable via '+')"

    def discover(self, request: UniverseRequest) -> list[TickerEntry]:
        index_keys = _resolve_index_names(request.index_name)
        cap = request.max_per_source

        # Merge tickers from all requested indices, dedup preserving order
        seen: set[str] = set()
        merged: list[str] = []
        sources_used: list[str] = []

        for key in index_keys:
            tickers = _INDEX_CATALOG.get(key, [])
            if not tickers:
                continue
            sources_used.append(key)
            for t in tickers:
                if t not in seen:
                    seen.add(t)
                    merged.append(t)

        label = "+".join(sources_used) if len(sources_used) > 1 else (sources_used[0] if sources_used else "unknown")

        return [
            TickerEntry(
                ticker=t,
                source=self.source,
                score=1.0,
                reason=f"{label} constituent",
            )
            for t in merged[:cap]
        ]


# ── Portfolio Provider ───────────────────────────────────────────────────────


class PortfolioProvider:
    """Extracts tickers from saved user portfolios."""
    name = "portfolio"
    source = UniverseSource.PORTFOLIO
    description = "Tickers from saved portfolio positions"

    def discover(self, request: UniverseRequest) -> list[TickerEntry]:
        try:
            from src.data.database import SessionLocal, PortfolioPosition
            with SessionLocal() as db:
                positions = (
                    db.query(PortfolioPosition.ticker)
                    .distinct()
                    .limit(request.max_per_source)
                    .all()
                )
                return [
                    TickerEntry(
                        ticker=row.ticker,
                        source=self.source,
                        score=1.0,
                        reason="portfolio position",
                    )
                    for row in positions
                    if row.ticker
                ]
        except Exception as exc:
            logger.warning(f"PortfolioProvider failed: {exc}")
            return []


# ── Idea History Provider ────────────────────────────────────────────────────


class IdeaHistoryProvider:
    """Re-scan tickers from recent high-quality ideas."""
    name = "idea_history"
    source = UniverseSource.IDEA_HISTORY
    description = "Re-scan tickers that generated strong ideas recently"

    def discover(self, request: UniverseRequest) -> list[TickerEntry]:
        try:
            from src.data.database import SessionLocal, IdeaRecord
            cutoff = datetime.now(timezone.utc) - timedelta(days=request.history_days)
            with SessionLocal() as db:
                ideas = (
                    db.query(IdeaRecord.ticker, IdeaRecord.signal_strength)
                    .filter(
                        IdeaRecord.generated_at >= cutoff,
                        IdeaRecord.signal_strength >= request.min_signal_strength,
                    )
                    .order_by(IdeaRecord.signal_strength.desc())
                    .distinct()
                    .limit(request.max_per_source)
                    .all()
                )
                return [
                    TickerEntry(
                        ticker=row.ticker,
                        source=self.source,
                        score=row.signal_strength,
                        reason=f"recent idea (signal={row.signal_strength:.2f})",
                    )
                    for row in ideas
                    if row.ticker
                ]
        except Exception as exc:
            logger.warning(f"IdeaHistoryProvider failed: {exc}")
            return []


# ── Screener Provider ────────────────────────────────────────────────────────


class ScreenerProvider:
    """Programmatic screener — filters by market cap and volume.

    Uses a static universe of large-cap US equities as a proxy.
    In production, this would call FMP / Polygon stock screener API.
    """
    name = "screener"
    source = UniverseSource.SCREENER
    description = "Programmatic screener: large-cap, high-volume US equities"

    # Static proxy universe — represents stocks that typically pass
    # the $1B market cap + 500K volume filter
    _SCREENER_UNIVERSE = [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B",
        "LLY", "AVGO", "JPM", "UNH", "V", "XOM", "MA", "PG", "JNJ",
        "COST", "HD", "ABBV", "MRK", "WMT", "NFLX", "CVX", "BAC",
        "PEP", "AMD", "CRM", "TMO", "LIN", "CSCO", "ACN", "MCD", "ADBE",
        "WFC", "PM", "GE", "DHR", "TXN", "QCOM", "CAT", "AMGN",
        "AMAT", "VZ", "CMCSA", "NEE", "GS", "T", "LOW", "SPGI",
        "PLTR", "UBER", "COIN", "SQ", "SNOW", "SHOP", "NET", "CRWD",
        "DDOG", "MRVL", "ARM", "MU", "DELL", "HPE", "SMCI",
        "GM", "F", "RIVN", "NIO", "LI", "XPEV",
        "DIS", "PARA", "WBD", "FOX", "NWSA",
        "CCL", "RCL", "NCLH", "MAR", "HLT", "ABNB",
        "DAL", "UAL", "LUV", "AAL",
    ]

    def discover(self, request: UniverseRequest) -> list[TickerEntry]:
        cap = request.max_per_source
        return [
            TickerEntry(
                ticker=t,
                source=self.source,
                score=0.8,
                reason=f"screener: cap>={request.min_market_cap/1e9:.0f}B, vol>={request.min_volume//1000}K",
            )
            for t in self._SCREENER_UNIVERSE[:cap]
        ]


# ── Sector Rotation Provider ────────────────────────────────────────────────

_SECTOR_TICKERS = {
    "technology": ["AAPL", "MSFT", "NVDA", "AVGO", "CRM", "ADBE", "AMD", "QCOM", "TXN", "INTU"],
    "healthcare": ["UNH", "LLY", "JNJ", "ABBV", "MRK", "PFE", "TMO", "ABT", "DHR", "AMGN"],
    "financials": ["JPM", "BAC", "WFC", "GS", "MS", "BLK", "SCHW", "AXP", "CB", "MMC"],
    "energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "DVN"],
    "consumer_discretionary": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "TJX", "LOW", "BKNG", "CMG"],
    "consumer_staples": ["PG", "KO", "PEP", "COST", "WMT", "PM", "MO", "CL", "KMB", "MDLZ"],
    "industrials": ["CAT", "GE", "HON", "UNP", "BA", "RTX", "DE", "LMT", "NOC", "GD"],
    "materials": ["LIN", "APD", "SHW", "ECL", "FCX", "NEM", "NUE", "DOW", "DD", "PPG"],
    "utilities": ["NEE", "SO", "DUK", "D", "AEP", "SRE", "XEL", "PCG", "WEC", "ES"],
    "real_estate": ["PLD", "AMT", "CCI", "EQIX", "SPG", "PSA", "DLR", "O", "WELL", "AVB"],
    "communication": ["META", "GOOGL", "DIS", "CMCSA", "NFLX", "VZ", "T", "TMUS", "CHTR", "EA"],
}


class SectorRotationProvider:
    """Provides tickers from sectors favored by current macro regime.

    In production, integrates with the Macro engine to determine
    which sectors are in favor.  For now, uses a configurable
    favored_sectors list or defaults to all.
    """
    name = "sector_rotation"
    source = UniverseSource.SECTOR_ROTATION
    description = "Tickers from macro-favored sectors"

    def __init__(self, favored_sectors: list[str] | None = None):
        self._favored = favored_sectors

    def discover(self, request: UniverseRequest) -> list[TickerEntry]:
        sectors = self._favored or list(_SECTOR_TICKERS.keys())
        entries: list[TickerEntry] = []
        per_sector = max(1, request.max_per_source // len(sectors))

        for sector in sectors:
            tickers = _SECTOR_TICKERS.get(sector, [])
            for t in tickers[:per_sector]:
                entries.append(TickerEntry(
                    ticker=t,
                    source=self.source,
                    score=0.9,
                    reason=f"sector rotation: {sector}",
                ))
            if len(entries) >= request.max_per_source:
                break

        return entries[:request.max_per_source]


# ── Custom Provider ──────────────────────────────────────────────────────────


class CustomProvider:
    """Pass-through for user-supplied ticker lists (watchlist)."""
    name = "custom"
    source = UniverseSource.CUSTOM
    description = "User-supplied ticker list (watchlist)"

    def discover(self, request: UniverseRequest) -> list[TickerEntry]:
        return [
            TickerEntry(
                ticker=t.upper().strip(),
                source=self.source,
                score=1.0,
                reason="user watchlist",
            )
            for t in request.custom_tickers[:request.max_per_source]
            if t.strip()
        ]


# ── Provider Registry ───────────────────────────────────────────────────────


class UniverseProviderRegistry:
    """Central catalog of universe providers."""

    def __init__(self) -> None:
        self._providers: dict[str, UniverseProvider] = {}

    def register(self, provider: UniverseProvider) -> None:
        if provider.name in self._providers:
            raise ValueError(f"Universe provider '{provider.name}' already registered")
        self._providers[provider.name] = provider
        logger.debug(
            "universe_provider_registered",
            extra={"name": provider.name, "source": provider.source.value},
        )

    def get_by_source(self, source: UniverseSource) -> UniverseProvider | None:
        for p in self._providers.values():
            if p.source == source:
                return p
        return None

    def list_all(self) -> list[UniverseProvider]:
        return list(self._providers.values())

    def list_sources(self) -> list[dict]:
        return [
            {
                "name": p.name,
                "source": p.source.value,
                "description": p.description,
            }
            for p in self._providers.values()
        ]

    def __len__(self) -> int:
        return len(self._providers)

    def __contains__(self, name: str) -> bool:
        return name in self._providers


# ── Universe Service ─────────────────────────────────────────────────────────


class UniverseService:
    """Orchestrates universe providers, deduplicates, and caps results.

    Flow:
        1. For each requested source, find the provider
        2. Call provider.discover(request)
        3. Merge all TickerEntries
        4. Deduplicate (keep highest-scored entry per ticker)
        5. Sort by score descending
        6. Cap to max_tickers
    """

    def __init__(self, registry: UniverseProviderRegistry) -> None:
        self._registry = registry

    def discover(self, request: UniverseRequest) -> UniverseResult:
        import time as _time
        start = _time.monotonic_ns()

        all_entries: list[TickerEntry] = []
        source_breakdown: dict[str, int] = {}

        for source in request.sources:
            provider = self._registry.get_by_source(source)
            if provider is None:
                logger.warning(f"No provider registered for source: {source.value}")
                continue

            try:
                entries = provider.discover(request)
                all_entries.extend(entries)
                source_breakdown[source.value] = len(entries)
                logger.debug(
                    "universe_source_discovered",
                    extra={
                        "source": source.value,
                        "tickers_found": len(entries),
                    },
                )
            except Exception as exc:
                logger.warning(f"Provider {provider.name} failed: {exc}")
                source_breakdown[source.value] = 0

        total_discovered = len(all_entries)

        # Deduplicate — keep highest score per ticker
        best: dict[str, TickerEntry] = {}
        for entry in all_entries:
            key = entry.ticker.upper()
            if key not in best or entry.score > best[key].score:
                best[key] = entry

        deduped = sorted(best.values(), key=lambda e: e.score, reverse=True)
        total_after_dedup = len(deduped)

        # Cap
        capped = deduped[:request.max_tickers]
        total_after_cap = len(capped)

        elapsed_ms = (_time.monotonic_ns() - start) / 1e6

        tickers = [e.ticker for e in capped]

        logger.info(
            "universe_discovery_complete",
            extra={
                "total_discovered": total_discovered,
                "after_dedup": total_after_dedup,
                "after_cap": total_after_cap,
                "sources": list(source_breakdown.keys()),
                "duration_ms": round(elapsed_ms, 1),
            },
        )

        return UniverseResult(
            tickers=tickers,
            total_discovered=total_discovered,
            total_after_dedup=total_after_dedup,
            total_after_cap=total_after_cap,
            source_breakdown=source_breakdown,
            entries=capped,
            discovery_ms=round(elapsed_ms, 1),
        )


# ── Default singleton ────────────────────────────────────────────────────────


def _build_default_service() -> UniverseService:
    """Create the default service with all providers registered."""
    registry = UniverseProviderRegistry()
    registry.register(StaticIndexProvider())
    registry.register(PortfolioProvider())
    registry.register(IdeaHistoryProvider())
    registry.register(ScreenerProvider())
    registry.register(SectorRotationProvider())
    registry.register(CustomProvider())
    return UniverseService(registry)


default_universe_service = _build_default_service()
