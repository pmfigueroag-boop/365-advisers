"""
src/data/external/adapters/santiment.py
──────────────────────────────────────────────────────────────────────────────
Santiment Adapter — crypto social and on-chain analytics.

Provides: social volume, dev activity, whale alerts, sentiment for crypto.
Auth: API key required. Free tier has limited queries.
Docs: https://academy.santiment.net/for-developers/
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
from src.data.external.contracts.sentiment_signal import SentimentSignal

logger = logging.getLogger("365advisers.external.santiment")
_SAN_BASE = "https://api.santiment.net/graphql"


class SantimentAdapter(ProviderAdapter):
    """Adapter for Santiment GraphQL API — crypto sentiment & on-chain data."""

    def __init__(self) -> None:
        s = get_settings()
        self._api_key = s.SANTIMENT_API_KEY
        self._timeout = s.EDPL_SAN_TIMEOUT
        self._client = httpx.AsyncClient(timeout=self._timeout)

    @property
    def name(self) -> str:
        return "santiment"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.SENTIMENT

    def get_capabilities(self) -> set[ProviderCapability]:
        return {ProviderCapability.SOCIAL_SENTIMENT}

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        ticker = (request.ticker or "").lower()
        if not ticker:
            return self._error_response("ticker/slug is required")
        if not self._api_key:
            return self._error_response("SANTIMENT_API_KEY not configured")
        t0 = time.perf_counter()
        try:
            query = """{ getMetric(metric: "social_volume_total") {
                timeseriesData(slug: "%s" from: "utc_now-7d" to: "utc_now" interval: "1d") {
                    datetime value } } }""" % ticker
            resp = await self._client.post(
                _SAN_BASE, json={"query": query},
                headers={"Authorization": f"Apikey {self._api_key}"},
            )
            resp.raise_for_status()
            raw = resp.json()
            ts_data = raw.get("data", {}).get("getMetric", {}).get("timeseriesData", [])
            total_vol = sum(d.get("value", 0) for d in ts_data)
            data = SentimentSignal(
                ticker=ticker.upper(), platform="santiment",
                message_volume_7d=int(total_vol),
                source="santiment", fetched_at=datetime.now(timezone.utc),
            )
            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"Santiment error: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        if not self._api_key:
            return HealthStatus(provider_name=self.name, domain=self.domain, status=ProviderStatus.DISABLED, message="no API key")
        try:
            resp = await self._client.post(
                _SAN_BASE, json={"query": "{ currentUser { id } }"},
                headers={"Authorization": f"Apikey {self._api_key}"},
            )
            status = ProviderStatus.ACTIVE if resp.status_code == 200 else ProviderStatus.DEGRADED
            return HealthStatus(provider_name=self.name, domain=self.domain, status=status, message="ok")
        except Exception as exc:
            return HealthStatus(provider_name=self.name, domain=self.domain, status=ProviderStatus.DISABLED, message=str(exc))
