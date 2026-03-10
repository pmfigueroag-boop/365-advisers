"""
src/engines/idea_generation/metrics.py
──────────────────────────────────────────────────────────────────────────────
Observability adapter for the Idea Generation Engine.

Provides a vendor-agnostic metrics interface that can be backed by:
  - ``NoOpCollector``  — zero-cost default for when no backend is configured
  - ``InMemoryCollector`` — deterministic collector for tests
  - Future: Prometheus, OpenTelemetry, StatsD, etc.

Usage::

    from src.engines.idea_generation.metrics import get_collector

    m = get_collector()
    m.increment("ideas_generated_total", tags={"detector": "value"})
    m.timing("chunk_processing_ms", 142.3, tags={"mode": "distributed"})

Design principles:
  - Low-cardinality labels only (detector, idea_type, mode, error_type).
  - Never use ticker or user_id as a metric label.
  - Tags are flat str→str dicts for portability.
"""

from __future__ import annotations

import logging
import threading
from typing import Protocol

logger = logging.getLogger("365advisers.idea_generation.metrics")


# ── Protocol ──────────────────────────────────────────────────────────────────

class MetricsCollector(Protocol):
    """Minimal metrics interface — increment counters, record timings."""

    def increment(
        self, name: str, value: int = 1, tags: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter metric."""
        ...

    def timing(
        self, name: str, ms: float, tags: dict[str, str] | None = None,
    ) -> None:
        """Record a timing/duration metric in milliseconds."""
        ...

    def gauge(
        self, name: str, value: float, tags: dict[str, str] | None = None,
    ) -> None:
        """Set a gauge metric to an absolute value."""
        ...


# ── NoOpCollector ─────────────────────────────────────────────────────────────

class NoOpCollector:
    """Zero-cost collector that discards all metrics.

    Used as the default when no observability backend is configured.
    """

    def increment(
        self, name: str, value: int = 1, tags: dict[str, str] | None = None,
    ) -> None:
        pass

    def timing(
        self, name: str, ms: float, tags: dict[str, str] | None = None,
    ) -> None:
        pass

    def gauge(
        self, name: str, value: float, tags: dict[str, str] | None = None,
    ) -> None:
        pass


# ── InMemoryCollector ─────────────────────────────────────────────────────────

class InMemoryCollector:
    """Collects metrics in memory for deterministic testing.

    Thread-safe.  Metrics are stored as ``(name, tags_tuple)`` → value.

    Usage::

        collector = InMemoryCollector()
        set_collector(collector)
        # ... run code ...
        assert collector.get("ideas_generated_total", detector="value") == 3
    """

    def __init__(self) -> None:
        self._counters: dict[tuple[str, tuple], int] = {}
        self._timings: dict[tuple[str, tuple], list[float]] = {}
        self._gauges: dict[tuple[str, tuple], float] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _tags_key(tags: dict[str, str] | None) -> tuple:
        if not tags:
            return ()
        return tuple(sorted(tags.items()))

    def increment(
        self, name: str, value: int = 1, tags: dict[str, str] | None = None,
    ) -> None:
        key = (name, self._tags_key(tags))
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + value

    def timing(
        self, name: str, ms: float, tags: dict[str, str] | None = None,
    ) -> None:
        key = (name, self._tags_key(tags))
        with self._lock:
            self._timings.setdefault(key, []).append(ms)

    def gauge(
        self, name: str, value: float, tags: dict[str, str] | None = None,
    ) -> None:
        key = (name, self._tags_key(tags))
        with self._lock:
            self._gauges[key] = value

    # ── Query helpers for tests ───────────────────────────────────────

    def get(self, name: str, **tags: str) -> int:
        """Get counter value.  ``collector.get("x", detector="value")``."""
        key = (name, self._tags_key(tags or None))
        return self._counters.get(key, 0)

    def get_timing(self, name: str, **tags: str) -> list[float]:
        """Get recorded timings as a list."""
        key = (name, self._tags_key(tags or None))
        return list(self._timings.get(key, []))

    def get_gauge(self, name: str, **tags: str) -> float | None:
        key = (name, self._tags_key(tags or None))
        return self._gauges.get(key)

    def total(self, name: str) -> int:
        """Sum across all tag combinations for a given metric name."""
        return sum(v for (n, _), v in self._counters.items() if n == name)

    def reset(self) -> None:
        """Clear all collected metrics."""
        with self._lock:
            self._counters.clear()
            self._timings.clear()
            self._gauges.clear()


# ── Module-level singleton ────────────────────────────────────────────────────

_collector: MetricsCollector = NoOpCollector()
_lock = threading.Lock()


def get_collector() -> MetricsCollector:
    """Return the active metrics collector."""
    return _collector


def set_collector(collector: MetricsCollector) -> None:
    """Replace the active metrics collector (e.g. at app startup or in tests)."""
    global _collector
    with _lock:
        _collector = collector
    logger.info(
        "metrics_collector_set",
        extra={"collector_type": type(collector).__name__},
    )
