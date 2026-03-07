"""
src/data/external/health.py
──────────────────────────────────────────────────────────────────────────────
HealthChecker & CircuitBreaker for external data providers.

Each adapter has an independent circuit breaker.  The HealthChecker
aggregates status across all providers for the ``/api/health/providers``
endpoint and provides record_success / record_failure hooks consumed
by the FallbackRouter.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone

from src.data.external.base import DataDomain, HealthStatus, ProviderStatus

logger = logging.getLogger("365advisers.external.health")


# ─── Exceptions ───────────────────────────────────────────────────────────────


class CircuitBreakerOpen(Exception):
    """Raised when a circuit breaker is in the OPEN state."""
    pass


# ─── Circuit Breaker ──────────────────────────────────────────────────────────


class CircuitBreaker:
    """
    Per-provider circuit breaker (Closed → Open → Half-Open → Closed).

    - **Closed** (normal):   requests pass through.
    - **Open** (tripped):    requests are blocked; enters half-open after
                             ``recovery_timeout`` seconds.
    - **Half-Open** (probe): a single request is allowed; success closes
                             the circuit, failure re-opens it.

    Parameters
    ----------
    failure_threshold : int
        Consecutive failures before opening the circuit (default 3).
    recovery_timeout : float
        Seconds to wait before transitioning from open → half-open (default 60).
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state: str = "closed"  # closed / open / half_open
        self._consecutive_failures: int = 0
        self._last_failure_time: float = 0.0

    @property
    def state(self) -> str:
        # Auto-transition from open → half_open when timeout elapsed
        if self._state == "open":
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = "half_open"
        return self._state

    @property
    def is_open(self) -> bool:
        return self.state == "open"

    def record_success(self) -> None:
        """Record a successful call — reset circuit to closed."""
        self._consecutive_failures = 0
        self._state = "closed"

    def record_failure(self) -> None:
        """Record a failed call — may trip the circuit."""
        self._consecutive_failures += 1
        self._last_failure_time = time.monotonic()

        if self._consecutive_failures >= self.failure_threshold:
            if self._state != "open":
                logger.warning(
                    f"Circuit breaker OPENED after {self._consecutive_failures} "
                    f"consecutive failures (threshold={self.failure_threshold})"
                )
            self._state = "open"


# ─── Health Checker ───────────────────────────────────────────────────────────


class HealthChecker:
    """
    Aggregates health metrics for all registered providers.

    Each provider's circuit breaker and latency stats are tracked
    independently.  The ``summary()`` method returns a serialisable
    snapshot for API consumers.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout

        self._breakers: dict[str, CircuitBreaker] = {}
        self._last_success: dict[str, datetime] = {}
        self._last_failure: dict[str, datetime] = {}
        self._last_error: dict[str, str] = {}
        self._latencies: dict[str, list[float]] = defaultdict(list)
        # Map provider name → domain (set during first record call or register)
        self._domains: dict[str, DataDomain] = {}

    # ── Setup ────────────────────────────────────────────────────────────

    def register_provider(self, name: str, domain: DataDomain) -> None:
        """Pre-register a provider so its breaker exists before the first call."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                self._failure_threshold, self._recovery_timeout,
            )
            self._domains[name] = domain

    def _ensure_breaker(self, name: str) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                self._failure_threshold, self._recovery_timeout,
            )
        return self._breakers[name]

    # ── Recording ────────────────────────────────────────────────────────

    def record_success(self, provider_name: str, latency_ms: float = 0.0) -> None:
        """Record a successful fetch."""
        breaker = self._ensure_breaker(provider_name)
        breaker.record_success()
        self._last_success[provider_name] = datetime.now(timezone.utc)
        self._latencies[provider_name].append(latency_ms)
        # Keep a rolling window of 100 measurements
        if len(self._latencies[provider_name]) > 100:
            self._latencies[provider_name] = self._latencies[provider_name][-100:]

    def record_failure(self, provider_name: str, error: str = "") -> None:
        """Record a failed fetch."""
        breaker = self._ensure_breaker(provider_name)
        breaker.record_failure()
        self._last_failure[provider_name] = datetime.now(timezone.utc)
        self._last_error[provider_name] = error

    # ── Query ────────────────────────────────────────────────────────────

    def is_circuit_open(self, provider_name: str) -> bool:
        """Check if the circuit breaker for *provider_name* is open."""
        breaker = self._breakers.get(provider_name)
        return breaker.is_open if breaker else False

    def get_health(self, provider_name: str) -> HealthStatus:
        """Return detailed health for a single provider."""
        breaker = self._ensure_breaker(provider_name)
        lats = self._latencies.get(provider_name, [])
        avg_lat = sum(lats) / len(lats) if lats else 0.0

        if breaker.state == "open":
            status = ProviderStatus.DISABLED
        elif breaker.state == "half_open":
            status = ProviderStatus.DEGRADED
        elif breaker._consecutive_failures > 0:
            status = ProviderStatus.DEGRADED
        else:
            status = ProviderStatus.ACTIVE

        return HealthStatus(
            provider_name=provider_name,
            domain=self._domains.get(provider_name, DataDomain.MARKET_DATA),
            status=status,
            last_success=self._last_success.get(provider_name),
            last_failure=self._last_failure.get(provider_name),
            consecutive_failures=breaker._consecutive_failures,
            avg_latency_ms=round(avg_lat, 1),
            message=self._last_error.get(provider_name, ""),
        )

    # ── Summary ──────────────────────────────────────────────────────────

    def summary(self) -> dict[str, dict]:
        """
        Serialisable health summary of all known providers.

        Returns ``{provider_name: HealthStatus.model_dump()}``.
        """
        return {
            name: self.get_health(name).model_dump(mode="json")
            for name in self._breakers
        }
