"""
src/data/external/adapters/etf_flows.py
──────────────────────────────────────────────────────────────────────────────
ETF Flow Data Adapter.

Provides sector, factor, and thematic ETF flow data.  In production this
would connect to a paid ETF flow API.  This implementation provides:

  1. A real adapter that fetches ETF price changes as flow proxies (free)
  2. The contract structure ready for a premium feed upgrade

The proxy approach calculates flow momentum from ETF price changes over
5d/20d windows — a reasonable approximation of actual dollar flows.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import httpx

from src.config import get_settings
from src.data.external.base import (
    DataDomain,
    HealthStatus,
    ProviderAdapter,
    ProviderCapability,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
)
from src.data.external.contracts.etf_flows import (
    ETFFlowData,
    SectorFlowSummary,
)

logger = logging.getLogger("365advisers.external.etf_flows")

# Sector ETFs used as proxies
_SECTOR_ETFS: dict[str, list[str]] = {
    "Technology": ["XLK", "VGT", "QQQ"],
    "Healthcare": ["XLV", "VHT", "IBB"],
    "Financials": ["XLF", "VFH", "KBE"],
    "Energy": ["XLE", "VDE", "OIH"],
    "Consumer Discretionary": ["XLY", "VCR"],
    "Consumer Staples": ["XLP", "VDC"],
    "Industrials": ["XLI", "VIS"],
    "Materials": ["XLB", "VAW"],
    "Utilities": ["XLU", "VPU"],
    "Real Estate": ["XLRE", "VNQ"],
    "Communication Services": ["XLC"],
}

# Factor ETFs
_FACTOR_ETFS: dict[str, str] = {
    "value": "VLUE",
    "growth": "VUG",
    "momentum": "MTUM",
    "quality": "QUAL",
    "low_volatility": "USMV",
    "size": "IJR",
    "dividend": "VYM",
}

# Thematic ETFs
_THEMATIC_ETFS: dict[str, str] = {
    "ai_tech": "BOTZ",
    "clean_energy": "ICLN",
    "cybersecurity": "CIBR",
    "biotech": "XBI",
    "semiconductors": "SMH",
    "cloud": "SKYY",
}


class ETFFlowAdapter(ProviderAdapter):
    """
    ETF flow adapter using price-change proxy methodology.

    Calculates flow momentum from ETF return differentials across
    5-day and 20-day windows.  When a premium flow API becomes
    available, only the ``_fetch_*`` methods need replacement.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._timeout = settings.EDPL_DEFAULT_TIMEOUT
        self._polygon_key = settings.POLYGON_API_KEY
        self._client = httpx.AsyncClient(timeout=self._timeout)

    @property
    def name(self) -> str:
        return "etf_flows"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.ETF_FLOWS

    def get_capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.SECTOR_FLOWS,
            ProviderCapability.FACTOR_FLOWS,
            ProviderCapability.THEMATIC_FLOWS,
        }

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """Fetch ETF flow data using price-change proxy."""
        t0 = time.perf_counter()

        try:
            sector_flows = await self._compute_sector_flows()
            factor_flows = await self._compute_factor_flows()
            thematic_flows = await self._compute_thematic_flows()

            data = ETFFlowData(
                as_of=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                sector_flows=sector_flows,
                factor_flows=factor_flows,
                thematic_flows=thematic_flows,
                source="etf_price_proxy",
            )

            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)

        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"ETF flow fetch error: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        return HealthStatus(
            provider_name=self.name,
            domain=self.domain,
            status=ProviderStatus.ACTIVE,
            message="proxy mode — always available",
        )

    # ── Internal ──────────────────────────────────────────────────────────

    async def _get_etf_return(self, ticker: str, days: int) -> float:
        """
        Get ETF return over N days using Polygon or yfinance.

        Returns % change (e.g., 0.02 = +2%).
        """
        if self._polygon_key:
            try:
                from datetime import timedelta
                end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                start = (datetime.now(timezone.utc) - timedelta(days=days + 5)).strftime("%Y-%m-%d")
                resp = await self._client.get(
                    f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}",
                    params={"adjusted": "true", "sort": "asc", "apiKey": self._polygon_key},
                )
                if resp.status_code == 200:
                    results = resp.json().get("results", [])
                    if len(results) >= 2:
                        recent_close = results[-1]["c"]
                        past_close = results[-min(days, len(results))]["c"]
                        if past_close > 0:
                            return (recent_close - past_close) / past_close
            except Exception as exc:
                logger.debug(f"Polygon ETF return fetch failed for {ticker}: {exc}")

        # Fallback: use yfinance
        try:
            import yfinance as yf
            hist = yf.Ticker(ticker).history(period=f"{days + 5}d")
            if len(hist) >= 2:
                close_vals = hist["Close"].values
                return float((close_vals[-1] - close_vals[-min(days, len(close_vals))]) / close_vals[-min(days, len(close_vals))])
        except Exception:
            pass

        return 0.0

    async def _compute_sector_flows(self) -> list[SectorFlowSummary]:
        """Compute sector flow momentum from ETF returns."""
        summaries: list[SectorFlowSummary] = []

        for sector, etfs in _SECTOR_ETFS.items():
            primary = etfs[0]
            ret_5d = await self._get_etf_return(primary, 5)
            ret_20d = await self._get_etf_return(primary, 20)

            # Flow momentum: 5d return vs (20d/4) normalized
            momentum = ret_5d - (ret_20d / 4) if ret_20d != 0 else ret_5d

            summaries.append(SectorFlowSummary(
                sector=sector,
                net_flow_5d=ret_5d * 10000,      # scale to bps-like units
                net_flow_20d=ret_20d * 10000,
                flow_momentum=round(momentum * 10000, 2),
                top_inflow_etfs=[e for e in etfs if ret_5d > 0],
                top_outflow_etfs=[e for e in etfs if ret_5d < 0],
            ))

        return summaries

    async def _compute_factor_flows(self) -> dict[str, float]:
        """Compute factor flow momentum."""
        flows: dict[str, float] = {}
        for factor, etf in _FACTOR_ETFS.items():
            ret = await self._get_etf_return(etf, 5)
            flows[factor] = round(ret * 10000, 2)
        return flows

    async def _compute_thematic_flows(self) -> dict[str, float]:
        """Compute thematic flow momentum."""
        flows: dict[str, float] = {}
        for theme, etf in _THEMATIC_ETFS.items():
            ret = await self._get_etf_return(etf, 5)
            flows[theme] = round(ret * 10000, 2)
        return flows
