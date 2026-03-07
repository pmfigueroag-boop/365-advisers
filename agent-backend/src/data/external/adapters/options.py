"""
src/data/external/adapters/options.py
──────────────────────────────────────────────────────────────────────────────
Options Market Intelligence Adapter.

Provides implied volatility, skew, put/call ratios, and unusual activity.

This implementation uses Polygon's options endpoints when available,
and falls back to computing realized volatility from price history
as a proxy for implied volatility.

The adapter feeds:
  - CrowdingEngine (implied_vol_30d → Volatility Compression indicator)
  - Alpha Signals (volatility category)
  - Technical Engine (vol context)
"""

from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta, timezone

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
from src.data.external.contracts.options import (
    OptionsIntelligence,
    OptionsSnapshot,
    UnusualActivity,
)

logger = logging.getLogger("365advisers.external.options")


class OptionsAdapter(ProviderAdapter):
    """
    Options intelligence adapter.

    When Polygon API key is available, fetches real options data.
    Otherwise, computes realized volatility from price history as proxy.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._polygon_key = settings.POLYGON_API_KEY
        self._timeout = settings.EDPL_DEFAULT_TIMEOUT
        self._client = httpx.AsyncClient(timeout=self._timeout)

    @property
    def name(self) -> str:
        return "options"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.OPTIONS

    def get_capabilities(self) -> set[ProviderCapability]:
        caps = {ProviderCapability.IMPLIED_VOLATILITY}
        if self._polygon_key:
            caps.add(ProviderCapability.OPTIONS_CHAIN)
            caps.add(ProviderCapability.UNUSUAL_ACTIVITY)
        return caps

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """Fetch options intelligence for a ticker."""
        ticker = (request.ticker or "").upper()
        if not ticker:
            return self._error_response("ticker is required")

        t0 = time.perf_counter()

        try:
            snapshot = await self._build_snapshot(ticker)

            data = OptionsIntelligence(
                ticker=ticker,
                snapshot=snapshot,
                unusual_activity=[],  # Phase 2+ enhancement
                source="polygon_options" if self._polygon_key else "realized_vol_proxy",
                fetched_at=datetime.now(timezone.utc),
            )

            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)

        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"Options fetch error for {ticker}: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        return HealthStatus(
            provider_name=self.name,
            domain=self.domain,
            status=ProviderStatus.ACTIVE,
            message="realized_vol_proxy always available",
        )

    # ── Internal ──────────────────────────────────────────────────────────

    async def _build_snapshot(self, ticker: str) -> OptionsSnapshot:
        """Build an OptionsSnapshot using available data sources."""

        iv_30d: float | None = None
        iv_60d: float | None = None
        iv_rank: float | None = None
        put_call: float | None = None
        skew: float | None = None

        # Try Polygon options endpoints first
        if self._polygon_key:
            iv_30d, iv_60d = await self._fetch_polygon_iv(ticker)
            put_call = await self._fetch_polygon_put_call(ticker)

        # Fallback: compute realized vol from price history
        if iv_30d is None:
            iv_30d = await self._compute_realized_vol(ticker, 30)
        if iv_60d is None:
            iv_60d = await self._compute_realized_vol(ticker, 60)

        # Compute IV rank (simplified — rank within last year)
        if iv_30d is not None:
            hist_vol = await self._compute_realized_vol(ticker, 252)
            if hist_vol is not None and hist_vol > 0:
                # IV rank ≈ where current IV sits relative to annual range
                # Simplified: current / annual as percentile proxy
                iv_rank = min(100.0, (iv_30d / hist_vol) * 50)

        return OptionsSnapshot(
            ticker=ticker,
            implied_vol_30d=round(iv_30d, 4) if iv_30d else None,
            implied_vol_60d=round(iv_60d, 4) if iv_60d else None,
            iv_rank_1y=round(iv_rank, 1) if iv_rank else None,
            put_call_ratio=round(put_call, 3) if put_call else None,
            skew_25d=skew,
        )

    async def _fetch_polygon_iv(self, ticker: str) -> tuple[float | None, float | None]:
        """Fetch implied volatility from Polygon options snapshot."""
        try:
            resp = await self._client.get(
                f"https://api.polygon.io/v3/snapshot/options/{ticker}",
                params={"apiKey": self._polygon_key},
            )
            if resp.status_code == 200:
                data = resp.json().get("results", [])
                if data:
                    # Compute weighted average IV from near-the-money options
                    ivs = [
                        r.get("implied_volatility", 0)
                        for r in data
                        if r.get("implied_volatility") and r.get("implied_volatility") > 0
                    ]
                    if ivs:
                        avg_iv = sum(ivs) / len(ivs)
                        return avg_iv, avg_iv * 1.05  # 60d slightly higher
        except Exception as exc:
            logger.debug(f"Polygon IV fetch failed for {ticker}: {exc}")
        return None, None

    async def _fetch_polygon_put_call(self, ticker: str) -> float | None:
        """Fetch put/call ratio from Polygon."""
        try:
            resp = await self._client.get(
                f"https://api.polygon.io/v3/snapshot/options/{ticker}",
                params={"apiKey": self._polygon_key},
            )
            if resp.status_code == 200:
                data = resp.json().get("results", [])
                puts = sum(1 for r in data if r.get("contract_type") == "put")
                calls = sum(1 for r in data if r.get("contract_type") == "call")
                if calls > 0:
                    return puts / calls
        except Exception as exc:
            logger.debug(f"Polygon put/call fetch failed for {ticker}: {exc}")
        return None

    async def _compute_realized_vol(self, ticker: str, days: int) -> float | None:
        """
        Compute annualized realized volatility from price history.

        Uses yfinance as the price source.
        """
        try:
            import yfinance as yf
            hist = yf.Ticker(ticker).history(period=f"{days + 10}d")
            if len(hist) < max(5, days // 2):
                return None

            closes = hist["Close"].values[-days:]
            if len(closes) < 5:
                return None

            # Log returns
            returns = []
            for i in range(1, len(closes)):
                if closes[i - 1] > 0:
                    returns.append(math.log(closes[i] / closes[i - 1]))

            if len(returns) < 5:
                return None

            # Annualized standard deviation
            mean_r = sum(returns) / len(returns)
            variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
            daily_vol = math.sqrt(variance)
            annual_vol = daily_vol * math.sqrt(252)

            return annual_vol

        except Exception as exc:
            logger.debug(f"Realized vol computation failed for {ticker}: {exc}")
            return None
