"""
src/data/external/adapters/stocktwits.py
──────────────────────────────────────────────────────────────────────────────
Stocktwits Adapter — social sentiment from the investment community.

Provides: sentiment per symbol, message volume, trending, watchlist count.
Rate limiting: 200 req/hour with API key, 50 without.
Docs: https://api.stocktwits.com/developers/docs
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import httpx

from src.config import get_settings
from src.data.external.base import (
    DataDomain, HealthStatus, ProviderAdapter, ProviderCapability,
    ProviderRequest, ProviderResponse, ProviderStatus,
)
from src.data.external.contracts.sentiment_signal import SentimentSignal, SocialMention

logger = logging.getLogger("365advisers.external.stocktwits")
_ST_BASE = "https://api.stocktwits.com/api/2"


class StocktwitsAdapter(ProviderAdapter):
    def __init__(self) -> None:
        s = get_settings()
        self._api_key = s.STOCKTWITS_API_KEY
        self._timeout = s.EDPL_ST_TIMEOUT
        self._client = httpx.AsyncClient(base_url=_ST_BASE, timeout=self._timeout)

    @property
    def name(self) -> str:
        return "stocktwits"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.SENTIMENT

    def get_capabilities(self) -> set[ProviderCapability]:
        return {ProviderCapability.SOCIAL_SENTIMENT, ProviderCapability.SENTIMENT_SCORES}

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        ticker = (request.ticker or "").upper()
        if not ticker:
            return self._error_response("ticker is required")
        t0 = time.perf_counter()
        try:
            params: dict[str, str] = {}
            if self._api_key:
                params["access_token"] = self._api_key
            resp = await self._client.get(f"/streams/symbol/{ticker}.json", params=params)
            resp.raise_for_status()
            raw = resp.json()
            data = self._transform(ticker, raw)
            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)
        except httpx.TimeoutException:
            elapsed = (time.perf_counter() - t0) * 1000
            return self._error_response(f"Timeout after {self._timeout}s", latency_ms=elapsed)
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"Stocktwits error for {ticker}: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        try:
            resp = await self._client.get("/streams/trending.json")
            status = ProviderStatus.ACTIVE if resp.status_code == 200 else ProviderStatus.DEGRADED
            return HealthStatus(provider_name=self.name, domain=self.domain, status=status, message="ok")
        except Exception as exc:
            return HealthStatus(provider_name=self.name, domain=self.domain, status=ProviderStatus.DISABLED, message=str(exc))

    def _transform(self, ticker: str, raw: dict) -> SentimentSignal:
        sym = raw.get("symbol", {})
        msgs = raw.get("messages", [])
        bull = sum(1 for m in msgs if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bullish")
        bear = sum(1 for m in msgs if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bearish")
        total = bull + bear
        mentions: list[SocialMention] = []
        for m in msgs[:10]:
            sb = m.get("entities", {}).get("sentiment", {}).get("basic", "")
            mentions.append(SocialMention(platform="stocktwits", message=m.get("body", "")[:200], sentiment=sb.lower() or "neutral"))
        return SentimentSignal(
            ticker=ticker, platform="stocktwits",
            bullish_pct=round(bull / total * 100, 1) if total else None,
            bearish_pct=round(bear / total * 100, 1) if total else None,
            sentiment_score=round((bull - bear) / total, 3) if total else None,
            message_volume_24h=len(msgs),
            watchlist_count=sym.get("watchlist_count"),
            is_trending=sym.get("is_trending", False),
            recent_mentions=mentions,
            source="stocktwits", fetched_at=datetime.now(timezone.utc),
        )
