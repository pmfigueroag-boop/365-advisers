"""
src/data/external/adapters/macro.py
──────────────────────────────────────────────────────────────────────────────
Macro Nowcasting Adapter.

Provides yield curve, VIX, economic indicators, and regime classification.

Data sources:
  - FRED (Federal Reserve Economic Data) via API — free with key
  - yfinance for VIX and Treasury ETFs (always available)
  - Static defaults when no data is available

The adapter feeds:
  - RegimeWeightsEngine (regime classification)
  - Fundamental Engine (Risk & Macro agent context)
  - Alpha Signals (macro category)
  - Decision Engine (CIO Memo context)
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
from src.data.external.contracts.macro import (
    MacroContext,
    MacroIndicator,
    YieldCurve,
)

logger = logging.getLogger("365advisers.external.macro")


class MacroAdapter(ProviderAdapter):
    """
    Macro nowcasting adapter with FRED + yfinance fallback.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._fred_key = settings.FRED_API_KEY
        self._timeout = settings.EDPL_FRED_TIMEOUT
        self._client = httpx.AsyncClient(timeout=self._timeout)

    @property
    def name(self) -> str:
        return "macro"

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
        """Fetch macro nowcasting snapshot."""
        t0 = time.perf_counter()

        try:
            yield_curve = await self._fetch_yield_curve()
            vix = await self._fetch_vix()
            indicators = await self._fetch_indicators()

            # Derive regime classification
            regime = self._classify_regime(yield_curve, vix, indicators)

            data = MacroContext(
                as_of=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                yield_curve=yield_curve,
                vix=vix,
                vix_term_structure=self._vix_term_structure(vix),
                indicators=indicators,
                regime_classification=regime,
                source="fred_yfinance" if self._fred_key else "yfinance_proxy",
            )

            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)

        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"Macro fetch error: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        return HealthStatus(
            provider_name=self.name,
            domain=self.domain,
            status=ProviderStatus.ACTIVE,
            message="yfinance proxy always available",
        )

    # ── Internal ──────────────────────────────────────────────────────────

    async def _fetch_yield_curve(self) -> YieldCurve:
        """Fetch US Treasury yields."""

        us_2y: float | None = None
        us_10y: float | None = None
        us_30y: float | None = None

        # Try FRED first
        if self._fred_key:
            us_2y = await self._fred_series("DGS2")
            us_10y = await self._fred_series("DGS10")
            us_30y = await self._fred_series("DGS30")

        # Fallback: yfinance Treasury ETFs as proxy
        if us_10y is None:
            try:
                import yfinance as yf
                # Use ^TNX (10-year) and ^TYX (30-year) indexes
                tnx = yf.Ticker("^TNX").history(period="5d")
                if not tnx.empty:
                    us_10y = float(tnx["Close"].iloc[-1])

                tyx = yf.Ticker("^TYX").history(period="5d")
                if not tyx.empty:
                    us_30y = float(tyx["Close"].iloc[-1])

                # 2-year proxy from SHY (1-3 Year Treasury ETF)
                two_yr = yf.Ticker("^IRX").history(period="5d")  # 13-week T-Bill
                if not two_yr.empty:
                    us_2y = float(two_yr["Close"].iloc[-1])

            except Exception as exc:
                logger.debug(f"yfinance yield fetch failed: {exc}")

        spread = None
        if us_2y is not None and us_10y is not None:
            spread = round(us_10y - us_2y, 3)

        return YieldCurve(
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            us_2y=us_2y,
            us_10y=us_10y,
            us_30y=us_30y,
            spread_2s10s=spread,
            is_inverted=spread < 0 if spread is not None else False,
        )

    async def _fetch_vix(self) -> float | None:
        """Fetch current VIX level."""
        try:
            import yfinance as yf
            vix = yf.Ticker("^VIX").history(period="5d")
            if not vix.empty:
                return round(float(vix["Close"].iloc[-1]), 2)
        except Exception as exc:
            logger.debug(f"VIX fetch failed: {exc}")
        return None

    async def _fetch_indicators(self) -> list[MacroIndicator]:
        """Fetch key macro indicators."""
        indicators: list[MacroIndicator] = []

        if self._fred_key:
            # Fetch key FRED series
            series_map = {
                "Fed Funds Rate": "FEDFUNDS",
                "CPI YoY": "CPIAUCSL",
                "Unemployment Rate": "UNRATE",
                "ISM Manufacturing": "MANEMP",
            }

            for name, series_id in series_map.items():
                value = await self._fred_series(series_id)
                if value is not None:
                    indicators.append(MacroIndicator(
                        name=name,
                        value=value,
                        regime_signal="neutral",
                    ))

        return indicators

    async def _fred_series(self, series_id: str) -> float | None:
        """Fetch latest value from a FRED series."""
        try:
            resp = await self._client.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": self._fred_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 1,
                },
            )
            if resp.status_code == 200:
                observations = resp.json().get("observations", [])
                if observations:
                    val = observations[0].get("value", ".")
                    if val != ".":
                        return float(val)
        except Exception as exc:
            logger.debug(f"FRED fetch failed for {series_id}: {exc}")
        return None

    def _classify_regime(
        self,
        yield_curve: YieldCurve,
        vix: float | None,
        indicators: list[MacroIndicator],
    ) -> str:
        """
        Simple regime classification based on available data.

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

    def _vix_term_structure(self, vix: float | None) -> str:
        """Estimate VIX term structure (simplified)."""
        if vix is None:
            return "normal"
        if vix > 30:
            return "backwardation"
        elif vix < 15:
            return "contango"
        return "normal"
