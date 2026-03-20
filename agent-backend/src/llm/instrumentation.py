"""
src/llm/instrumentation.py
─────────────────────────────────────────────────────────────────────────────
Thread-safe structured logging and in-memory metrics for LLM invocations.

Records every invocation with provider, model, latency, task type,
fallback status, and token usage. Exposes aggregated metrics for
monitoring endpoints.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any

from src.llm.types import LLMInvocationResult, LLMMetrics

logger = logging.getLogger("365advisers.llm.instrumentation")


class LLMInstruments:
    """Thread-safe in-memory LLM usage tracker."""

    def __init__(self):
        self._lock = threading.Lock()
        self._total = 0
        self._successful = 0
        self._failed = 0
        self._fallback_used = 0
        self._total_latency_ms = 0.0
        self._total_tokens = 0
        self._by_task: dict[str, int] = defaultdict(int)
        self._by_provider: dict[str, int] = defaultdict(int)
        self._recent_errors: list[dict[str, Any]] = []
        self._max_errors = 50

    def record(self, result: LLMInvocationResult) -> None:
        """Record an invocation result (thread-safe)."""
        with self._lock:
            self._total += 1
            self._by_task[result.task_type.value] += 1

            if result.success:
                self._successful += 1
                self._by_provider[result.provider.value] += 1
                self._total_latency_ms += result.latency_ms
                if result.tokens_used:
                    self._total_tokens += result.tokens_used
            else:
                self._failed += 1
                self._recent_errors.append({
                    "task_type": result.task_type.value,
                    "provider": result.provider.value,
                    "model": result.model,
                    "error": result.error,
                    "error_type": result.error_type,
                    "fallback_used": result.fallback_used,
                    "timestamp": result.timestamp.isoformat(),
                })
                if len(self._recent_errors) > self._max_errors:
                    self._recent_errors = self._recent_errors[-self._max_errors:]

            if result.fallback_used:
                self._fallback_used += 1

        # Structured log (outside lock — logging has its own thread safety)
        logger.info(
            "LLM invocation: task=%s provider=%s model=%s latency=%.0fms "
            "success=%s fallback=%s tokens=%s",
            result.task_type.value,
            result.provider.value,
            result.model,
            result.latency_ms,
            result.success,
            result.fallback_used,
            result.tokens_used or "N/A",
        )

    def get_metrics(self) -> LLMMetrics:
        """Return aggregated metrics (thread-safe snapshot)."""
        with self._lock:
            avg = (
                self._total_latency_ms / self._successful
                if self._successful > 0 else 0.0
            )
            return LLMMetrics(
                total_invocations=self._total,
                successful=self._successful,
                failed=self._failed,
                fallback_used=self._fallback_used,
                avg_latency_ms=round(avg, 1),
                total_tokens=self._total_tokens,
                by_task_type=dict(self._by_task),
                by_provider=dict(self._by_provider),
                errors=list(self._recent_errors[-10:]),
            )

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        with self._lock:
            self._total = 0
            self._successful = 0
            self._failed = 0
            self._fallback_used = 0
            self._total_latency_ms = 0.0
            self._total_tokens = 0
            self._by_task = defaultdict(int)
            self._by_provider = defaultdict(int)
            self._recent_errors = []


# Singleton
_instruments = LLMInstruments()


def get_instruments() -> LLMInstruments:
    return _instruments
