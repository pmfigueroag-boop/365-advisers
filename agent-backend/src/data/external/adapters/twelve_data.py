"""
src/data/external/adapters/twelve_data.py
──────────────────────────────────────────────────────────────────────────────
Twelve Data Adapter — real-time & historical market data provider.

Provides:
  - Time series (1min to monthly) for stocks, forex, crypto
  - Real-time and delayed quotes
  - Technical indicators (RSI, MACD, SMA, EMA, etc.)
  - Exchange info and reference data

Rate limiting: Free = 8 req/min, 800 req/day.
               Grow = 800 req/min.

Docs: https://twelvedata.com/docs
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
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
)

logger = logging.getLogger("365advisers.external.twelve_data")

_TD_BASE = "https://api.twelvedata.com"


class TwelveDataAdapter(ProviderAdapter):
    """
    Adapter for the Twelve Data REST API.

    Secondary market data provider for time series and technical indicators.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.TWELVE_DATA_API_KEY
        self._timeout = settings.EDPL_TD_TIMEOUT
        self._client = httpx.AsyncClient(
            base_url=_TD_BASE,
            timeout=self._timeout,
            headers={"Accept": "application/json"},
        )

    @property
    def name(self) -> str:
        return "twelve_data"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.MARKET_DATA

    def get_capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.INTRADAY_BARS,
            ProviderCapability.DAILY_BARS,
        }

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """
        Fetch time series from Twelve Data.

        Expected request.params:
          - interval: str  ("1min","5min","15min","1h","1day","1week","1month")
                           default "1day"
          - outputsize: int (number of data points, max 5000)  default 90
        """
        ticker = (request.ticker or "").upper()
        if not ticker:
            return self._error_response("ticker is required")
        if not self._api_key:
            return self._error_response("TWELVE_DATA_API_KEY not configured")

        interval = request.params.get("interval", "1day")
        outputsize = request.params.get("outputsize", 90)
        t0 = time.perf_counter()

        try:
            resp = await self._client.get(
                "/time_series",
                params={
                    "symbol": ticker,
                    "interval": interval,
                    "outputsize": outputsize,
                    "apikey": self._api_key,
                },
            )
            resp.raise_for_status()
            raw = resp.json()

            if raw.get("status") == "error":
                elapsed = (time.perf_counter() - t0) * 1000
                return self._error_response(
                    raw.get("message", "Unknown error"), latency_ms=elapsed,
                )

            bars = self._parse_values(raw.get("values", []), interval)
            last_price = bars[0].close if bars else None

            data = EnhancedMarketData(
                ticker=ticker,
                intraday_bars=bars,
                last_trade_price=last_price,
                source="twelve_data",
                fetched_at=datetime.now(timezone.utc),
            )
            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)

        except httpx.TimeoutException:
            elapsed = (time.perf_counter() - t0) * 1000
            return self._error_response(
                f"Timeout after {self._timeout}s", latency_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"Twelve Data error for {ticker}: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        try:
            resp = await self._client.get(
                "/time_series",
                params={
                    "symbol": "AAPL",
                    "interval": "1day",
                    "outputsize": 1,
                    "apikey": self._api_key,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") != "error":
                    return HealthStatus(
                        provider_name=self.name, domain=self.domain,
                        status=ProviderStatus.ACTIVE, message="connected",
                    )
            return HealthStatus(
                provider_name=self.name, domain=self.domain,
                status=ProviderStatus.DEGRADED,
                message=f"HTTP {resp.status_code}",
            )
        except Exception as exc:
            return HealthStatus(
                provider_name=self.name, domain=self.domain,
                status=ProviderStatus.DISABLED, message=str(exc),
            )

    def _parse_values(self, values: list[dict], interval: str) -> list[IntradayBar]:
        bars: list[IntradayBar] = []
        fmt = "%Y-%m-%d %H:%M:%S" if "min" in interval or "h" in interval else "%Y-%m-%d"
        for v in values:
            try:
                ts = datetime.strptime(v["datetime"], fmt).replace(tzinfo=timezone.utc)
                bars.append(IntradayBar(
                    timestamp=ts,
                    open=float(v.get("open", 0)),
                    high=float(v.get("high", 0)),
                    low=float(v.get("low", 0)),
                    close=float(v.get("close", 0)),
                    volume=int(float(v.get("volume", 0))),
                ))
            except (ValueError, TypeError, KeyError):
                continue
        return bars
