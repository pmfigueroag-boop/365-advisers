"""
tests/test_perturbation.py
--------------------------------------------------------------------------
Tests for PerturbationValidator and governor fragility gate.
"""

from __future__ import annotations

import pytest
from datetime import date

from src.engines.backtesting.models import SignalEvent, SignalStrength
from src.engines.backtesting.perturbation_validator import (
    PerturbationValidator,
    PerturbationReport,
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
) -> SignalEvent:
    return SignalEvent(
        signal_id=signal_id,
        ticker="AAPL",
        fired_date=fired_date,
        strength=SignalStrength.MODERATE,
        confidence=0.7,
        value=1.0,
        price_at_fire=100.0,
        forward_returns={20: excess_return_20 + 0.005},
        benchmark_returns={20: 0.005},
        excess_returns={20: excess_return_20},
    )


def _make_robust_events(signal_id: str, n: int = 30) -> list[SignalEvent]:
    """Strong, consistent signal — should be robust to perturbation."""
    events = []
    for i in range(n):
        # Tight returns with minimal noise
        excess = 0.03 + 0.001 * (1 if i % 2 == 0 else -1)
        events.append(_make_event(signal_id, date(2024, 1, 1 + i), excess))
    return events


def _make_fragile_events(signal_id: str, n: int = 30) -> list[SignalEvent]:
    """Signal where Sharpe depends on tiny return differences — fragile."""
    events = []
    for i in range(n):
        # Very small excess with high variance relative to mean
        excess = 0.001 + 0.02 * (1 if i % 2 == 0 else -1)
        events.append(_make_event(signal_id, date(2024, 1, 1 + i), excess))
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

class TestPerturbationValidator:
    def test_robust_signal_low_sensitivity(self):
        """Robust signal → low perturbation sensitivity."""
        events = _make_robust_events("robust")
        validator = PerturbationValidator(n_trials=30, noise_pct=0.02, seed=42)
        report = validator.validate(events)

        assert report.total_signals == 1
        result = report.signal_results[0]
        assert result.signal_id == "robust"
        assert result.is_fragile is False
        assert result.perturbation_sensitivity < 0.50
        assert result.sharpe_retention > 0.80

    def test_fragile_signal_high_sensitivity(self):
        """Fragile signal (small mean, high var) → high perturbation sensitivity."""
        events = _make_fragile_events("fragile")
        validator = PerturbationValidator(n_trials=30, noise_pct=0.05, seed=42)
        report = validator.validate(events)

        assert report.total_signals == 1
        result = report.signal_results[0]
        # Fragile signals have larger sensitivity than robust ones
        assert result.perturbation_sensitivity > 0.10

    def test_empty_events_returns_empty(self):
        """No events → empty report."""
        validator = PerturbationValidator(n_trials=30, seed=42)
        report = validator.validate([])
        assert report.total_signals == 0

    def test_multiple_signals(self):
        """Multiple signals evaluated independently."""
        robust = _make_robust_events("robust", n=30)
        fragile = _make_fragile_events("fragile", n=30)
        validator = PerturbationValidator(n_trials=20, noise_pct=0.02, seed=42)
        report = validator.validate(robust + fragile)

        assert report.total_signals == 2
        ids = {r.signal_id for r in report.signal_results}
        assert ids == {"robust", "fragile"}

    def test_invalid_params_rejected(self):
        """Invalid constructor params raise ValueError."""
        with pytest.raises(ValueError):
            PerturbationValidator(n_trials=2)
        with pytest.raises(ValueError):
            PerturbationValidator(noise_pct=0.0001)
        with pytest.raises(ValueError):
            PerturbationValidator(noise_pct=0.60)

    def test_reproducible_with_seed(self):
        """Same seed → same results."""
        events = _make_robust_events("sig", n=30)

        v1 = PerturbationValidator(n_trials=20, seed=99)
        r1 = v1.validate(events)

        v2 = PerturbationValidator(n_trials=20, seed=99)
        r2 = v2.validate(events)

        assert r1.signal_results[0].perturbation_sensitivity == \
               r2.signal_results[0].perturbation_sensitivity
        assert r1.signal_results[0].mean_perturbed_sharpe == \
               r2.signal_results[0].mean_perturbed_sharpe

    def test_signal_meta_propagated(self):
        """Signal names from metadata appear in results."""
        events = _make_robust_events("sig.a", n=20)
        meta = {"sig.a": "RSI Strong"}
        validator = PerturbationValidator(n_trials=10, seed=42)
        report = validator.validate(events, signal_meta=meta)

        assert report.signal_results[0].signal_name == "RSI Strong"

    def test_insufficient_events_skipped(self):
        """Signal with < 10 events gets default (no crash)."""
        events = [_make_event("small", date(2024, 1, i + 1)) for i in range(5)]
        validator = PerturbationValidator(n_trials=10, seed=42)
        report = validator.validate(events)

        assert report.total_signals == 1
        result = report.signal_results[0]
        assert result.base_sharpe == 0.0  # Not enough data


# ─── Governor Integration ───────────────────────────────────────────────────

class TestGovernorFragilityGate:
    def setup_method(self):
        self.governor = CalibrationGovernor()

    def test_governor_flags_fragile_weight_increase(self):
        """Weight increase with high perturbation sensitivity → FLAGGED."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0,
            new_value=1.1,
            perturbation_sensitivity=0.65,  # Very fragile
        )
        record = _make_performance_record(total_firings=100, sharpe_20=0.5)
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.FLAGGED
        assert "Fragile signal" in decisions[0].reason

    def test_governor_allows_robust_weight_increase(self):
        """Weight increase with low sensitivity → normal rules."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0,
            new_value=1.08,
            perturbation_sensitivity=0.15,  # Robust
        )
        record = _make_performance_record(total_firings=100, sharpe_20=0.5)
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.APPROVED

    def test_governor_allows_fragile_weight_decrease(self):
        """Weight decrease with fragile signal → no flag (correct direction)."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0,
            new_value=0.8,
            perturbation_sensitivity=0.80,  # Fragile, but we're reducing
        )
        record = _make_performance_record(total_firings=100, sharpe_20=0.5)
        decisions = self.governor.review([change], {"test.sig": record})

        assert "Fragile signal" not in decisions[0].reason
