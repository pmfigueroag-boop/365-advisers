"""
src/data/external/fallback.py
──────────────────────────────────────────────────────────────────────────────
FallbackRouter — resilient request routing with automatic fallback.

When the primary adapter for a domain fails (or its circuit breaker is
open), the router transparently tries the next adapter in the registry's
priority chain.  If all adapters fail, a Null/empty contract is returned
so that downstream engines continue to operate in degraded mode.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from src.data.external.base import (
    DataDomain,
    ProviderAdapter,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
)
from src.data.external.registry import ProviderRegistry
from src.data.external.health import CircuitBreakerOpen, HealthChecker

logger = logging.getLogger("365advisers.external.fallback")


class FallbackRouter:
    """
    Routes data requests through the adapter priority chain with
    automatic fallback and circuit-breaker integration.

    Usage
    -----
    >>> router = FallbackRouter(registry, health_checker)
    >>> response = await router.fetch(DataDomain.MARKET_DATA, request)
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        health_checker: HealthChecker,
        null_factories: dict[DataDomain, Callable[[], Any]] | None = None,
    ) -> None:
        self._registry = registry
        self._health = health_checker
        # Factories that produce an empty-but-valid contract per domain
        self._null_factories: dict[DataDomain, Callable[[], Any]] = null_factories or {}

    def register_null_factory(
        self, domain: DataDomain, factory: Callable[[], Any],
    ) -> None:
        """Register a factory that returns a Null/empty contract for *domain*."""
        self._null_factories[domain] = factory

    async def fetch(
        self,
        domain: DataDomain,
        request: ProviderRequest,
    ) -> ProviderResponse:
        """
        Attempt to fetch data by walking the adapter priority chain.

        1. For each adapter (highest priority first):
           a. Check circuit breaker — if open, skip.
           b. Call ``adapter.fetch(request)``.
           c. If OK, record success with HealthChecker and return.
           d. If error, record failure and try next.
        2. If all adapters fail, return a null contract response.
        """
        adapters = self._registry.get_all(domain)

        if not adapters:
            logger.warning(f"No adapters registered for domain '{domain.value}' — returning null")
            return self._null_response(domain, request)

        last_error: str = ""
        for adapter in adapters:
            adapter_name = adapter.name

            # Check circuit breaker
            if self._health.is_circuit_open(adapter_name):
                logger.debug(f"Circuit breaker open for '{adapter_name}' — skipping")
                continue

            # Check if disabled
            if self._registry.get_status(adapter_name) == ProviderStatus.DISABLED:
                logger.debug(f"Adapter '{adapter_name}' is disabled — skipping")
                continue

            try:
                t0 = time.perf_counter()
                response = await adapter.fetch(request)
                elapsed = (time.perf_counter() - t0) * 1000
                response.latency_ms = elapsed

                if response.ok:
                    self._health.record_success(adapter_name, elapsed)
                    self._registry.set_status(adapter_name, ProviderStatus.ACTIVE)
                    logger.debug(
                        f"[{domain.value}] '{adapter_name}' OK in {elapsed:.0f}ms"
                    )
                    return response

                # Partial failure — data was None or had an error
                last_error = response.error or "empty response"
                self._health.record_failure(adapter_name, last_error)
                logger.warning(
                    f"[{domain.value}] '{adapter_name}' returned error: {last_error}"
                )

            except CircuitBreakerOpen:
                logger.debug(f"Circuit breaker tripped for '{adapter_name}'")
                continue

            except Exception as exc:
                last_error = str(exc)
                self._health.record_failure(adapter_name, last_error)
                logger.warning(
                    f"[{domain.value}] '{adapter_name}' exception: {last_error}"
                )

        # All adapters exhausted — return null contract
        logger.warning(
            f"All adapters for '{domain.value}' failed — returning null contract. "
            f"Last error: {last_error}"
        )
        return self._null_response(domain, request, last_error)

    # ── Internal ──────────────────────────────────────────────────────────

    def _null_response(
        self,
        domain: DataDomain,
        request: ProviderRequest,
        error: str = "no adapters available",
    ) -> ProviderResponse:
        """Build a response with a null/empty contract."""
        null_data = None
        factory = self._null_factories.get(domain)
        if factory is not None:
            try:
                null_data = factory()
            except Exception as exc:
                logger.error(f"Null factory for '{domain.value}' failed: {exc}")

        return ProviderResponse(
            domain=domain,
            provider_name="null",
            status=ProviderStatus.DEGRADED,
            data=null_data,
            error=error,
        )
