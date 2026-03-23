"""
src/orchestration/sla_monitor.py
──────────────────────────────────────────────────────────────────────────────
Pipeline SLA Observability.

Tracks per-analysis execution time, per-layer breakdown, and SLA
compliance metrics.  Thread-safe via a simple ring buffer.

Usage::

    from src.orchestration.sla_monitor import sla_monitor

    # In the pipeline:
    sla_monitor.start(analysis_id, ticker)
    sla_monitor.mark_layer(analysis_id, "fundamental")
    sla_monitor.mark_layer(analysis_id, "technical")
    ...
    sla_monitor.finish(analysis_id)   # logs WARNING if > SLA_TARGET_MS

    # API:
    stats = sla_monitor.get_stats()
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger("365advisers.orchestration.sla")

# ── Configuration ────────────────────────────────────────────────────────────

SLA_TARGET_MS = 90_000       # 90 seconds — FR-1.1.4
SLA_WARNING_MS = 75_000      # warn early at 75s so operators can watch
RING_BUFFER_SIZE = 500       # keep last 500 analyses


@dataclass
class AnalysisTrace:
    """Timing trace for a single pipeline execution."""
    analysis_id: str
    ticker: str
    start_ns: int = 0
    end_ns: int = 0
    from_cache: bool = False
    layers: dict[str, float] = field(default_factory=dict)  # layer → ms
    total_ms: float = 0.0
    sla_met: bool = True

    def elapsed_ms(self) -> float:
        if self.end_ns and self.start_ns:
            return (self.end_ns - self.start_ns) / 1e6
        if self.start_ns:
            return (time.monotonic_ns() - self.start_ns) / 1e6
        return 0.0


class SLAMonitor:
    """
    Ring-buffer based SLA monitor for the analysis pipeline.

    Stores traces for the last N analyses and computes aggregate metrics
    (P50, P90, P99, compliance rate).
    """

    def __init__(self, buffer_size: int = RING_BUFFER_SIZE):
        self._active: dict[str, AnalysisTrace] = {}
        self._history: deque[AnalysisTrace] = deque(maxlen=buffer_size)
        self._lock = Lock()
        self._total_started = 0
        self._total_completed = 0
        self._total_breaches = 0

    # ── Pipeline integration points ──────────────────────────────────────

    def start(self, analysis_id: str, ticker: str) -> None:
        """Called at the start of run_combined_stream."""
        trace = AnalysisTrace(
            analysis_id=analysis_id,
            ticker=ticker,
            start_ns=time.monotonic_ns(),
        )
        with self._lock:
            self._active[analysis_id] = trace
            self._total_started += 1

    def mark_layer(self, analysis_id: str, layer_name: str) -> None:
        """Record the completion timestamp of a pipeline layer."""
        with self._lock:
            trace = self._active.get(analysis_id)
        if not trace:
            return
        elapsed = (time.monotonic_ns() - trace.start_ns) / 1e6
        trace.layers[layer_name] = round(elapsed, 1)

        # Early warning
        if elapsed > SLA_WARNING_MS and layer_name != "done":
            logger.warning(
                "SLA WARNING: %s [%s] at layer '%s' — %.0fms (%.0f%% of 90s budget)",
                trace.ticker, analysis_id[:8], layer_name,
                elapsed, elapsed / SLA_TARGET_MS * 100,
            )

    def finish(self, analysis_id: str, from_cache: bool = False) -> AnalysisTrace | None:
        """Called at the end — computes total and checks SLA."""
        with self._lock:
            trace = self._active.pop(analysis_id, None)
        if not trace:
            return None

        trace.end_ns = time.monotonic_ns()
        trace.from_cache = from_cache
        trace.total_ms = round(trace.elapsed_ms(), 1)
        trace.sla_met = trace.total_ms <= SLA_TARGET_MS

        with self._lock:
            self._history.append(trace)
            self._total_completed += 1
            if not trace.sla_met:
                self._total_breaches += 1

        # Log
        if trace.sla_met:
            logger.info(
                "SLA OK: %s [%s] completed in %.1fs (%s)",
                trace.ticker, analysis_id[:8], trace.total_ms / 1000,
                "cache" if from_cache else "cold",
            )
        else:
            layer_breakdown = " | ".join(
                f"{k}={v:.0f}ms" for k, v in trace.layers.items()
            )
            logger.warning(
                "SLA BREACH: %s [%s] took %.1fs (limit: %.0fs) — %s",
                trace.ticker, analysis_id[:8],
                trace.total_ms / 1000, SLA_TARGET_MS / 1000,
                layer_breakdown,
            )

        return trace

    # ── Statistics ────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return aggregate SLA statistics for the API."""
        with self._lock:
            traces = list(self._history)
            total_started = self._total_started
            total_completed = self._total_completed
            total_breaches = self._total_breaches

        if not traces:
            return {
                "sla_target_ms": SLA_TARGET_MS,
                "total_analyses": 0,
                "compliance_pct": 100.0,
                "breaches": 0,
                "percentiles": {},
                "recent": [],
            }

        durations = sorted(t.total_ms for t in traces)
        n = len(durations)

        def percentile(p: float) -> float:
            idx = int(p / 100 * (n - 1))
            return round(durations[min(idx, n - 1)], 1)

        cold_traces = [t for t in traces if not t.from_cache]
        cache_traces = [t for t in traces if t.from_cache]

        compliance = (
            (total_completed - total_breaches) / total_completed * 100
            if total_completed > 0 else 100.0
        )

        # Last 5 analyses for quick inspection
        recent = [
            {
                "analysis_id": t.analysis_id[:8],
                "ticker": t.ticker,
                "total_ms": t.total_ms,
                "sla_met": t.sla_met,
                "from_cache": t.from_cache,
                "layers": t.layers,
            }
            for t in list(self._history)[-5:]
        ]

        return {
            "sla_target_ms": SLA_TARGET_MS,
            "total_analyses": total_completed,
            "total_started": total_started,
            "compliance_pct": round(compliance, 1),
            "breaches": total_breaches,
            "percentiles": {
                "p50_ms": percentile(50),
                "p90_ms": percentile(90),
                "p95_ms": percentile(95),
                "p99_ms": percentile(99),
            },
            "cold_start": {
                "count": len(cold_traces),
                "avg_ms": round(sum(t.total_ms for t in cold_traces) / len(cold_traces), 1) if cold_traces else 0,
            },
            "cache_hit": {
                "count": len(cache_traces),
                "avg_ms": round(sum(t.total_ms for t in cache_traces) / len(cache_traces), 1) if cache_traces else 0,
            },
            "recent": recent,
        }


# ── Singleton ────────────────────────────────────────────────────────────────

sla_monitor = SLAMonitor()
