"""
src/engines/monitoring/health.py
─────────────────────────────────────────────────────────────────────────────
Signal Health Score & Circuit Breaker — Enhances the existing monitoring
infrastructure with:

  1. **Health Score**: Composite 0-100 score per signal combining:
     - Stability (40%): Rolling hit-rate consistency
     - Drift (30%): Inverse of concept drift severity
     - Performance (30%): Recent forward return quality

  2. **Circuit Breaker**: Auto-disables signals that fail the health
     threshold for N consecutive evaluation windows.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from src.data.database import SessionLocal

logger = logging.getLogger("365advisers.monitoring.health")


# ─── Models ──────────────────────────────────────────────────────────────────

class SignalHealthScore(BaseModel):
    """Health score for a single signal."""
    signal_id: str
    health_score: float = 50.0          # 0-100
    stability_score: float = 50.0       # 0-100
    drift_score: float = 100.0          # 0-100 (100 = no drift)
    performance_score: float = 50.0     # 0-100
    consecutive_failures: int = 0
    is_disabled: bool = False
    disabled_reason: str = ""
    last_evaluated: datetime | None = None


class CircuitBreakerConfig(BaseModel):
    """Configuration for the auto-disable circuit breaker."""
    health_threshold: float = 30.0         # Score below which counts as failure
    consecutive_failures_limit: int = 3    # Failures before auto-disable
    auto_reenable_after_days: int = 30     # Days before re-evaluation
    stability_weight: float = 0.4
    drift_weight: float = 0.3
    performance_weight: float = 0.3


class MonitoringSweepResult(BaseModel):
    """Result of a full monitoring sweep."""
    signals_evaluated: int = 0
    signals_healthy: int = 0
    signals_warning: int = 0
    signals_critical: int = 0
    signals_auto_disabled: int = 0
    signal_scores: list[SignalHealthScore] = Field(default_factory=list)
    sweep_timestamp: datetime | None = None


# ─── Signal Health Calculator ─────────────────────────────────────────────────

class SignalHealthCalculator:
    """Computes composite health scores for signals."""

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self.config = config or CircuitBreakerConfig()

    def compute_health(
        self,
        signal_id: str,
        stability: float,
        drift_severity: float,
        recent_hit_rate: float,
        recent_avg_return: float,
    ) -> SignalHealthScore:
        """Compute health score from component metrics.

        Args:
            signal_id: Signal identifier.
            stability: Rolling hit-rate consistency [0, 1].
            drift_severity: Concept drift severity [0, 1] (0=no drift).
            recent_hit_rate: Recent hit rate [0, 1].
            recent_avg_return: Recent average forward return.

        Returns:
            SignalHealthScore with composite and component scores.
        """
        # Normalize components to 0-100
        stability_score = stability * 100
        drift_score = (1.0 - drift_severity) * 100   # Invert: less drift = higher score
        performance_score = self._performance_to_score(recent_hit_rate, recent_avg_return)

        # Weighted composite
        health = (
            self.config.stability_weight * stability_score
            + self.config.drift_weight * drift_score
            + self.config.performance_weight * performance_score
        )

        return SignalHealthScore(
            signal_id=signal_id,
            health_score=round(max(0, min(100, health)), 2),
            stability_score=round(stability_score, 2),
            drift_score=round(drift_score, 2),
            performance_score=round(performance_score, 2),
            last_evaluated=datetime.now(timezone.utc),
        )

    @staticmethod
    def _performance_to_score(hit_rate: float, avg_return: float) -> float:
        """Convert performance metrics to a 0-100 score.

        - Hit rate of 50% = score 50 (break-even)
        - Hit rate of 60% = score ~70
        - Hit rate of 70%+ = score ~90+
        - Positive avg return gives bonus
        """
        base = hit_rate * 100

        # Positive return bonus: up to +20 points
        return_bonus = min(20, max(-20, avg_return * 1000))

        return max(0, min(100, base + return_bonus))


# ─── Circuit Breaker ─────────────────────────────────────────────────────────

class CircuitBreaker:
    """Auto-disables signals that consistently fail health thresholds.

    When a signal's health score drops below the threshold for
    `consecutive_failures_limit` consecutive evaluations, the circuit
    breaker disables it by recording a disable event in the governance
    audit trail.
    """

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self.config = config or CircuitBreakerConfig()
        self._failure_counts: dict[str, int] = {}
        self._disabled: dict[str, dict] = {}

    def evaluate(self, score: SignalHealthScore) -> SignalHealthScore:
        """Evaluate a signal health score and apply circuit breaker logic.

        Returns updated health score with disable status.
        """
        signal_id = score.signal_id
        threshold = self.config.health_threshold
        limit = self.config.consecutive_failures_limit

        if score.health_score < threshold:
            self._failure_counts[signal_id] = self._failure_counts.get(signal_id, 0) + 1
        else:
            # Reset failure count on healthy evaluation
            self._failure_counts[signal_id] = 0
            # Re-enable if previously disabled
            if signal_id in self._disabled:
                del self._disabled[signal_id]
                logger.info("CIRCUIT-BREAKER: Signal %s re-enabled (health=%.1f)", signal_id, score.health_score)

        consecutive = self._failure_counts.get(signal_id, 0)
        score.consecutive_failures = consecutive

        # Check if should auto-disable
        if consecutive >= limit and signal_id not in self._disabled:
            score.is_disabled = True
            score.disabled_reason = (
                f"Health score {score.health_score:.1f} below threshold {threshold:.0f} "
                f"for {consecutive} consecutive evaluations"
            )
            self._disabled[signal_id] = {
                "disabled_at": datetime.now(timezone.utc).isoformat(),
                "reason": score.disabled_reason,
                "health_at_disable": score.health_score,
            }
            logger.warning(
                "CIRCUIT-BREAKER: Auto-disabled signal %s (health=%.1f, failures=%d)",
                signal_id, score.health_score, consecutive,
            )
        elif signal_id in self._disabled:
            score.is_disabled = True
            score.disabled_reason = self._disabled[signal_id].get("reason", "previously disabled")

        return score

    def get_disabled_signals(self) -> dict[str, dict]:
        """Return all currently disabled signals with metadata."""
        return dict(self._disabled)

    def force_enable(self, signal_id: str) -> bool:
        """Manually re-enable a disabled signal."""
        if signal_id in self._disabled:
            del self._disabled[signal_id]
            self._failure_counts[signal_id] = 0
            logger.info("CIRCUIT-BREAKER: Signal %s manually re-enabled", signal_id)
            return True
        return False

    def force_disable(self, signal_id: str, reason: str = "manual") -> None:
        """Manually disable a signal."""
        self._disabled[signal_id] = {
            "disabled_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }
        logger.info("CIRCUIT-BREAKER: Signal %s manually disabled", signal_id)


# ─── Monitoring Sweep Orchestrator ────────────────────────────────────────────

class MonitoringSweepEngine:
    """Orchestrates a full monitoring sweep across all signals.

    Combines:
    - Signal performance data (from scorecard)
    - Concept drift data (from drift engine)
    - Health score calculation
    - Circuit breaker evaluation
    """

    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self.config = config or CircuitBreakerConfig()
        self._health_calc = SignalHealthCalculator(self.config)
        self._circuit_breaker = CircuitBreaker(self.config)

    def run_sweep(
        self,
        signal_metrics: list[dict[str, Any]],
        drift_data: dict[str, float] | None = None,
    ) -> MonitoringSweepResult:
        """Run a full monitoring sweep.

        Args:
            signal_metrics: List of dicts with keys:
                signal_id, hit_rate, signal_stability, avg_return
            drift_data: {signal_id: drift_severity (0-1)}

        Returns:
            MonitoringSweepResult with per-signal health scores.
        """
        drift = drift_data or {}
        scores: list[SignalHealthScore] = []

        for metrics in signal_metrics:
            signal_id = metrics.get("signal_id", "unknown")

            health = self._health_calc.compute_health(
                signal_id=signal_id,
                stability=metrics.get("signal_stability", 0.5),
                drift_severity=drift.get(signal_id, 0.0),
                recent_hit_rate=metrics.get("hit_rate", 0.5),
                recent_avg_return=metrics.get("avg_return", 0.0),
            )

            # Apply circuit breaker
            health = self._circuit_breaker.evaluate(health)
            scores.append(health)

        # Categorize
        healthy = sum(1 for s in scores if s.health_score >= 70)
        warning = sum(1 for s in scores if 30 <= s.health_score < 70)
        critical = sum(1 for s in scores if s.health_score < 30)
        disabled = sum(1 for s in scores if s.is_disabled)

        result = MonitoringSweepResult(
            signals_evaluated=len(scores),
            signals_healthy=healthy,
            signals_warning=warning,
            signals_critical=critical,
            signals_auto_disabled=disabled,
            signal_scores=scores,
            sweep_timestamp=datetime.now(timezone.utc),
        )

        logger.info(
            "MONITORING SWEEP: %d signals — %d healthy, %d warning, %d critical, %d disabled",
            len(scores), healthy, warning, critical, disabled,
        )
        return result

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._circuit_breaker
