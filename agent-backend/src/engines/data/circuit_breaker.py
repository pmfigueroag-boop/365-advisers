"""
src/engines/data/circuit_breaker.py
--------------------------------------------------------------------------
Data Pipeline Circuit Breaker — failover between data providers.

Patterns:
  - Circuit breaker: open after N consecutive failures, half-open after cooldown
  - Failover chain: try primary → secondary → tertiary
  - Health checks: periodic pings to detect recovery
  - Metrics: uptime, error rates, response times per provider

States:
  CLOSED   → normal operation, requests flow through
  OPEN     → provider down, skip entirely
  HALF_OPEN → cooldown elapsed, try one request

Usage::

    cb = CircuitBreakerManager()
    cb.register("yfinance", priority=1)
    cb.register("alpha_vantage", priority=2)
    cb.register("twelve_data", priority=3)

    provider = cb.get_available()  # returns highest-priority healthy provider
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.data.circuit_breaker")


# ── Contracts ────────────────────────────────────────────────────────────────

class BreakerState(str, Enum):
    CLOSED = "closed"       # Normal — requests flow
    OPEN = "open"           # Down — skip this provider
    HALF_OPEN = "half_open" # Trying recovery


class CircuitBreakerConfig(BaseModel):
    """Configuration for circuit breakers."""
    failure_threshold: int = Field(
        3, description="Consecutive failures before opening circuit",
    )
    cooldown_seconds: float = Field(
        60.0, description="Seconds to wait before half-open",
    )
    success_threshold: int = Field(
        2, description="Consecutive successes in half-open to close",
    )


class ProviderHealth(BaseModel):
    """Health metrics for a data provider."""
    name: str
    priority: int = 0
    state: BreakerState = BreakerState.CLOSED
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_requests: int = 0
    total_failures: int = 0
    last_failure_at: datetime | None = None
    last_success_at: datetime | None = None
    opened_at: datetime | None = None
    error_rate: float = 0.0
    is_available: bool = True


class FailoverResult(BaseModel):
    """Result of a failover chain execution."""
    selected_provider: str = ""
    attempted_providers: list[str] = Field(default_factory=list)
    success: bool = False
    fallback_used: bool = False


# ── Engine ───────────────────────────────────────────────────────────────────

class CircuitBreakerManager:
    """
    Manages circuit breakers for multiple data providers.

    Features:
      - Per-provider circuit breakers with configurable thresholds
      - Priority-based failover chain
      - Automatic recovery (half-open → closed on success)
      - Health metrics and error rate tracking
    """

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self.config = config or CircuitBreakerConfig()
        self._providers: dict[str, ProviderHealth] = {}

    def register(self, name: str, priority: int = 0) -> ProviderHealth:
        """Register a data provider."""
        health = ProviderHealth(name=name, priority=priority)
        self._providers[name] = health
        logger.info("CIRCUIT-BREAKER: Registered provider '%s' (priority=%d)", name, priority)
        return health

    def record_success(self, name: str) -> BreakerState:
        """Record a successful request."""
        if name not in self._providers:
            return BreakerState.CLOSED

        p = self._providers[name]
        p.total_requests += 1
        p.consecutive_failures = 0
        p.consecutive_successes += 1
        p.last_success_at = datetime.now(timezone.utc)

        # Half-open → closed after enough successes
        if p.state == BreakerState.HALF_OPEN:
            if p.consecutive_successes >= self.config.success_threshold:
                p.state = BreakerState.CLOSED
                p.opened_at = None
                logger.info("CIRCUIT-BREAKER: '%s' recovered → CLOSED", name)

        p.error_rate = p.total_failures / max(p.total_requests, 1)
        p.is_available = p.state != BreakerState.OPEN
        return p.state

    def record_failure(self, name: str) -> BreakerState:
        """Record a failed request."""
        if name not in self._providers:
            return BreakerState.OPEN

        p = self._providers[name]
        p.total_requests += 1
        p.total_failures += 1
        p.consecutive_failures += 1
        p.consecutive_successes = 0
        p.last_failure_at = datetime.now(timezone.utc)

        # Check if should open
        if p.consecutive_failures >= self.config.failure_threshold:
            if p.state != BreakerState.OPEN:
                p.state = BreakerState.OPEN
                p.opened_at = datetime.now(timezone.utc)
                logger.warning(
                    "CIRCUIT-BREAKER: '%s' OPENED after %d failures",
                    name, p.consecutive_failures,
                )

        p.error_rate = p.total_failures / max(p.total_requests, 1)
        p.is_available = p.state != BreakerState.OPEN
        return p.state

    def get_available(self) -> str | None:
        """Get highest-priority available provider."""
        self._check_half_open()

        available = [
            p for p in self._providers.values()
            if p.state != BreakerState.OPEN
        ]

        if not available:
            # All open — try half-open on highest priority
            all_providers = sorted(self._providers.values(), key=lambda p: p.priority)
            if all_providers:
                p = all_providers[0]
                p.state = BreakerState.HALF_OPEN
                return p.name
            return None

        # Sort by priority (lower = higher priority)
        available.sort(key=lambda p: p.priority)
        return available[0].name

    def get_failover_chain(self) -> list[str]:
        """Get ordered list of available providers for failover."""
        self._check_half_open()

        providers = sorted(self._providers.values(), key=lambda p: p.priority)
        return [p.name for p in providers if p.state != BreakerState.OPEN]

    def get_health(self, name: str | None = None) -> list[ProviderHealth]:
        """Get health status of providers."""
        if name:
            p = self._providers.get(name)
            return [p] if p else []
        return list(self._providers.values())

    def execute_with_failover(
        self,
        fn: callable,
        *args,
        **kwargs,
    ) -> FailoverResult:
        """
        Execute a function with automatic failover.

        Tries each available provider in priority order until one succeeds.

        Parameters
        ----------
        fn : callable
            Function(provider_name, *args, **kwargs) -> result.
            Should raise Exception on failure.
        """
        chain = self.get_failover_chain()

        if not chain:
            # Force half-open on best provider
            best = self.get_available()
            if best:
                chain = [best]

        attempted: list[str] = []

        for provider in chain:
            attempted.append(provider)
            try:
                fn(provider, *args, **kwargs)
                self.record_success(provider)
                return FailoverResult(
                    selected_provider=provider,
                    attempted_providers=attempted,
                    success=True,
                    fallback_used=len(attempted) > 1,
                )
            except Exception as e:
                self.record_failure(provider)
                logger.warning(
                    "CIRCUIT-BREAKER: '%s' failed: %s, trying next",
                    provider, e,
                )

        return FailoverResult(
            attempted_providers=attempted,
            success=False,
        )

    def _check_half_open(self) -> None:
        """Move OPEN providers to HALF_OPEN if cooldown elapsed."""
        now = datetime.now(timezone.utc)
        for p in self._providers.values():
            if p.state == BreakerState.OPEN and p.opened_at:
                elapsed = (now - p.opened_at).total_seconds()
                if elapsed >= self.config.cooldown_seconds:
                    p.state = BreakerState.HALF_OPEN
                    p.consecutive_successes = 0
                    logger.info(
                        "CIRCUIT-BREAKER: '%s' cooldown elapsed → HALF_OPEN",
                        p.name,
                    )

    @property
    def provider_count(self) -> int:
        return len(self._providers)
