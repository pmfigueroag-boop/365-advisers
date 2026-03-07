"""
src/routes/providers.py
──────────────────────────────────────────────────────────────────────────────
API endpoints for the External Data Provider Layer (EDPL).

Exposes provider health, status, and introspection endpoints.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from src.data.external.base import DataDomain, ProviderStatus
from src.data.external.registry import ProviderRegistry
from src.data.external.health import HealthChecker

logger = logging.getLogger("365advisers.routes.providers")

router = APIRouter(prefix="/providers", tags=["providers"])


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
    """
    if _health_checker is None:
        return {"status": "not_initialised", "providers": {}}

    return {
        "status": "ok",
        "providers": _health_checker.summary(),
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
