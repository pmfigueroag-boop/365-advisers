"""
src/data/external/__init__.py
──────────────────────────────────────────────────────────────────────────────
External Data Provider Layer (EDPL).

Central abstraction between raw external data sources (Polygon, FRED, etc.)
and the internal Feature Layer / Engines.  Every adapter returns typed
contracts; the FallbackRouter ensures graceful degradation.
"""

from src.data.external.base import (
    DataDomain,
    ProviderAdapter,
    ProviderCapability,
    ProviderStatus,
)
from src.data.external.registry import ProviderRegistry
from src.data.external.fallback import FallbackRouter
from src.data.external.health import CircuitBreaker, HealthChecker

__all__ = [
    "DataDomain",
    "ProviderAdapter",
    "ProviderCapability",
    "ProviderStatus",
    "ProviderRegistry",
    "FallbackRouter",
    "CircuitBreaker",
    "HealthChecker",
]
