"""
tests/test_intraday_risk_monitor.py
--------------------------------------------------------------------------
Tests for IntradayRiskMonitor — drawdown circuit breakers.
"""

from __future__ import annotations

import pytest

from src.engines.portfolio.intraday_risk_monitor import (
    IntradayRiskConfig,
    IntradayRiskMonitor,
    PnLSnapshot,
    RiskState,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _monitor(**kw) -> IntradayRiskMonitor:
    return IntradayRiskMonitor(IntradayRiskConfig(**kw))


# ─── State Tests ─────────────────────────────────────────────────────────────

class TestStateTransitions:

    def test_initial_state_normal(self):
        m = _monitor()
        assert m.get_state() == RiskState.NORMAL

    def test_positive_pnl_stays_normal(self):
        m = _monitor()
        m.update_pnl(pnl_bps=50)  # +50 bps
        assert m.get_state() == RiskState.NORMAL

    def test_warning_on_2pct_drawdown(self):
        """Drawdown of ~250 bps triggers WARNING (default threshold 200 bps)."""
        m = _monitor()
        m.update_pnl(pnl_bps=100)   # Up to +1%
        m.update_pnl(pnl_bps=-350)  # Down to -2.5% from peak → DD = 3.5%
        assert m.get_state() in (RiskState.WARNING, RiskState.THROTTLE)

    def test_throttle_on_4pct_drawdown(self):
        """4%+ drawdown triggers THROTTLE."""
        m = _monitor()
        m.update_pnl(pnl_decimal=-0.045)  # -4.5% drawdown
        assert m.get_state() == RiskState.THROTTLE

    def test_halt_on_6pct_drawdown(self):
        """6%+ drawdown triggers HALT."""
        m = _monitor()
        m.update_pnl(pnl_decimal=-0.07)  # -7% drawdown
        assert m.get_state() == RiskState.HALT

    def test_progressive_degradation(self):
        """Normal → Warning → Throttle → Halt."""
        m = _monitor(
            warning_drawdown=0.01,
            throttle_drawdown=0.02,
            halt_drawdown=0.03,
        )
        m.update_pnl(pnl_decimal=-0.015)
        assert m.get_state() == RiskState.WARNING

        m.update_pnl(pnl_decimal=-0.010)
        assert m.get_state() == RiskState.THROTTLE

        m.update_pnl(pnl_decimal=-0.015)
        assert m.get_state() == RiskState.HALT


# ─── High Water Mark ─────────────────────────────────────────────────────────

class TestHighWaterMark:

    def test_hwm_updates_on_new_high(self):
        m = _monitor()
        m.update_pnl(pnl_decimal=0.01)
        snap = m.get_snapshot()
        assert snap.high_water_mark == pytest.approx(0.01)

        m.update_pnl(pnl_decimal=0.005)
        snap = m.get_snapshot()
        assert snap.high_water_mark == pytest.approx(0.015)

    def test_hwm_does_not_decrease(self):
        m = _monitor()
        m.update_pnl(pnl_decimal=0.02)
        m.update_pnl(pnl_decimal=-0.01)
        snap = m.get_snapshot()
        assert snap.high_water_mark == pytest.approx(0.02)

    def test_drawdown_from_hwm(self):
        m = _monitor()
        m.update_pnl(pnl_decimal=0.03)
        m.update_pnl(pnl_decimal=-0.01)
        snap = m.get_snapshot()
        assert snap.current_drawdown == pytest.approx(-0.01)


# ─── Trading Controls ───────────────────────────────────────────────────────

class TestTradingControls:

    def test_can_trade_in_normal(self):
        m = _monitor()
        assert m.can_trade() is True

    def test_can_trade_in_warning(self):
        m = _monitor(warning_drawdown=0.005)
        m.update_pnl(pnl_decimal=-0.01)
        assert m.get_state() == RiskState.WARNING
        assert m.can_trade() is True

    def test_cannot_trade_in_throttle(self):
        m = _monitor(throttle_drawdown=0.005)
        m.update_pnl(pnl_decimal=-0.01)
        assert m.can_trade() is False

    def test_cannot_trade_in_halt(self):
        m = _monitor(halt_drawdown=0.005)
        m.update_pnl(pnl_decimal=-0.01)
        assert m.can_trade() is False


# ─── Position Scale ──────────────────────────────────────────────────────────

class TestPositionScale:

    def test_normal_full_scale(self):
        m = _monitor()
        assert m.get_position_scale() == 1.0

    def test_warning_reduced_scale(self):
        m = _monitor(warning_drawdown=0.005)
        m.update_pnl(pnl_decimal=-0.01)
        assert m.get_position_scale() == 0.75

    def test_throttle_capped_scale(self):
        m = _monitor(throttle_drawdown=0.005, max_position_in_throttle=0.40)
        m.update_pnl(pnl_decimal=-0.01)
        assert m.get_position_scale() == 0.40

    def test_halt_zero_scale(self):
        m = _monitor(halt_drawdown=0.005)
        m.update_pnl(pnl_decimal=-0.01)
        assert m.get_position_scale() == 0.0


# ─── Rolling Vol ─────────────────────────────────────────────────────────────

class TestRollingVol:

    def test_vol_with_constant_pnl(self):
        """Constant P&L → vol = 0."""
        m = _monitor()
        for _ in range(20):
            m.update_pnl(pnl_decimal=0.001)
        snap = m.get_snapshot()
        assert snap.rolling_vol < 1e-6

    def test_vol_with_volatile_pnl(self):
        """Alternating +/- P&L → positive vol."""
        m = _monitor()
        for i in range(20):
            m.update_pnl(pnl_decimal=0.01 if i % 2 == 0 else -0.01)
        snap = m.get_snapshot()
        assert snap.rolling_vol > 0


# ─── Reset ───────────────────────────────────────────────────────────────────

class TestReset:

    def test_reset_clears_state(self):
        m = _monitor(halt_drawdown=0.005)
        m.update_pnl(pnl_decimal=-0.01)
        assert m.get_state() == RiskState.HALT

        m.reset()
        assert m.get_state() == RiskState.NORMAL
        snap = m.get_snapshot()
        assert snap.cumulative_pnl == 0.0
        assert snap.high_water_mark == 0.0

    def test_reset_preserves_transition_log(self):
        m = _monitor(warning_drawdown=0.005)
        m.update_pnl(pnl_decimal=-0.01)
        m.reset()
        log = m.get_transition_log()
        assert len(log) >= 2  # At least: NORMAL→WARNING, then reset


# ─── Snapshot ────────────────────────────────────────────────────────────────

class TestSnapshot:

    def test_snapshot_contract(self):
        m = _monitor()
        m.update_pnl(pnl_bps=100)
        snap = m.get_snapshot()
        assert isinstance(snap, PnLSnapshot)
        assert snap.updates_count == 1
        assert snap.cumulative_pnl > 0

    def test_pnl_via_bps_and_decimal_equivalent(self):
        """100 bps = 0.01 decimal."""
        m1 = _monitor()
        m1.update_pnl(pnl_bps=100)

        m2 = _monitor()
        m2.update_pnl(pnl_decimal=0.01)

        assert m1.get_snapshot().cumulative_pnl == pytest.approx(
            m2.get_snapshot().cumulative_pnl,
        )
