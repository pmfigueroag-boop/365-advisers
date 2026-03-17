"""
src/engines/backtesting/kill_switch.py
--------------------------------------------------------------------------
Signal Kill Switch — automatically deactivates signals when live
performance degrades below thresholds.

Monitors:
  - Rolling IC (information coefficient)
  - Cumulative excess return
  - Drawdown depth
  - Consecutive losing periods

When thresholds are breached, the signal is:
  1. FLAGGED (warning, still active)
  2. THROTTLED (reduced weight)
  3. KILLED (fully deactivated)

Integration with AuditTrail: every state transition is logged.

Usage::

    ks = KillSwitch()
    status = ks.evaluate("sig.momentum", live_metrics)
    if status.action == "KILL":
        # deactivate signal in production
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.backtesting.kill_switch")


# ── Contracts ────────────────────────────────────────────────────────────────

class SignalHealth(str, Enum):
    HEALTHY = "healthy"
    FLAGGED = "flagged"
    THROTTLED = "throttled"
    KILLED = "killed"


class KillSwitchConfig(BaseModel):
    """Thresholds for the kill switch."""
    # IC thresholds
    min_rolling_ic: float = Field(
        0.02, description="IC below this → FLAG",
    )
    kill_ic: float = Field(
        -0.01, description="IC below this → KILL",
    )

    # Return thresholds
    max_cumulative_loss: float = Field(
        -0.10, description="Cumulative excess return below this → KILL",
    )
    max_drawdown: float = Field(
        -0.15, description="Drawdown below this → KILL",
    )

    # Consistency
    max_consecutive_losses: int = Field(
        5, description="N consecutive losing periods → THROTTLE",
    )
    kill_consecutive_losses: int = Field(
        8, description="N consecutive losing periods → KILL",
    )

    # Throttle
    throttle_weight_multiplier: float = Field(
        0.5, ge=0.0, le=1.0,
        description="Weight multiplier when throttled",
    )

    # Cooldown
    cooldown_periods: int = Field(
        20, description="Periods to wait after KILL before re-evaluation",
    )


class LiveMetrics(BaseModel):
    """Live performance metrics for a signal."""
    signal_id: str
    rolling_ic: float = 0.0
    cumulative_excess_return: float = 0.0
    current_drawdown: float = 0.0
    consecutive_losses: int = 0
    periods_since_activation: int = 0
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class KillSwitchDecision(BaseModel):
    """Decision from the kill switch evaluation."""
    signal_id: str
    previous_health: SignalHealth = SignalHealth.HEALTHY
    current_health: SignalHealth = SignalHealth.HEALTHY
    action: str = ""  # "NONE", "FLAG", "THROTTLE", "KILL", "RESTORE"
    reason: str = ""
    weight_multiplier: float = 1.0
    triggers: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Engine ───────────────────────────────────────────────────────────────────

class KillSwitch:
    """
    Automated signal deactivation based on live performance.

    State machine: HEALTHY → FLAGGED → THROTTLED → KILLED

    Each evaluation computes the worst applicable state and transitions
    accordingly. State can also improve if metrics recover.
    """

    def __init__(self, config: KillSwitchConfig | None = None) -> None:
        self.config = config or KillSwitchConfig()
        self._states: dict[str, SignalHealth] = {}
        self._kill_history: list[KillSwitchDecision] = []

    def evaluate(self, metrics: LiveMetrics) -> KillSwitchDecision:
        """
        Evaluate signal health and decide action.

        Parameters
        ----------
        metrics : LiveMetrics
            Current live performance metrics.

        Returns
        -------
        KillSwitchDecision
            Action to take (NONE, FLAG, THROTTLE, KILL).
        """
        sig = metrics.signal_id
        prev_health = self._states.get(sig, SignalHealth.HEALTHY)
        triggers: list[str] = []

        # Evaluate each criterion
        target_health = SignalHealth.HEALTHY

        # IC check
        if metrics.rolling_ic < self.config.kill_ic:
            target_health = SignalHealth.KILLED
            triggers.append(f"IC={metrics.rolling_ic:.4f} < kill_threshold={self.config.kill_ic}")
        elif metrics.rolling_ic < self.config.min_rolling_ic:
            target_health = max(target_health, SignalHealth.FLAGGED, key=self._severity)
            triggers.append(f"IC={metrics.rolling_ic:.4f} < min={self.config.min_rolling_ic}")

        # Cumulative loss
        if metrics.cumulative_excess_return < self.config.max_cumulative_loss:
            target_health = max(target_health, SignalHealth.KILLED, key=self._severity)
            triggers.append(
                f"Cum.excess={metrics.cumulative_excess_return:.4f} < "
                f"max_loss={self.config.max_cumulative_loss}"
            )

        # Drawdown
        if metrics.current_drawdown < self.config.max_drawdown:
            target_health = max(target_health, SignalHealth.KILLED, key=self._severity)
            triggers.append(
                f"DD={metrics.current_drawdown:.4f} < max={self.config.max_drawdown}"
            )

        # Consecutive losses
        if metrics.consecutive_losses >= self.config.kill_consecutive_losses:
            target_health = max(target_health, SignalHealth.KILLED, key=self._severity)
            triggers.append(
                f"ConsecLosses={metrics.consecutive_losses} >= "
                f"kill={self.config.kill_consecutive_losses}"
            )
        elif metrics.consecutive_losses >= self.config.max_consecutive_losses:
            target_health = max(target_health, SignalHealth.THROTTLED, key=self._severity)
            triggers.append(
                f"ConsecLosses={metrics.consecutive_losses} >= "
                f"throttle={self.config.max_consecutive_losses}"
            )

        # Determine action
        action = "NONE"
        weight_mult = 1.0

        if target_health == SignalHealth.KILLED:
            action = "KILL"
            weight_mult = 0.0
        elif target_health == SignalHealth.THROTTLED:
            action = "THROTTLE"
            weight_mult = self.config.throttle_weight_multiplier
        elif target_health == SignalHealth.FLAGGED:
            action = "FLAG"
            weight_mult = 1.0
        elif prev_health != SignalHealth.HEALTHY:
            action = "RESTORE"
            weight_mult = 1.0

        reason = "; ".join(triggers) if triggers else "All metrics within tolerance"

        decision = KillSwitchDecision(
            signal_id=sig,
            previous_health=prev_health,
            current_health=target_health,
            action=action,
            reason=reason,
            weight_multiplier=weight_mult,
            triggers=triggers,
        )

        self._states[sig] = target_health
        self._kill_history.append(decision)

        logger.info(
            "KILL-SWITCH: %s: %s → %s (action=%s, weight=%.2f) — %s",
            sig, prev_health.value, target_health.value,
            action, weight_mult, reason[:80],
        )

        return decision

    def get_health(self, signal_id: str) -> SignalHealth:
        """Get current health of a signal."""
        return self._states.get(signal_id, SignalHealth.HEALTHY)

    def get_active_kills(self) -> list[str]:
        """Get all currently killed signals."""
        return [s for s, h in self._states.items() if h == SignalHealth.KILLED]

    def get_history(self, signal_id: str | None = None) -> list[KillSwitchDecision]:
        """Get decision history."""
        if signal_id:
            return [d for d in self._kill_history if d.signal_id == signal_id]
        return list(self._kill_history)

    def reset(self, signal_id: str) -> None:
        """Manually reset a signal to healthy."""
        self._states[signal_id] = SignalHealth.HEALTHY
        logger.info("KILL-SWITCH: Manually reset %s to HEALTHY", signal_id)

    @staticmethod
    def _severity(health: SignalHealth) -> int:
        """Severity ordering for max()."""
        return {
            SignalHealth.HEALTHY: 0,
            SignalHealth.FLAGGED: 1,
            SignalHealth.THROTTLED: 2,
            SignalHealth.KILLED: 3,
        }[health]
