"""
tests/test_walk_forward.py
--------------------------------------------------------------------------
Tests for WalkForwardValidator and governor OOS overfit gate.
"""

from __future__ import annotations

import pytest
from datetime import date

from src.engines.backtesting.models import SignalEvent, SignalStrength
from src.engines.backtesting.walk_forward_validator import (
    WalkForwardValidator,
    WalkForwardReport,
    SignalWFResult,
)
from src.engines.backtesting.calibration_models import (
    GovernanceAction,
    ParameterChange,
    ParameterType,
)
from src.engines.backtesting.calibration_governor import CalibrationGovernor
from src.engines.alpha_signals.models import SignalCategory
from src.engines.backtesting.models import SignalPerformanceRecord


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_event(
    signal_id: str,
    fired_date: date,
    excess_return_20: float = 0.01,
    ticker: str = "AAPL",
) -> SignalEvent:
    return SignalEvent(
        signal_id=signal_id,
        ticker=ticker,
        fired_date=fired_date,
        strength=SignalStrength.MODERATE,
        confidence=0.7,
        value=1.0,
        price_at_fire=100.0,
        forward_returns={20: excess_return_20 + 0.005},
        benchmark_returns={20: 0.005},
        excess_returns={20: excess_return_20},
    )


def _make_dated_events(
    signal_id: str,
    start_date: date,
    n: int,
    base_excess: float = 0.02,
    noise: float = 0.005,
) -> list[SignalEvent]:
    """Create N events spread across days from start_date."""
    events = []
    for i in range(n):
        d = date.fromordinal(start_date.toordinal() + i)
        excess = base_excess + (noise * (1 if i % 2 == 0 else -1))
        events.append(_make_event(signal_id, d, excess))
    return events


def _make_overfit_events(
    signal_id: str,
    start_date: date,
    n: int,
) -> list[SignalEvent]:
    """Create events that perform great in first half, poorly in second half."""
    events = []
    mid = n // 2
    for i in range(n):
        d = date.fromordinal(start_date.toordinal() + i)
        if i < mid:
            excess = 0.05 + 0.002 * (1 if i % 2 == 0 else -1)  # Strong train
        else:
            excess = -0.01 + 0.03 * (1 if i % 2 == 0 else -1)  # Noisy test
        events.append(_make_event(signal_id, d, excess))
    return events


def _make_performance_record(
    signal_id: str = "test.sig",
    total_firings: int = 100,
    sharpe_20: float = 0.5,
    hit_rate_20: float = 0.55,
) -> SignalPerformanceRecord:
    return SignalPerformanceRecord(
        signal_id=signal_id,
        signal_name=f"Test {signal_id}",
        category=SignalCategory("value"),
        total_firings=total_firings,
        total_correct=int(total_firings * hit_rate_20),
        sharpe_ratio={20: sharpe_20},
        hit_rate={20: hit_rate_20},
        avg_return={20: 0.005},
    )


# ─── Validator Tests ─────────────────────────────────────────────────────────

class TestWalkForwardValidator:
    def test_stable_signal_low_degradation(self):
        """Signal with consistent performance → low OOS degradation."""
        events = _make_dated_events(
            "stable", date(2023, 1, 1), n=200, base_excess=0.02, noise=0.003,
        )
        validator = WalkForwardValidator(n_windows=4, train_pct=0.7)
        report = validator.validate(events)

        assert report.total_signals == 1
        result = report.signal_results[0]
        assert result.signal_id == "stable"
        assert result.is_overfit is False
        # Stable signal shouldn't degrade much
        assert result.oos_degradation < 0.50

    def test_overfit_signal_detected(self):
        """Signal that's great in-sample but poor OOS → high degradation."""
        # Create 4 windows worth of events where each window's first 70%
        # is strong but last 30% collapses
        events = []
        for w in range(4):
            base_day = date(2023, 1, 1).toordinal() + w * 90
            window_events = _make_overfit_events(
                "overfit_sig", date.fromordinal(base_day), n=60,
            )
            events.extend(window_events)

        validator = WalkForwardValidator(n_windows=4, train_pct=0.7)
        report = validator.validate(events)

        assert report.total_signals == 1
        result = report.signal_results[0]
        # Should detect high degradation
        assert result.avg_train_sharpe > result.avg_test_sharpe

    def test_empty_events_returns_empty(self):
        """No events → empty report."""
        validator = WalkForwardValidator(n_windows=4)
        report = validator.validate([])
        assert report.total_signals == 0
        assert report.n_windows == 4

    def test_multiple_signals(self):
        """Multiple signals evaluated independently."""
        stable = _make_dated_events(
            "stable", date(2023, 1, 1), n=200, base_excess=0.025, noise=0.003,
        )
        noisy = _make_dated_events(
            "noisy", date(2023, 1, 1), n=200, base_excess=0.005, noise=0.04,
        )
        validator = WalkForwardValidator(n_windows=4, train_pct=0.7)
        report = validator.validate(stable + noisy)

        assert report.total_signals == 2
        ids = {r.signal_id for r in report.signal_results}
        assert ids == {"stable", "noisy"}

    def test_invalid_params_rejected(self):
        """Invalid constructor params raise ValueError."""
        with pytest.raises(ValueError):
            WalkForwardValidator(n_windows=1)
        with pytest.raises(ValueError):
            WalkForwardValidator(train_pct=0.1)
        with pytest.raises(ValueError):
            WalkForwardValidator(train_pct=0.95)

    def test_signal_meta_propagated(self):
        """Signal names from metadata appear in results."""
        events = _make_dated_events("sig.a", date(2023, 1, 1), n=200)
        meta = {"sig.a": "MACD Bearish"}
        validator = WalkForwardValidator(n_windows=4)
        report = validator.validate(events, signal_meta=meta)

        assert report.signal_results[0].signal_name == "MACD Bearish"

    def test_window_count_matches(self):
        """Windows in results should match n_windows (or fewer if data sparse)."""
        events = _make_dated_events(
            "sig", date(2023, 1, 1), n=300, base_excess=0.02,
        )
        validator = WalkForwardValidator(n_windows=4, train_pct=0.7)
        report = validator.validate(events)

        result = report.signal_results[0]
        assert len(result.windows) <= 4
        for w in result.windows:
            assert w.train_events >= 5
            assert w.test_events >= 5


# ─── Governor Integration ───────────────────────────────────────────────────

class TestGovernorOOSGate:
    def setup_method(self):
        self.governor = CalibrationGovernor()

    def test_governor_flags_overfit_weight_increase(self):
        """Weight increase with high OOS degradation → FLAGGED."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0,
            new_value=1.1,
            oos_degradation=0.65,  # 65% degradation
        )
        record = _make_performance_record(total_firings=100, sharpe_20=0.5)
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.FLAGGED
        assert "OOS overfit" in decisions[0].reason
        assert "65%" in decisions[0].reason

    def test_governor_allows_stable_weight_increase(self):
        """Weight increase with low OOS degradation → normal rules."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0,
            new_value=1.08,
            oos_degradation=0.15,  # Only 15% degradation — OK
        )
        record = _make_performance_record(total_firings=100, sharpe_20=0.5)
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.APPROVED

    def test_governor_allows_overfit_weight_decrease(self):
        """Weight decrease with high OOS degradation → no flag (correct direction)."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0,
            new_value=0.8,
            oos_degradation=0.70,  # High degradation, but we're decreasing weight
        )
        record = _make_performance_record(total_firings=100, sharpe_20=0.5)
        decisions = self.governor.review([change], {"test.sig": record})

        assert "OOS overfit" not in decisions[0].reason
