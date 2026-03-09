"""
src/routes/market_data_api.py
──────────────────────────────────────────────────────────────────────────────
Internal unified endpoints for consuming multi-source data from 365 Advisers.

These endpoints abstract over the provider layer and return canonical
contract data, ready for frontend consumption and engine input.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query, HTTPException

from src.data.external.base import DataDomain, ProviderRequest
from src.data.external.fallback import FallbackRouter
from src.data.external.scheduler import SyncManager

logger = logging.getLogger("365advisers.routes.market_data_api")

router = APIRouter(prefix="/api/data", tags=["Market Data API"])

_fallback: FallbackRouter | None = None
_sync_mgr: SyncManager | None = None


def init_market_data_routes(fallback: FallbackRouter, sync_mgr: SyncManager | None = None) -> None:
    """Called at startup to inject dependencies."""
    global _fallback, _sync_mgr
    _fallback = fallback
    _sync_mgr = sync_mgr


def _get_router() -> FallbackRouter:
    if _fallback is None:
        raise HTTPException(500, "Market data API not initialized")
    return _fallback


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/quotes/{symbol}")
async def latest_quote(symbol: str) -> dict[str, Any]:
    """Latest quote / price data for a symbol."""
    fb = _get_router()
    req = ProviderRequest(domain=DataDomain.MARKET_DATA, ticker=symbol, params={"outputsize": 1})
    resp = await fb.fetch(DataDomain.MARKET_DATA, req)
    return {"symbol": symbol, "ok": resp.ok, "provider": resp.provider_name, "data": resp.data, "latency_ms": resp.latency_ms}


@router.get("/history/{symbol}")
async def historical_prices(
    symbol: str,
    days: int = Query(default=90, ge=1, le=365),
    interval: str = Query(default="1day"),
) -> dict[str, Any]:
    """Historical OHLCV for a symbol."""
    fb = _get_router()
    req = ProviderRequest(domain=DataDomain.MARKET_DATA, ticker=symbol, params={"days_back": days, "interval": interval})
    resp = await fb.fetch(DataDomain.MARKET_DATA, req)
    return {"symbol": symbol, "ok": resp.ok, "provider": resp.provider_name, "data": resp.data, "latency_ms": resp.latency_ms}


@router.get("/fundamentals/{symbol}")
async def fundamentals(
    symbol: str,
    endpoint: str = Query(default="profile"),
) -> dict[str, Any]:
    """Fundamental data: profile, income-statement, balance-sheet, ratios, estimates."""
    fb = _get_router()
    req = ProviderRequest(domain=DataDomain.FUNDAMENTAL, ticker=symbol, params={"endpoint": endpoint})
    resp = await fb.fetch(DataDomain.FUNDAMENTAL, req)
    return {"symbol": symbol, "ok": resp.ok, "provider": resp.provider_name, "data": resp.data, "latency_ms": resp.latency_ms}


@router.get("/macro/dashboard")
async def macro_dashboard(
    indicator: str = Query(default="GDP"),
    country: str = Query(default="US"),
) -> dict[str, Any]:
    """Macro economic indicator data."""
    fb = _get_router()
    req = ProviderRequest(domain=DataDomain.MACRO, params={"indicator": indicator, "country": country})
    resp = await fb.fetch(DataDomain.MACRO, req)
    return {"ok": resp.ok, "provider": resp.provider_name, "data": resp.data, "latency_ms": resp.latency_ms}


@router.get("/sentiment/{symbol}")
async def sentiment_snapshot(symbol: str) -> dict[str, Any]:
    """Social / news sentiment for a symbol."""
    fb = _get_router()
    req = ProviderRequest(domain=DataDomain.SENTIMENT, ticker=symbol)
    resp = await fb.fetch(DataDomain.SENTIMENT, req)
    return {"symbol": symbol, "ok": resp.ok, "provider": resp.provider_name, "data": resp.data, "latency_ms": resp.latency_ms}


@router.get("/filings/{symbol}")
async def latest_filings(symbol: str) -> dict[str, Any]:
    """Recent SEC filings for a company."""
    fb = _get_router()
    req = ProviderRequest(domain=DataDomain.FILING_EVENTS, ticker=symbol)
    resp = await fb.fetch(DataDomain.FILING_EVENTS, req)
    return {"symbol": symbol, "ok": resp.ok, "provider": resp.provider_name, "data": resp.data, "latency_ms": resp.latency_ms}


@router.get("/options/{symbol}")
async def options_chain(symbol: str) -> dict[str, Any]:
    """Options intelligence for a symbol."""
    fb = _get_router()
    req = ProviderRequest(domain=DataDomain.OPTIONS, ticker=symbol)
    resp = await fb.fetch(DataDomain.OPTIONS, req)
    return {"symbol": symbol, "ok": resp.ok, "provider": resp.provider_name, "data": resp.data, "latency_ms": resp.latency_ms}


@router.get("/volatility/{symbol}")
async def volatility_snapshot(symbol: str = "^VIX") -> dict[str, Any]:
    """Volatility / VIX data."""
    fb = _get_router()
    req = ProviderRequest(domain=DataDomain.VOLATILITY, ticker=symbol)
    resp = await fb.fetch(DataDomain.VOLATILITY, req)
    return {"symbol": symbol, "ok": resp.ok, "provider": resp.provider_name, "data": resp.data, "latency_ms": resp.latency_ms}


@router.get("/sync/schedules")
async def get_sync_schedules() -> dict[str, Any]:
    """Current sync schedule configuration."""
    if _sync_mgr is None:
        return {"schedules": [], "message": "Sync manager not initialized"}
    return {"schedules": _sync_mgr.summary()}
