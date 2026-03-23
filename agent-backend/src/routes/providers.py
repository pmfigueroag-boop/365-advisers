"""
src/routes/providers.py
──────────────────────────────────────────────────────────────────────────────
API endpoints for the External Data Provider Layer (EDPL).

Exposes provider health, status, coverage reports, and
introspection endpoints.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query

from src.data.external.base import DataDomain, ProviderStatus
from src.data.external.registry import ProviderRegistry
from src.data.external.health import HealthChecker

logger = logging.getLogger("365advisers.routes.providers")

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/providers", tags=["providers"], dependencies=[Depends(get_current_user)])


# ─── Singleton instances (initialised at startup via lifespan) ────────────────
# These will be populated by the app startup hook; the route handlers access
# them through module-level references.

_registry: ProviderRegistry | None = None
_health_checker: HealthChecker | None = None


def init_provider_routes(
    registry: ProviderRegistry,
    health_checker: HealthChecker,
) -> None:
    """
    Called during app startup to inject the global EDPL singletons.

    This avoids circular imports and keeps the route module stateless
    until the app is fully initialised.
    """
    global _registry, _health_checker
    _registry = registry
    _health_checker = health_checker
    logger.info("Provider routes initialised with EDPL singletons")


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/health")
async def provider_health():
    """
    Health status of all registered external data providers.

    Returns per-provider status, circuit breaker state, latency,
    last success/failure timestamps, and consecutive failure count.
    Also includes aggregate health status.
    """
    if _health_checker is None:
        return {"status": "not_initialised", "providers": {}}

    summary = _health_checker.summary()

    # Compute aggregate status
    all_statuses = [p.get("status", "unknown") for p in summary.values()]
    active = sum(1 for s in all_statuses if s == "active")
    degraded = sum(1 for s in all_statuses if s == "degraded")
    disabled = sum(1 for s in all_statuses if s == "disabled")

    if degraded > len(all_statuses) * 0.5:
        overall = "critical"
    elif degraded > 0:
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "status": "ok",
        "overall_status": overall,
        "active_count": active,
        "degraded_count": degraded,
        "disabled_count": disabled,
        "providers": summary,
    }


@router.get("/registry")
async def provider_registry():
    """
    Introspection of all registered providers — domain, capabilities, status.
    """
    if _registry is None:
        return {"status": "not_initialised", "domains": {}}

    return {
        "status": "ok",
        "domains": _registry.summary(),
        "active_domains": [d.value for d in _registry.list_domains()],
    }


@router.get("/health/{provider_name}")
async def provider_health_detail(provider_name: str):
    """
    Detailed health status for a single provider.
    """
    if _health_checker is None:
        return {"status": "not_initialised"}

    health = _health_checker.get_health(provider_name)
    return health.model_dump(mode="json")


@router.get("/health/history/{provider_name}")
async def provider_health_history(
    provider_name: str,
    hours: int = Query(default=24, ge=1, le=168, description="Hours of history to retrieve"),
):
    """
    Health snapshot history for a provider over the last N hours.

    Used by the frontend System view to render health sparklines.
    """
    # This endpoint returns data from the persistence layer
    # when available. Falls back to empty list if persistence
    # is not configured.
    try:
        from src.data.database import SessionLocal
        from src.data.external.persistence.repository import EDPLRepository

        with SessionLocal() as session:
            repo = EDPLRepository(session)
            records = repo.get_health_history(provider_name, hours)
            return {
                "provider_name": provider_name,
                "hours": hours,
                "snapshots": [
                    {
                        "status": r.status,
                        "circuit_breaker_state": r.circuit_breaker_state,
                        "consecutive_failures": r.consecutive_failures,
                        "avg_latency_ms": r.avg_latency_ms,
                        "success_rate_24h": r.success_rate_24h,
                        "snapshot_at": r.snapshot_at.isoformat() if r.snapshot_at else None,
                    }
                    for r in records
                ],
            }
    except Exception as exc:
        logger.debug(f"Health history not available: {exc}")
        return {
            "provider_name": provider_name,
            "hours": hours,
            "snapshots": [],
            "message": "Persistence layer not configured",
        }


@router.get("/coverage/{ticker}")
async def coverage_history(
    ticker: str,
    limit: int = Query(default=10, ge=1, le=50, description="Number of records"),
):
    """
    Coverage report history for a specific ticker.

    Used by the frontend Analysis view to render historical completeness.
    """
    try:
        import json
        from src.data.database import SessionLocal
        from src.data.external.persistence.repository import EDPLRepository

        with SessionLocal() as session:
            repo = EDPLRepository(session)
            records = repo.get_coverage_history(ticker, limit)
            return {
                "ticker": ticker,
                "history": [
                    {
                        "analysis_id": r.analysis_id,
                        "completeness_score": r.completeness_score,
                        "completeness_label": r.completeness_label,
                        "partial_domains": json.loads(r.partial_domains_json or "[]"),
                        "unavailable_domains": json.loads(r.unavailable_domains_json or "[]"),
                        "messages": json.loads(r.messages_json or "[]"),
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in records
                ],
            }
    except Exception as exc:
        logger.debug(f"Coverage history not available: {exc}")
        return {"ticker": ticker, "history": [], "message": "Persistence not configured"}


@router.post("/{provider_name}/disable")
async def disable_provider(provider_name: str):
    """
    Manually disable a provider (admin action).

    The provider will be skipped by the FallbackRouter until re-enabled.
    """
    if _registry is None:
        return {"error": "not_initialised"}

    adapter = _registry.get_by_name(provider_name)
    if adapter is None:
        return {"error": f"provider '{provider_name}' not found"}

    _registry.set_status(provider_name, ProviderStatus.DISABLED)
    return {"status": "disabled", "provider": provider_name}


@router.post("/{provider_name}/enable")
async def enable_provider(provider_name: str):
    """
    Re-enable a previously disabled provider.
    """
    if _registry is None:
        return {"error": "not_initialised"}

    adapter = _registry.get_by_name(provider_name)
    if adapter is None:
        return {"error": f"provider '{provider_name}' not found"}

    _registry.set_status(provider_name, ProviderStatus.UNKNOWN)
    return {"status": "enabled", "provider": provider_name}

