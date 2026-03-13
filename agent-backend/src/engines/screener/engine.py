"""
src/engines/screener/engine.py
──────────────────────────────────────────────────────────────────────────────
Composable Screener Engine — multi-criteria stock screening.

Pipeline:
  1. Resolve universe (reuse UniverseService from idea_generation)
  2. Fetch data for each ticker (fundamental + technical)
  3. Apply filter pipeline
  4. Sort & paginate
  5. Return with evidence trail
"""

from __future__ import annotations

import logging
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.engines.screener.contracts import (
    ScreenerFilter,
    ScreenerRequest,
    ScreenerMatch,
    ScreenerResult,
)
from src.engines.screener.providers import (
    FilterProvider,
    FilterRegistry,
    FundamentalFilterProvider,
    TechnicalFilterProvider,
    MetadataFilterProvider,
    SCREENER_PRESETS,
)

logger = logging.getLogger("365advisers.screener.engine")


# ── Universe resolution ──────────────────────────────────────────────────────

def _resolve_universe(request: ScreenerRequest) -> list[str]:
    """Get the ticker list to screen from the existing universe service."""
    try:
        from src.engines.idea_generation.universe_discovery import (
            default_universe_service,
            UniverseRequest,
            UniverseSource,
        )

        source_map = {
            "sp500":     UniverseSource.STATIC_INDEX,
            "nasdaq100": UniverseSource.STATIC_INDEX,
            "dow30":     UniverseSource.STATIC_INDEX,
            "custom":    UniverseSource.CUSTOM,
        }

        source = source_map.get(request.universe, UniverseSource.STATIC_INDEX)
        index_name = request.universe if request.universe in ("sp500", "nasdaq100", "dow30") else "sp500"

        if source == UniverseSource.CUSTOM and request.custom_tickers:
            return [t.upper().strip() for t in request.custom_tickers if t.strip()]

        result = default_universe_service.discover(
            UniverseRequest(
                sources=[source],
                index_name=index_name,
                max_tickers=500,
                custom_tickers=request.custom_tickers,
            )
        )
        return result.tickers

    except Exception as exc:
        logger.warning(f"Universe resolution failed, using SP500 fallback: {exc}")
        # Inline fallback — top 50 S&P500
        return [
            "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "LLY",
            "AVGO", "JPM", "TSLA", "UNH", "V", "XOM", "MA", "PG", "JNJ",
            "COST", "HD", "ABBV", "MRK", "WMT", "NFLX", "KO", "CVX", "BAC",
            "PEP", "CRM", "AMD", "TMO", "LIN", "CSCO", "ACN", "MCD", "ADBE",
            "WFC", "PM", "GE", "DHR", "TXN", "QCOM", "CAT", "AMGN", "AMAT",
            "VZ", "CMCSA", "NEE", "GS", "T", "LOW",
        ]


# ── Data fetching ────────────────────────────────────────────────────────────

def _fetch_ticker_data(ticker: str) -> dict | None:
    """Fetch combined fundamental + technical data for a single ticker."""
    try:
        from src.data.market_data import fetch_fundamental_data, fetch_technical_data

        fund = fetch_fundamental_data(ticker)
        tech = fetch_technical_data(ticker)

        return {
            "ticker": ticker,
            "name": fund.get("name", ticker),
            "sector": fund.get("sector", ""),
            "industry": fund.get("industry", ""),
            "info": fund.get("info", {}),
            "ratios": fund.get("ratios", {}),
            "indicators": tech.get("indicators", {}),
            "tv_summary": tech.get("tv_summary", {}),
            "exchange": tech.get("exchange", ""),
        }
    except Exception as exc:
        logger.warning(f"Data fetch failed for {ticker}: {exc}")
        return None


def _batch_fetch(tickers: list[str], max_workers: int = 8) -> dict[str, dict]:
    """Fetch data for multiple tickers concurrently."""
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {
            executor.submit(_fetch_ticker_data, t): t for t in tickers
        }
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                data = future.result()
                if data is not None:
                    results[ticker] = data
            except Exception as exc:
                logger.warning(f"Batch fetch error for {ticker}: {exc}")
    return results


# ── Screener Engine ──────────────────────────────────────────────────────────

class ScreenerEngine:
    """
    Composable multi-criteria stock screener.

    Usage::

        engine = ScreenerEngine.default()
        result = engine.screen(ScreenerRequest(
            filters=[
                ScreenerFilter(field="pe_ratio", operator="lte", value=20),
                ScreenerFilter(field="roic", operator="gte", value=0.15),
            ],
            universe="sp500",
            limit=20,
        ))
    """

    def __init__(self, registry: FilterRegistry) -> None:
        self._registry = registry

    @classmethod
    def default(cls) -> ScreenerEngine:
        """Create engine with all built-in providers registered."""
        registry = FilterRegistry()
        registry.register(FundamentalFilterProvider())
        registry.register(TechnicalFilterProvider())
        registry.register(MetadataFilterProvider())
        return cls(registry)

    @property
    def registry(self) -> FilterRegistry:
        return self._registry

    def available_fields(self) -> list[dict]:
        """Return all supported filter fields across all providers."""
        return self._registry.all_fields()

    def get_presets(self) -> dict:
        """Return available preset screens."""
        return SCREENER_PRESETS

    def screen(
        self,
        request: ScreenerRequest,
        *,
        max_workers: int = 8,
    ) -> ScreenerResult:
        """
        Run the full screener pipeline.

        Args:
            request: Screening criteria (filters, universe, sort, limit).
            max_workers: Max parallel data fetch threads.

        Returns:
            ScreenerResult with matching tickers and metadata.
        """
        start = _time.monotonic_ns()

        # ── 1. Resolve preset if specified ────────────────────────────────
        filters = list(request.filters)
        if request.preset and request.preset in SCREENER_PRESETS:
            preset_cfg = SCREENER_PRESETS[request.preset]
            for f in preset_cfg["filters"]:
                filters.append(ScreenerFilter(**f))

        # ── 2. Resolve universe ───────────────────────────────────────────
        tickers = _resolve_universe(request)
        logger.info(f"Screener: scanning {len(tickers)} tickers with {len(filters)} filters")

        # ── 3. Fetch data ─────────────────────────────────────────────────
        ticker_data = _batch_fetch(tickers, max_workers=max_workers)

        # ── 4. Apply filters ──────────────────────────────────────────────
        matches: list[ScreenerMatch] = []

        for ticker, data in ticker_data.items():
            field_values: dict[str, float | str | None] = {}
            passed = 0

            for f in filters:
                actual = self._registry.extract_field(data, f.field)
                field_values[f.field] = actual
                if f.evaluate(actual):
                    passed += 1

            # Only include if ALL filters pass
            if passed == len(filters):
                info = data.get("info", {})
                ratios = data.get("ratios", {})
                market_cap = info.get("marketCap") or ratios.get("valuation", {}).get("market_cap")

                matches.append(ScreenerMatch(
                    ticker=ticker,
                    name=data.get("name", ticker),
                    sector=data.get("sector", ""),
                    industry=data.get("industry", ""),
                    price=info.get("currentPrice") or info.get("regularMarketPrice"),
                    market_cap=float(market_cap) if market_cap else None,
                    field_values=field_values,
                    filters_passed=passed,
                    filters_total=len(filters),
                ))

        # ── 5. Sort ───────────────────────────────────────────────────────
        sort_field = request.sort_by
        if sort_field == "score":
            # Default sort: by market cap descending
            matches.sort(key=lambda m: m.market_cap or 0, reverse=request.sort_desc)
        elif sort_field in ("market_cap", "price"):
            matches.sort(
                key=lambda m: getattr(m, sort_field) or 0,
                reverse=request.sort_desc,
            )
        else:
            # Sort by a filter field value
            matches.sort(
                key=lambda m: float(m.field_values.get(sort_field, 0) or 0),
                reverse=request.sort_desc,
            )

        # ── 6. Cap ────────────────────────────────────────────────────────
        capped = matches[:request.limit]
        elapsed_ms = (_time.monotonic_ns() - start) / 1e6

        logger.info(
            f"Screener complete: {len(capped)}/{len(ticker_data)} passed "
            f"({len(filters)} filters) in {elapsed_ms:.0f}ms"
        )

        return ScreenerResult(
            matches=capped,
            total_scanned=len(ticker_data),
            total_passed=len(matches),
            filters_applied=len(filters),
            universe=request.universe,
            preset=request.preset,
            processing_ms=round(elapsed_ms, 1),
        )
