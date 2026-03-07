"""
src/data/external/registry.py
──────────────────────────────────────────────────────────────────────────────
Provider Registry — central catalogue of registered external data adapters.

The registry keeps an ordered list of adapters per DataDomain (priority
order) and exposes helpers to resolve the best available adapter for a
given domain at runtime.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Sequence

from src.data.external.base import (
    DataDomain,
    ProviderAdapter,
    ProviderCapability,
    ProviderStatus,
)

logger = logging.getLogger("365advisers.external.registry")


class ProviderRegistry:
    """
    Thread-safe registry of ProviderAdapters, keyed by DataDomain.

    Adapters are stored in **priority order** — the first adapter registered
    for a domain is the preferred one.  The FallbackRouter consults this
    ordering when the primary adapter fails.

    Usage
    -----
    >>> registry = ProviderRegistry()
    >>> registry.register(PolygonAdapter())
    >>> registry.register(YFinanceLegacyAdapter())   # lower priority
    >>> adapter = registry.get_primary(DataDomain.MARKET_DATA)
    """

    def __init__(self) -> None:
        self._adapters: dict[DataDomain, list[ProviderAdapter]] = defaultdict(list)
        self._status: dict[str, ProviderStatus] = {}

    # ── Registration ─────────────────────────────────────────────────────

    def register(
        self,
        adapter: ProviderAdapter,
        *,
        priority: int | None = None,
    ) -> None:
        """
        Register an adapter for its declared domain.

        Parameters
        ----------
        adapter : ProviderAdapter
            The adapter instance.
        priority : int | None
            Position in the priority list (0 = highest).  ``None`` appends
            at the end (lowest priority).
        """
        domain = adapter.domain
        adapters = self._adapters[domain]

        if any(a.name == adapter.name for a in adapters):
            logger.warning(f"Adapter '{adapter.name}' already registered for {domain.value} — skipping")
            return

        if priority is not None and 0 <= priority < len(adapters):
            adapters.insert(priority, adapter)
        else:
            adapters.append(adapter)

        self._status[adapter.name] = ProviderStatus.UNKNOWN
        logger.info(
            f"Registered adapter '{adapter.name}' for domain "
            f"'{domain.value}' (priority {priority or len(adapters) - 1})"
        )

    def unregister(self, adapter_name: str) -> bool:
        """Remove an adapter by name.  Returns True if found and removed."""
        for domain, adapters in self._adapters.items():
            for i, a in enumerate(adapters):
                if a.name == adapter_name:
                    adapters.pop(i)
                    self._status.pop(adapter_name, None)
                    logger.info(f"Unregistered adapter '{adapter_name}' from {domain.value}")
                    return True
        return False

    # ── Lookup ───────────────────────────────────────────────────────────

    def get_primary(self, domain: DataDomain) -> ProviderAdapter | None:
        """Return the highest-priority adapter for *domain*, or None."""
        adapters = self._adapters.get(domain, [])
        for adapter in adapters:
            if self._status.get(adapter.name) != ProviderStatus.DISABLED:
                return adapter
        return None

    def get_all(self, domain: DataDomain) -> Sequence[ProviderAdapter]:
        """Return all registered adapters for *domain* in priority order."""
        return list(self._adapters.get(domain, []))

    def get_by_name(self, name: str) -> ProviderAdapter | None:
        """Find an adapter by name across all domains."""
        for adapters in self._adapters.values():
            for a in adapters:
                if a.name == name:
                    return a
        return None

    def get_capable(
        self, domain: DataDomain, capability: ProviderCapability,
    ) -> ProviderAdapter | None:
        """Return the first non-disabled adapter that supports *capability*."""
        for adapter in self._adapters.get(domain, []):
            if (
                self._status.get(adapter.name) != ProviderStatus.DISABLED
                and capability in adapter.get_capabilities()
            ):
                return adapter
        return None

    # ── Status Management ────────────────────────────────────────────────

    def set_status(self, adapter_name: str, status: ProviderStatus) -> None:
        """Update runtime status of an adapter."""
        if adapter_name in self._status:
            old = self._status[adapter_name]
            self._status[adapter_name] = status
            if old != status:
                logger.info(f"Provider '{adapter_name}' status: {old.value} → {status.value}")

    def get_status(self, adapter_name: str) -> ProviderStatus:
        return self._status.get(adapter_name, ProviderStatus.UNKNOWN)

    # ── Introspection ────────────────────────────────────────────────────

    def list_domains(self) -> list[DataDomain]:
        """Return domains that have at least one registered adapter."""
        return [d for d, adapters in self._adapters.items() if adapters]

    def summary(self) -> dict[str, list[dict]]:
        """
        Return a serialisable summary of all registered adapters.

        Used by the ``/api/health/providers`` endpoint.
        """
        result: dict[str, list[dict]] = {}
        for domain, adapters in self._adapters.items():
            result[domain.value] = [
                {
                    "name": a.name,
                    "status": self._status.get(a.name, ProviderStatus.UNKNOWN).value,
                    "capabilities": sorted(c.value for c in a.get_capabilities()),
                }
                for a in adapters
            ]
        return result
