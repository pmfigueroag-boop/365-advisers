"""
src/data/external/adapters/fred.py
──────────────────────────────────────────────────────────────────────────────
Dedicated FRED (Federal Reserve Economic Data) Adapter.

Provides comprehensive macro-economic series including yield curve, GDP,
CPI, unemployment, ISM, financial conditions, housing, and consumer
confidence indicators.

This adapter replaces the inline FRED logic previously embedded in macro.py
and registers as the PRIMARY adapter for DataDomain.MACRO.  The existing
MacroAdapter becomes the fallback (yfinance-only proxy).

Data sources:
  - FRED REST API (api.stlouisfed.org)
  - Free with registration; empty API key → adapter skipped

Retry policy:
  - 2 retries with exponential backoff (1s, 2s)
  - HTTP 429 → respects Retry-After header
  - Per-series try/except for partial-success resilience
"""

from __future__ import annotations

import asyncio
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
from src.data.external.contracts.macro import (
    MacroContext,
    MacroIndicator,
    YieldCurve,
)

logger = logging.getLogger("365advisers.external.fred")

# ─── Series Catalogue ─────────────────────────────────────────────────────────

# Yield curve series
YIELD_SERIES = {
    "DGS2": "us_2y",
    "DGS10": "us_10y",
    "DGS30": "us_30y",
}

# Core indicators
INDICATOR_SERIES = {
    "FEDFUNDS": "Fed Funds Rate",
    "CPIAUCSL": "CPI YoY",
    "PCEPI": "PCE Price Index",
    "UNRATE": "Unemployment Rate",
    "MANEMP": "ISM Manufacturing Employment",
    "NFCI": "Financial Conditions Index",
}

# Extended indicators (Phase 2 contract extensions)
EXTENDED_SERIES = {
    "A191RL1Q225SBEA": "GDP Growth Annualized",
    "PAYEMS": "Nonfarm Payrolls Change",
    "RSAFS": "Retail Sales MoM",
    "HOUST": "Housing Starts",
    "UMCSENT": "Consumer Confidence",
    "USSLIND": "Leading Indicators Index",
}


class FREDAdapter(ProviderAdapter):
    """
    Dedicated FRED adapter for comprehensive macro-economic data.

    Fetches yield curve, economic indicators, and financial conditions
    from the FRED REST API.  Supports per-series partial failures —
    the adapter returns whatever data it can obtain.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.FRED_API_KEY
        self._timeout = settings.EDPL_FRED_TIMEOUT
        self._max_retries = settings.EDPL_DEFAULT_MAX_RETRIES
        self._retry_delay = settings.EDPL_DEFAULT_RETRY_DELAY
        self._client = httpx.AsyncClient(timeout=self._timeout)

    @property
    def name(self) -> str:
        return "fred"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.MACRO

    def get_capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.YIELD_CURVE,
            ProviderCapability.ECONOMIC_INDICATORS,
            ProviderCapability.FINANCIAL_CONDITIONS,
        }

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """Fetch comprehensive macro snapshot from FRED API."""
        t0 = time.perf_counter()

        if not self._api_key:
            elapsed = (time.perf_counter() - t0) * 1000
            return self._error_response(
                "FRED_API_KEY not configured", latency_ms=elapsed,
            )

        try:
            # Fetch all components concurrently
            yield_curve, vix, indicators, extended = await asyncio.gather(
                self._fetch_yield_curve(),
                self._fetch_vix_proxy(),
                self._fetch_indicators(),
                self._fetch_extended_indicators(),
                return_exceptions=True,
            )

            # Handle partial failures from gather
            if isinstance(yield_curve, Exception):
                logger.warning(f"FRED yield curve fetch failed: {yield_curve}")
                yield_curve = YieldCurve()
            if isinstance(vix, Exception):
                logger.warning(f"VIX proxy fetch failed: {vix}")
                vix = None
            if isinstance(indicators, Exception):
                logger.warning(f"FRED indicators fetch failed: {indicators}")
                indicators = []
            if isinstance(extended, Exception):
                logger.warning(f"FRED extended indicators failed: {extended}")
                extended = {}

            # Merge extended into indicators list
            all_indicators: list[MacroIndicator] = list(indicators) if isinstance(indicators, list) else []
            if isinstance(extended, dict):
                for name, value in extended.items():
                    if value is not None:
                        all_indicators.append(MacroIndicator(
                            name=name, value=value, regime_signal="neutral",
                        ))

            # Derive regime classification
            regime = self._classify_regime(yield_curve, vix, all_indicators)

            # Extract specific fields for first-class contract attributes
            fed_funds = self._find_indicator(all_indicators, "Fed Funds Rate")
            cpi_yoy = self._find_indicator(all_indicators, "CPI YoY")
            pce_yoy = self._find_indicator(all_indicators, "PCE Price Index")
            unemployment = self._find_indicator(all_indicators, "Unemployment Rate")
            ism = self._find_indicator(all_indicators, "ISM Manufacturing Employment")
            nfci = self._find_indicator(all_indicators, "Financial Conditions Index")

            data = MacroContext(
                as_of=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                yield_curve=yield_curve,
                vix=vix,
                vix_term_structure=self._vix_term_structure(vix),
                fed_funds_rate=fed_funds,
                cpi_yoy=cpi_yoy,
                pce_yoy=pce_yoy,
                unemployment_rate=unemployment,
                ism_manufacturing=ism,
                financial_conditions_index=nfci,
                indicators=all_indicators,
                regime_classification=regime,
                source="fred",
            )

            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)

        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"FRED adapter error: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        """Verify FRED API is reachable with a lightweight probe."""
        if not self._api_key:
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=ProviderStatus.DISABLED,
                message="FRED_API_KEY not configured",
            )

        try:
            resp = await self._client.get(
                "https://api.stlouisfed.org/fred/series",
                params={
                    "series_id": "DGS10",
                    "api_key": self._api_key,
                    "file_type": "json",
                },
            )
            if resp.status_code == 200:
                return HealthStatus(
                    provider_name=self.name,
                    domain=self.domain,
                    status=ProviderStatus.ACTIVE,
                    last_success=datetime.now(timezone.utc),
                    message="FRED API reachable",
                )
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=ProviderStatus.DEGRADED,
                message=f"FRED API returned HTTP {resp.status_code}",
            )
        except Exception as exc:
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=ProviderStatus.DEGRADED,
                message=f"Health check failed: {exc}",
            )

    # ── Internal: Data Fetchers ──────────────────────────────────────────

    async def _fetch_yield_curve(self) -> YieldCurve:
        """Fetch US Treasury yield curve from FRED."""
        values: dict[str, float | None] = {}

        for series_id, field_name in YIELD_SERIES.items():
            values[field_name] = await self._fred_series(series_id)

        spread = None
        us_2y = values.get("us_2y")
        us_10y = values.get("us_10y")
        if us_2y is not None and us_10y is not None:
            spread = round(us_10y - us_2y, 3)

        return YieldCurve(
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            us_2y=us_2y,
            us_10y=us_10y,
            us_30y=values.get("us_30y"),
            spread_2s10s=spread,
            is_inverted=spread < 0 if spread is not None else False,
        )

    async def _fetch_vix_proxy(self) -> float | None:
        """Fetch VIX via yfinance (FRED doesn't provide real-time VIX)."""
        try:
            import yfinance as yf
            vix = yf.Ticker("^VIX").history(period="5d")
            if not vix.empty:
                return round(float(vix["Close"].iloc[-1]), 2)
        except Exception as exc:
            logger.debug(f"VIX proxy fetch failed: {exc}")
        return None

    async def _fetch_indicators(self) -> list[MacroIndicator]:
        """Fetch core FRED indicator series."""
        indicators: list[MacroIndicator] = []

        for series_id, name in INDICATOR_SERIES.items():
            value = await self._fred_series(series_id)
            if value is not None:
                indicators.append(MacroIndicator(
                    name=name, value=value, regime_signal="neutral",
                ))

        return indicators

    async def _fetch_extended_indicators(self) -> dict[str, float | None]:
        """Fetch extended FRED series for contract enrichment."""
        results: dict[str, float | None] = {}

        for series_id, name in EXTENDED_SERIES.items():
            results[name] = await self._fred_series(series_id)

        return results

    # ── Internal: FRED API ───────────────────────────────────────────────

    async def _fred_series(self, series_id: str) -> float | None:
        """
        Fetch latest observation from a FRED series with retry.

        Retries with exponential backoff on transient failures.
        Respects HTTP 429 Retry-After header.
        """
        for attempt in range(1 + self._max_retries):
            try:
                resp = await self._client.get(
                    "https://api.stlouisfed.org/fred/series/observations",
                    params={
                        "series_id": series_id,
                        "api_key": self._api_key,
                        "file_type": "json",
                        "sort_order": "desc",
                        "limit": 1,
                    },
                )

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", "2"))
                    logger.debug(f"FRED rate limit for {series_id}, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    continue

                if resp.status_code == 200:
                    observations = resp.json().get("observations", [])
                    if observations:
                        val = observations[0].get("value", ".")
                        if val != ".":
                            return float(val)
                    return None

                logger.debug(f"FRED {series_id} returned HTTP {resp.status_code}")

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                if attempt < self._max_retries:
                    delay = self._retry_delay * (2 ** attempt)
                    logger.debug(f"FRED {series_id} retry {attempt + 1} after {delay}s: {exc}")
                    await asyncio.sleep(delay)
                else:
                    logger.debug(f"FRED {series_id} exhausted retries: {exc}")

            except Exception as exc:
                logger.debug(f"FRED fetch failed for {series_id}: {exc}")
                break

        return None

    # ── Internal: Derived Logic ──────────────────────────────────────────

    @staticmethod
    def _find_indicator(
        indicators: list[MacroIndicator], name: str,
    ) -> float | None:
        """Find an indicator value by name."""
        for ind in indicators:
            if ind.name == name:
                return ind.value
        return None

    @staticmethod
    def _classify_regime(
        yield_curve: YieldCurve,
        vix: float | None,
        indicators: list[MacroIndicator],
    ) -> str:
        """
        Regime classification based on available data.

        Classification logic:
          - risk_off: VIX > 25 OR inverted yield curve
          - risk_on: VIX < 15 AND positive 2s10s spread
          - transition: everything else
        """
        if vix is not None and vix > 25:
            return "risk_off"
        if yield_curve.is_inverted:
            return "risk_off"
        if vix is not None and vix < 15:
            if yield_curve.spread_2s10s is not None and yield_curve.spread_2s10s > 0:
                return "risk_on"
        return "transition"

    @staticmethod
    def _vix_term_structure(vix: float | None) -> str:
        """Estimate VIX term structure (simplified)."""
        if vix is None:
            return "normal"
        if vix > 30:
            return "backwardation"
        elif vix < 15:
            return "contango"
        return "normal"
