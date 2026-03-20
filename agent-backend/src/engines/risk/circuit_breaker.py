"""
src/engines/risk/circuit_breaker.py
──────────────────────────────────────────────────────────────────────────────
P3.4: Drawdown Circuit Breaker

Monitors portfolio equity curve and triggers a "go flat" state when
cumulative drawdown exceeds a configurable threshold (-10% default).

Once triggered, no new BUY signals are allowed until the portfolio
recovers to within a configurable recovery threshold (-5% default).

Usage:
    breaker = DrawdownCircuitBreaker(max_drawdown_pct=0.10)
    breaker.update(daily_return=0.02)
    if breaker.is_triggered:
        # Suppress new buy signals
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("365advisers.risk.circuit_breaker")


@dataclass
class CircuitBreakerState:
    """Current state of the circuit breaker."""
    is_triggered: bool = False
    current_drawdown: float = 0.0
    peak_equity: float = 1.0
    current_equity: float = 1.0
    trigger_count: int = 0
    last_trigger_at: str | None = None
    recovery_pct: float = 0.0  # how far recovered from max drawdown


class DrawdownCircuitBreaker:
    """
    P3.4: Portfolio-level drawdown circuit breaker.

    - Monitors equity curve via update(daily_return)
    - Triggers when drawdown exceeds max_drawdown_pct
    - Recovers when drawdown recovers to within recovery_threshold_pct
    - Tracks trigger history for reporting
    """

    def __init__(
        self,
        max_drawdown_pct: float = 0.10,      # -10% drawdown triggers
        recovery_threshold_pct: float = 0.05,  # recover to -5% to re-enable
    ):
        self.max_drawdown_pct = max_drawdown_pct
        self.recovery_threshold_pct = recovery_threshold_pct
        self._peak = 1.0
        self._equity = 1.0
        self._triggered = False
        self._trigger_count = 0
        self._last_trigger_at: str | None = None
        self._trigger_history: list[dict] = []

    @property
    def is_triggered(self) -> bool:
        """True if circuit breaker is currently active (no new buys)."""
        return self._triggered

    @property
    def current_drawdown(self) -> float:
        """Current drawdown as a positive decimal (e.g. 0.08 = 8% drawdown)."""
        if self._peak <= 0:
            return 0.0
        return max(0.0, (self._peak - self._equity) / self._peak)

    def update(self, daily_return: float, date_str: str = "") -> bool:
        """
        Update the equity curve with a new daily return.

        Returns True if the circuit breaker state CHANGED (triggered or recovered).
        """
        self._equity *= (1 + daily_return)
        if self._equity > self._peak:
            self._peak = self._equity

        dd = self.current_drawdown
        state_changed = False

        if not self._triggered and dd >= self.max_drawdown_pct:
            # Trigger circuit breaker
            self._triggered = True
            self._trigger_count += 1
            self._last_trigger_at = date_str or datetime.now(timezone.utc).isoformat()
            self._trigger_history.append({
                "trigger_date": self._last_trigger_at,
                "drawdown": round(dd, 4),
                "equity": round(self._equity, 6),
            })
            logger.warning(
                f"CIRCUIT BREAKER TRIGGERED: drawdown={dd:.1%} > "
                f"threshold={self.max_drawdown_pct:.1%} — NEW BUYS SUPPRESSED"
            )
            state_changed = True

        elif self._triggered and dd <= self.recovery_threshold_pct:
            # Recovery — re-enable trading
            self._triggered = False
            logger.info(
                f"CIRCUIT BREAKER RECOVERED: drawdown={dd:.1%} < "
                f"recovery threshold={self.recovery_threshold_pct:.1%} — BUYS RE-ENABLED"
            )
            state_changed = True

        return state_changed

    def reset(self):
        """Reset the circuit breaker state."""
        self._peak = 1.0
        self._equity = 1.0
        self._triggered = False

    def get_state(self) -> CircuitBreakerState:
        """Get current state for reporting."""
        dd = self.current_drawdown
        recovery = 0.0
        if self._triggered and self.max_drawdown_pct > 0:
            recovery = max(0.0, 1.0 - (dd / self.max_drawdown_pct))
        return CircuitBreakerState(
            is_triggered=self._triggered,
            current_drawdown=round(dd, 4),
            peak_equity=round(self._peak, 6),
            current_equity=round(self._equity, 6),
            trigger_count=self._trigger_count,
            last_trigger_at=self._last_trigger_at,
            recovery_pct=round(recovery, 4),
        )
