"""
tests/test_top_bottom.py
--------------------------------------------------------------------------
Tests for TopBottomValidator and governor negative-spread gate.
"""

from __future__ import annotations

import pytest
from datetime import date

from src.engines.backtesting.models import SignalEvent, SignalStrength
from src.engines.backtesting.top_bottom_validator import (
    TopBottomValidator,
    TopBottomReport,
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
    confidence: float = 0.7,
    excess_return_20: float = 0.01,
    ticker: str = "AAPL",
) -> SignalEvent:
    return SignalEvent(
        signal_id=signal_id,
        ticker=ticker,
        fired_date=fired_date,
        strength=SignalStrength.MODERATE,
        confidence=confidence,
        value=1.0,
        price_at_fire=100.0,
        forward_returns={20: excess_return_20 + 0.005},
        benchmark_returns={20: 0.005},
        excess_returns={20: excess_return_20},
    )


def _make_discriminating_events(
    signal_id: str,
    n_dates: int = 20,
    n_per_date: int = 10,
) -> list[SignalEvent]:
    """Signal where high confidence → high returns (positive spread)."""
    events = []
    for d in range(n_dates):
        fired = date(2024, 1, 1 + d)
        for i in range(n_per_date):
            # Confidence and return are correlated, slight date noise
            conf = 0.3 + 0.05 * i  # 0.30 to 0.75
            excess = 0.005 + 0.004 * i + 0.001 * (d % 3 - 1)
            events.append(_make_event(
                signal_id, fired, conf, excess, ticker=f"T{i}",
            ))
    return events


def _make_inverse_events(
    signal_id: str,
    n_dates: int = 20,
    n_per_date: int = 10,
) -> list[SignalEvent]:
    """Signal where high confidence → LOW returns (negative spread)."""
    events = []
    for d in range(n_dates):
        fired = date(2024, 1, 1 + d)
        for i in range(n_per_date):
            # Confidence and return are inversely correlated
            conf = 0.3 + 0.05 * i  # 0.30 to 0.75
            excess = 0.04 - 0.004 * i  # monotonically decreasing
            events.append(_make_event(
                signal_id, fired, conf, excess, ticker=f"T{i}",
            ))
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

class TestTopBottomValidator:
    def test_discriminating_signal_positive_spread(self):
        """Signal with conf correlated to returns → positive spread."""
        events = _make_discriminating_events("good_sig")
        validator = TopBottomValidator(quintile_pct=0.20)
        report = validator.validate(events)

        assert report.total_signals == 1
        result = report.signal_results[0]
        assert result.signal_id == "good_sig"
        assert result.spread > 0
        assert result.top_avg_return > result.bottom_avg_return
        assert result.has_negative_spread is False

    def test_inverse_signal_negative_spread(self):
        """Signal with inv. correlation → negative spread."""
        events = _make_inverse_events("bad_sig")
        validator = TopBottomValidator(quintile_pct=0.20)
        report = validator.validate(events)

        assert report.total_signals == 1
        result = report.signal_results[0]
        assert result.spread < 0
        assert result.has_negative_spread is True
        assert report.negative_spread_count == 1

    def test_significant_spread_detected(self):
        """Signal with consistent positive spread → significant t-stat."""
        import random
        rng = random.Random(42)
        events = []
        for d in range(30):
            fired = date(2024, 1, 1 + d)
            for i in range(10):
                conf = 0.3 + 0.05 * i
                # Per-event noise that scales with rank → varying spread
                excess = 0.005 + 0.004 * i + rng.gauss(0, 0.003)
                events.append(_make_event(
                    "sig", fired, conf, excess, ticker=f"T{i}",
                ))

        validator = TopBottomValidator(quintile_pct=0.20, min_periods=5)
        report = validator.validate(events)

        result = report.signal_results[0]
        assert result.n_periods >= 5
        assert result.spread > 0
        # With varying spreads across dates, t-stat should be computable
        assert abs(result.spread_t_stat) > 2.0
        assert result.is_significant is True

    def test_empty_events_returns_empty(self):
        """No events → empty report."""
        validator = TopBottomValidator()
        report = validator.validate([])
        assert report.total_signals == 0

    def test_multiple_signals(self):
        """Multiple signals evaluated independently."""
        good = _make_discriminating_events("good", n_dates=10)
        bad = _make_inverse_events("bad", n_dates=10)
        validator = TopBottomValidator()
        report = validator.validate(good + bad)

        assert report.total_signals == 2
        ids = {r.signal_id for r in report.signal_results}
        assert ids == {"good", "bad"}

    def test_invalid_params_rejected(self):
        """Invalid constructor params raise ValueError."""
        with pytest.raises(ValueError):
            TopBottomValidator(quintile_pct=0.05)
        with pytest.raises(ValueError):
            TopBottomValidator(quintile_pct=0.55)
        with pytest.raises(ValueError):
            TopBottomValidator(min_periods=1)

    def test_signal_meta_propagated(self):
        """Signal names appear in results."""
        events = _make_discriminating_events("sig.a", n_dates=10)
        meta = {"sig.a": "MACD Bearish"}
        validator = TopBottomValidator()
        report = validator.validate(events, signal_meta=meta)
        assert report.signal_results[0].signal_name == "MACD Bearish"

    def test_monotonicity_high_for_discriminating_signal(self):
        """Signal with monotonic conf→return → high monotonicity score."""
        events = _make_discriminating_events("mono", n_dates=10, n_per_date=10)
        validator = TopBottomValidator(quintile_pct=0.20)
        report = validator.validate(events)

        result = report.signal_results[0]
        assert len(result.quintile_returns) == 5
        # Q1 (low conf) should have lowest return, Q5 highest
        assert result.quintile_returns[0] < result.quintile_returns[4]
        # Kendall tau should be high (close to 1.0)
        assert result.monotonicity_score > 0.5

    def test_monotonicity_negative_for_inverse_signal(self):
        """Signal with inverse conf→return → negative monotonicity."""
        events = _make_inverse_events("inv", n_dates=10, n_per_date=10)
        validator = TopBottomValidator(quintile_pct=0.20)
        report = validator.validate(events)

        result = report.signal_results[0]
        assert len(result.quintile_returns) == 5
        # Q1 (low conf) should have HIGHER return than Q5
        assert result.quintile_returns[0] > result.quintile_returns[4]
        assert result.monotonicity_score < 0

    def test_quintile_returns_length(self):
        """quintile_returns should always have 5 entries."""
        events = _make_discriminating_events("q5", n_dates=10, n_per_date=10)
        validator = TopBottomValidator()
        report = validator.validate(events)
        assert len(report.signal_results[0].quintile_returns) == 5


# ─── Governor Integration ───────────────────────────────────────────────────

class TestGovernorSpreadGate:
    def setup_method(self):
        self.governor = CalibrationGovernor()

    def test_governor_flags_negative_spread_weight_increase(self):
        """Weight increase + significant negative spread → FLAGGED."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0,
            new_value=1.1,
            spread_t_stat=-2.8,  # Significantly negative
        )
        record = _make_performance_record(total_firings=100, sharpe_20=0.5)
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.FLAGGED
        assert "Inverse signal" in decisions[0].reason
        assert "-2.80" in decisions[0].reason

    def test_governor_allows_positive_spread_weight_increase(self):
        """Weight increase + positive spread → normal rules."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0,
            new_value=1.08,
            spread_t_stat=3.5,  # Positive, significant
        )
        record = _make_performance_record(total_firings=100, sharpe_20=0.5)
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.APPROVED

    def test_governor_allows_negative_spread_weight_decrease(self):
        """Weight decrease + negative spread → no flag (correct direction)."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0,
            new_value=0.8,
            spread_t_stat=-3.0,  # Negative, but we're reducing weight
        )
        record = _make_performance_record(total_firings=100, sharpe_20=0.5)
        decisions = self.governor.review([change], {"test.sig": record})

        assert "Inverse signal" not in decisions[0].reason
