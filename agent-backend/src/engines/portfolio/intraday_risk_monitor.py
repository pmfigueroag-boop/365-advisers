"""
src/engines/portfolio/intraday_risk_monitor.py
--------------------------------------------------------------------------
Intraday P&L Risk Monitor — real-time drawdown circuit breakers.

State machine:
  NORMAL → WARNING → THROTTLE → HALT

Monitors:
  - Cumulative P&L from mark-to-market updates
  - Drawdown from high-water mark
  - Rolling 5-minute volatility
  - Time since last high-water mark

Integration:
  - Pre-trade check: block new orders in THROTTLE/HALT
  - Alert dispatch: fire webhook on state transitions
  - Recovery: manual reset or automatic after recovery

Usage::

    monitor = IntradayRiskMonitor()
    monitor.update_pnl(pnl_bps=5)     # +5 bps
    monitor.update_pnl(pnl_bps=-250)  # Drawdown → WARNING
    state = monitor.get_state()
"""

from __future__ import annotations

import logging
import math
import time
from collections import deque
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.portfolio.intraday_risk")


# ── Contracts ────────────────────────────────────────────────────────────────

class RiskState(str, Enum):
    """Intraday risk state machine."""
    NORMAL = "normal"
    WARNING = "warning"
    THROTTLE = "throttle"
    HALT = "halt"


class IntradayRiskConfig(BaseModel):
    """Configurable drawdown limits (in decimal, e.g. 0.02 = 2%)."""
    warning_drawdown: float = Field(0.02, description="Drawdown for WARNING")
    throttle_drawdown: float = Field(0.04, description="Drawdown for THROTTLE")
    halt_drawdown: float = Field(0.06, description="Drawdown for HALT")
    recovery_fraction: float = Field(
        0.50, description="Recover drawdown by this fraction to downgrade state",
    )
    rolling_vol_window: int = Field(
        20, description="Number of updates for rolling vol",
    )
    max_position_in_throttle: float = Field(
        0.50, description="Max position scale factor in THROTTLE",
    )


class PnLSnapshot(BaseModel):
    """Point-in-time P&L state."""
    cumulative_pnl: float = 0.0       # Decimal return
    high_water_mark: float = 0.0
    current_drawdown: float = 0.0     # Always ≤ 0
    state: RiskState = RiskState.NORMAL
    rolling_vol: float = 0.0
    updates_count: int = 0
    state_transitions: int = 0
    time_since_hwm_seconds: float = 0.0


# ── Engine ───────────────────────────────────────────────────────────────────

class IntradayRiskMonitor:
    """
    Real-time portfolio risk monitor with drawdown circuit breakers.

    Tracks cumulative intraday P&L, computes drawdown from the session's
    high-water mark, and transitions through risk states based on
    configurable thresholds.
    """

    def __init__(self, config: IntradayRiskConfig | None = None) -> None:
        self.config = config or IntradayRiskConfig()
        self._cumulative_pnl: float = 0.0
        self._high_water_mark: float = 0.0
        self._hwm_time: float = time.monotonic()
        self._state: RiskState = RiskState.NORMAL
        self._updates_count: int = 0
        self._state_transitions: int = 0
        self._pnl_history: deque[float] = deque(
            maxlen=self.config.rolling_vol_window,
        )
        self._transition_log: list[dict] = []

    def update_pnl(self, pnl_bps: float | None = None, pnl_decimal: float | None = None) -> RiskState:
        """
        Record a P&L update and evaluate risk state.

        Parameters
        ----------
        pnl_bps : float | None
            P&L change in basis points (100 bps = 1%).
        pnl_decimal : float | None
            P&L change in decimal (0.01 = 1%).
        """
        if pnl_decimal is not None:
            delta = pnl_decimal
        elif pnl_bps is not None:
            delta = pnl_bps / 10_000
        else:
            return self._state

        self._cumulative_pnl += delta
        self._updates_count += 1
        self._pnl_history.append(delta)

        # Update high-water mark
        if self._cumulative_pnl > self._high_water_mark:
            self._high_water_mark = self._cumulative_pnl
            self._hwm_time = time.monotonic()

        # Compute drawdown
        drawdown = self._cumulative_pnl - self._high_water_mark  # Always ≤ 0

        # Evaluate state
        new_state = self._evaluate_state(drawdown)

        if new_state != self._state:
            self._log_transition(self._state, new_state, drawdown)
            self._state = new_state

        return self._state

    def get_state(self) -> RiskState:
        """Get current risk state."""
        return self._state

    def get_snapshot(self) -> PnLSnapshot:
        """Get full P&L snapshot."""
        drawdown = self._cumulative_pnl - self._high_water_mark
        return PnLSnapshot(
            cumulative_pnl=round(self._cumulative_pnl, 6),
            high_water_mark=round(self._high_water_mark, 6),
            current_drawdown=round(drawdown, 6),
            state=self._state,
            rolling_vol=round(self._compute_rolling_vol(), 6),
            updates_count=self._updates_count,
            state_transitions=self._state_transitions,
            time_since_hwm_seconds=round(
                time.monotonic() - self._hwm_time, 1,
            ),
        )

    def can_trade(self) -> bool:
        """Can new orders be placed?"""
        return self._state in (RiskState.NORMAL, RiskState.WARNING)

    def get_position_scale(self) -> float:
        """Position sizing multiplier based on risk state."""
        match self._state:
            case RiskState.NORMAL:
                return 1.0
            case RiskState.WARNING:
                return 0.75
            case RiskState.THROTTLE:
                return self.config.max_position_in_throttle
            case RiskState.HALT:
                return 0.0

    def reset(self) -> None:
        """Reset monitor (new trading day / manual override)."""
        prev = self._state
        self._cumulative_pnl = 0.0
        self._high_water_mark = 0.0
        self._hwm_time = time.monotonic()
        self._state = RiskState.NORMAL
        self._updates_count = 0
        self._pnl_history.clear()

        if prev != RiskState.NORMAL:
            self._log_transition(prev, RiskState.NORMAL, 0.0)
            logger.info("INTRADAY-RISK: Manual reset from %s → NORMAL", prev.value)

    def get_transition_log(self) -> list[dict]:
        """Get log of state transitions."""
        return list(self._transition_log)

    # ── Internal ─────────────────────────────────────────────────────────

    def _evaluate_state(self, drawdown: float) -> RiskState:
        """Determine risk state from current drawdown."""
        dd = abs(drawdown)

        if dd >= self.config.halt_drawdown:
            return RiskState.HALT
        elif dd >= self.config.throttle_drawdown:
            return RiskState.THROTTLE
        elif dd >= self.config.warning_drawdown:
            return RiskState.WARNING

        # Check for recovery: if currently in elevated state,
        # only downgrade if drawdown has recovered sufficiently
        if self._state == RiskState.WARNING and dd < self.config.warning_drawdown * self.config.recovery_fraction:
            return RiskState.NORMAL
        elif self._state in (RiskState.THROTTLE, RiskState.HALT):
            # Stay in current state until explicit reset or drawdown recovers
            if dd < self.config.warning_drawdown:
                return RiskState.WARNING
            return self._state

        return RiskState.NORMAL

    def _compute_rolling_vol(self) -> float:
        """Compute rolling standard deviation of P&L updates."""
        if len(self._pnl_history) < 2:
            return 0.0

        values = list(self._pnl_history)
        n = len(values)
        mean = sum(values) / n
        var = sum((v - mean) ** 2 for v in values) / (n - 1)
        return math.sqrt(var)

    def _log_transition(
        self,
        from_state: RiskState,
        to_state: RiskState,
        drawdown: float,
    ) -> None:
        """Log a state transition."""
        self._state_transitions += 1
        entry = {
            "from": from_state.value,
            "to": to_state.value,
            "drawdown": round(drawdown, 6),
            "pnl": round(self._cumulative_pnl, 6),
            "update_idx": self._updates_count,
        }
        self._transition_log.append(entry)

        severity = "WARNING" if to_state in (RiskState.THROTTLE, RiskState.HALT) else "INFO"
        logger.log(
            logging.WARNING if severity == "WARNING" else logging.INFO,
            "INTRADAY-RISK: %s → %s (drawdown=%.2f%%, pnl=%.2f%%)",
            from_state.value, to_state.value,
            drawdown * 100, self._cumulative_pnl * 100,
        )
