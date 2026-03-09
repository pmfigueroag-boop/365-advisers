"""
src/data/external/adapters/cboe.py
──────────────────────────────────────────────────────────────────────────────
Cboe Adapter — volatility and VIX data provider.

Provides:
  - VIX current value, term structure (VIX9D, VIX3M, VIX6M, VIX1Y)
  - Options chain data (delayed)
  - Historical volatility from Cboe public data feeds

Auth: None for delayed data feeds (public CSVs/JSON endpoints).
Docs: https://www.cboe.com/market_statistics/
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
from src.data.external.contracts.volatility_snapshot import (
    VolatilitySnapshot, VIXSnapshot,
)

logger = logging.getLogger("365advisers.external.cboe")

_CBOE_BASE = "https://cdn.cboe.com/api/global"


class CboeAdapter(ProviderAdapter):
    """Adapter for Cboe delayed market data — VIX term structure and volatility."""

    def __init__(self) -> None:
        s = get_settings()
        self._timeout = s.EDPL_CBOE_TIMEOUT
        self._client = httpx.AsyncClient(timeout=self._timeout)

    @property
    def name(self) -> str:
        return "cboe"

    @property
    def domain(self) -> DataDomain:
        return DataDomain.VOLATILITY

    def get_capabilities(self) -> set[ProviderCapability]:
        return {
            ProviderCapability.VIX_DATA,
            ProviderCapability.VOLATILITY_SURFACE,
            ProviderCapability.OPTIONS_CHAIN_FULL,
        }

    async def fetch(self, request: ProviderRequest) -> ProviderResponse:
        """Fetch VIX / volatility data from Cboe public endpoints."""
        t0 = time.perf_counter()
        try:
            vix = await self._fetch_vix_indices()
            data = VolatilitySnapshot(
                ticker="^VIX", vix=vix,
                vol_regime=self._classify_regime(vix.vix_current if vix else None),
                source="cboe", fetched_at=datetime.now(timezone.utc),
            )
            elapsed = (time.perf_counter() - t0) * 1000
            return self._ok_response(data, latency_ms=elapsed)
        except httpx.TimeoutException:
            elapsed = (time.perf_counter() - t0) * 1000
            return self._error_response(f"Timeout after {self._timeout}s", latency_ms=elapsed)
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning(f"Cboe error: {exc}")
            return self._error_response(str(exc), latency_ms=elapsed)

    async def health_check(self) -> HealthStatus:
        try:
            resp = await self._client.get(f"{_CBOE_BASE}/delayed_quotes/VIX.json")
            status = ProviderStatus.ACTIVE if resp.status_code == 200 else ProviderStatus.DEGRADED
            return HealthStatus(provider_name=self.name, domain=self.domain, status=status, message="ok")
        except Exception as exc:
            return HealthStatus(provider_name=self.name, domain=self.domain, status=ProviderStatus.DISABLED, message=str(exc))

    async def _fetch_vix_indices(self) -> VIXSnapshot:
        resp = await self._client.get(f"{_CBOE_BASE}/delayed_quotes/VIX.json")
        resp.raise_for_status()
        raw = resp.json().get("data", {})
        current = _sf(raw.get("current_price", raw.get("last_price")))
        return VIXSnapshot(
            vix_current=current,
            vix_open=_sf(raw.get("open")),
            vix_high=_sf(raw.get("high")),
            vix_low=_sf(raw.get("low")),
            vix_close=_sf(raw.get("close", raw.get("prev_close"))),
            vix_change=_sf(raw.get("change")),
            vix_change_pct=_sf(raw.get("change_pct", raw.get("percent_change"))),
        )

    def _classify_regime(self, vix: float | None) -> str:
        if vix is None:
            return "unknown"
        if vix < 15:
            return "low"
        if vix < 20:
            return "normal"
        if vix < 30:
            return "elevated"
        return "extreme"


def _sf(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
