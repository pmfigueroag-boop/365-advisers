"""
src/data/external/adapters/polygon.py
──────────────────────────────────────────────────────────────────────────────
Polygon.io Adapter — institutional-grade market data provider.

Provides:
  - Daily and intraday OHLCV bars with VWAP and trade count
  - Liquidity metrics (bid-ask spread, dollar volume, turnover)
  - Previous-day close / last trade price

Rate limiting:  Polygon free tier = 5 req/min.
                Polygon paid tier = unlimited.
                This adapter respects a configurable delay between requests.

Fallback: When Polygon is unavailable the FallbackRouter will cascade to
          the existing yfinance providers — the system continues to work
          with daily bars only.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

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
from src.data.external.contracts.enhanced_market import (
    EnhancedMarketData,
    IntradayBar,
    LiquiditySnapshot,
)

logger = logging.getLogger("365advisers.external.polygon")

_POLYGON_BASE = "https://api.polygon.io"


class PolygonAdapter(ProviderAdapter):
    """
    Adapter for the Polygon.io REST API.

    Transforms Polygon responses into the ``EnhancedMarketData`` contract
    consumed by the Feature Layer and downstream engines.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.POLYGON_API_KEY
        self._timeout = settings.EDPL_POLYGON_TIMEOUT
        self._client = httpx.AsyncClient(
            base_url=_POLYGON_BASE,
            timeout=self._timeout,
            headers={"Accept": "application/json"},
        )

    # ── ProviderAdapter interface ────────────────────────────────────────

    @property
    def name(self) -> str:
        return "polygon"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.MARKET_DATA

    def get_capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.INTRADAY_BARS,
            ProviderCapability.DAILY_BARS,
            ProviderCapability.LIQUIDITY_METRICS,
            ProviderCapability.TRADES_QUOTES,
        }

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """
        Fetch enhanced market data for a ticker from Polygon.io.

        Expected ``request.params``:
          - resolution: str  ("day" | "hour" | "minute")  default "day"
          - days_back: int   (lookback window)             default 30
        """
        ticker = (request.ticker or "").upper()
        if not ticker:
            return self._error_response("ticker is required")

        if not self._api_key:
            return self._error_response("POLYGON_API_KEY not configured")

        resolution = request.params.get("resolution", "day")
        days_back = request.params.get("days_back", 30)

        t0 = time.perf_counter()

        try:
            # Parallel fetches: aggregates + previous day + snapshot
            agg_data = await self._fetch_aggregates(ticker, resolution, days_back)
            prev_close = await self._fetch_previous_close(ticker)
            snapshot = await self._fetch_snapshot(ticker)

            # Build intraday bars
            bars = self._parse_bars(agg_data, ticker)

            # Build liquidity snapshot
            liquidity = self._build_liquidity(snapshot, agg_data, ticker)

            data = EnhancedMarketData(
                ticker=ticker,
                intraday_bars=bars,
                liquidity=liquidity,
                last_trade_price=prev_close,
                source="polygon",
                fetched_at=datetime.now(timezone.utc),
            )

            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)

        except httpx.TimeoutException:
            elapsed = (time.perf_counter() - t0) * 1000
            return self._error_response(
                f"Polygon timeout after {self._timeout}s", latency_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"Polygon fetch error for {ticker}: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        """Ping the Polygon /v1/marketstatus/now endpoint."""
        try:
            resp = await self._client.get(
                "/v1/marketstatus/now",
                params={"apiKey": self._api_key},
            )
            if resp.status_code == 200:
                return HealthStatus(
                    provider_name=self.name,
                    domain=self.domain,
                    status=ProviderStatus.ACTIVE,
                    message="connected",
                )
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=ProviderStatus.DEGRADED,
                message=f"HTTP {resp.status_code}",
            )
        except Exception as exc:
            return HealthStatus(
                provider_name=self.name,
                domain=self.domain,
                status=ProviderStatus.DISABLED,
                message=str(exc),
            )

    # ── Internal API calls ───────────────────────────────────────────────

    async def _fetch_aggregates(
        self, ticker: str, resolution: str, days_back: int,
    ) -> dict:
        """GET /v2/aggs/ticker/{ticker}/range/1/{res}/{from}/{to}"""
        timespan = {
            "minute": "minute",
            "hour": "hour",
            "day": "day",
        }.get(resolution, "day")

        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        from_date = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
        ).strftime("%Y-%m-%d")

        resp = await self._client.get(
            f"/v2/aggs/ticker/{ticker}/range/1/{timespan}/{from_date}/{to_date}",
            params={
                "adjusted": "true",
                "sort": "asc",
                "limit": 5000,
                "apiKey": self._api_key,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def _fetch_previous_close(self, ticker: str) -> float | None:
        """GET /v2/aggs/ticker/{ticker}/prev"""
        try:
            resp = await self._client.get(
                f"/v2/aggs/ticker/{ticker}/prev",
                params={"adjusted": "true", "apiKey": self._api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if results:
                return results[0].get("c")
        except Exception as exc:
            logger.debug(f"Previous close fetch failed for {ticker}: {exc}")
        return None

    async def _fetch_snapshot(self, ticker: str) -> dict | None:
        """GET /v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"""
        try:
            resp = await self._client.get(
                f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}",
                params={"apiKey": self._api_key},
            )
            resp.raise_for_status()
            return resp.json().get("ticker", {})
        except Exception as exc:
            logger.debug(f"Snapshot fetch failed for {ticker}: {exc}")
            return None

    # ── Parsers ──────────────────────────────────────────────────────────

    def _parse_bars(self, agg_data: dict, ticker: str) -> list[IntradayBar]:
        """Convert Polygon aggregate results to IntradayBar list."""
        results = agg_data.get("results", [])
        bars: list[IntradayBar] = []

        for r in results:
            ts_ms = r.get("t", 0)
            try:
                bars.append(IntradayBar(
                    timestamp=datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
                    open=float(r.get("o", 0)),
                    high=float(r.get("h", 0)),
                    low=float(r.get("l", 0)),
                    close=float(r.get("c", 0)),
                    volume=int(r.get("v", 0)),
                    vwap=r.get("vw"),
                    trade_count=r.get("n"),
                ))
            except (ValueError, TypeError) as exc:
                logger.debug(f"Skipping malformed bar for {ticker}: {exc}")

        return bars

    def _build_liquidity(
        self, snapshot: dict | None, agg_data: dict, ticker: str,
    ) -> LiquiditySnapshot:
        """Derive a LiquiditySnapshot from snapshot + aggregates."""
        results = agg_data.get("results", [])

        # Average daily volume (last 30 bars)
        recent = results[-30:] if len(results) >= 30 else results
        volumes = [r.get("v", 0) for r in recent]
        avg_vol = sum(volumes) / len(volumes) if volumes else 0

        # Average dollar volume
        dollar_vols = [
            r.get("v", 0) * r.get("vw", r.get("c", 0))
            for r in recent
            if r.get("v", 0) > 0
        ]
        avg_dollar_vol = sum(dollar_vols) / len(dollar_vols) if dollar_vols else 0

        # Bid-ask spread from snapshot (if available)
        spread_bps: float | None = None
        if snapshot:
            last_quote = snapshot.get("lastQuote", {})
            bid = last_quote.get("p", 0)
            ask = last_quote.get("P", 0)
            mid = (bid + ask) / 2 if bid and ask else 0
            if mid > 0:
                spread_bps = ((ask - bid) / mid) * 10000

        # Market impact estimate (simplified Almgren-Chriss for 1% participation)
        impact_bps: float | None = None
        if avg_vol > 0:
            participation_1pct = 0.01
            k = 0.1 if avg_vol > 5_000_000 else 0.2 if avg_vol > 1_000_000 else 0.5
            impact_bps = k * (participation_1pct ** 0.5) * 10000

        # Turnover ratio (if we have a price)
        turnover: float | None = None
        if snapshot:
            last_close = snapshot.get("prevDay", {}).get("c", 0)
            market_cap = snapshot.get("marketCap")  # may not exist on free tier
            if market_cap and market_cap > 0 and last_close > 0:
                turnover = (avg_vol * last_close) / market_cap

        return LiquiditySnapshot(
            ticker=ticker,
            bid_ask_spread_bps=round(spread_bps, 2) if spread_bps is not None else None,
            avg_daily_volume_30d=round(avg_vol, 0) if avg_vol else None,
            avg_dollar_volume_30d=round(avg_dollar_vol, 0) if avg_dollar_vol else None,
            market_impact_estimate_bps=round(impact_bps, 2) if impact_bps is not None else None,
            turnover_ratio=round(turnover, 6) if turnover is not None else None,
        )
