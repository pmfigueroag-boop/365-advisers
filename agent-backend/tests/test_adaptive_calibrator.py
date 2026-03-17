"""
tests/test_adaptive_calibrator.py
--------------------------------------------------------------------------
Tests for AdaptiveCalibrator, CalibrationGovernor, and CalibrationStore.
"""

from __future__ import annotations

import json
import tempfile
import pytest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    SignalCategory,
    SignalDirection,
)
from src.engines.alpha_signals.registry import SignalRegistry
from src.engines.backtesting.adaptive_calibrator import AdaptiveCalibrator
from src.engines.backtesting.calibration_governor import CalibrationGovernor
from src.engines.backtesting.calibration_store import CalibrationStore
from src.engines.backtesting.calibration_models import (
    CalibrationConfig,
    CalibrationVersion,
    CalibratedSignalConfig,
    GovernanceAction,
    ParameterChange,
    ParameterType,
    RegimeWeightTable,
)
from src.engines.backtesting.models import (
    BacktestReport,
    BacktestConfig,
    BacktestStatus,
    SignalPerformanceRecord,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_signal_def(
    signal_id: str = "test.signal",
    weight: float = 1.0,
    category: str = "value",
) -> AlphaSignalDefinition:
    return AlphaSignalDefinition(
        id=signal_id,
        name=f"Test Signal {signal_id}",
        category=SignalCategory(category),
        feature_path="fundamental.pe_ratio",
        direction=SignalDirection.BELOW,
        threshold=15.0,
        weight=weight,
    )


def _make_performance_record(
    signal_id: str = "test.signal",
    category: str = "value",
    total_firings: int = 100,
    hit_rate_20: float = 0.65,
    sharpe_20: float = 1.5,
    empirical_half_life: float = 15.0,
) -> SignalPerformanceRecord:
    return SignalPerformanceRecord(
        signal_id=signal_id,
        signal_name=f"Test Signal {signal_id}",
        category=SignalCategory(category),
        total_firings=total_firings,
        hit_rate={5: 0.55, 20: hit_rate_20, 60: 0.60},
        avg_return={5: 0.005, 20: 0.015, 60: 0.03},
        avg_excess_return={5: 0.002, 20: 0.008, 60: 0.015},
        sharpe_ratio={5: 0.5, 20: sharpe_20, 60: 1.0},
        confidence_level="MEDIUM",
        empirical_half_life=empirical_half_life,
        optimal_hold_period=20,
    )


def _make_report(records: list[SignalPerformanceRecord]) -> BacktestReport:
    return BacktestReport(
        config=BacktestConfig(
            universe=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2025, 1, 1),
        ),
        status=BacktestStatus.COMPLETED,
        signal_results=records,
        execution_time_seconds=10.0,
    )


# ─── AdaptiveCalibrator Tests ────────────────────────────────────────────────

class TestAdaptiveCalibrator:
    def setup_method(self):
        # Register test signals
        from src.engines.alpha_signals.registry import registry
        self.signal = _make_signal_def("test.high_sharpe", weight=1.0)
        registry.register(self.signal)
        self.calibrator = AdaptiveCalibrator()

    def test_positive_sharpe_increases_weight(self):
        """Signal with positive Sharpe should get higher weight."""
        record = _make_performance_record(
            signal_id="test.high_sharpe",
            sharpe_20=1.5,
            total_firings=100,
        )
        report = _make_report([record])
        changes, configs, _ = self.calibrator.calibrate(report)

        config = configs[0]
        assert config.weight > 1.0  # Weight increased
        # Bayesian: alpha = 100/(100+50)×sqrt(100/50) ≈ 0.943
        # IC = 0.6×tanh(0.75) + 0.4×(0.65-0.5)×2 ≈ 0.6×0.635+0.4×0.30 ≈ 0.501
        # scale = alpha×(1+IC) + (1-alpha)×1.0
        assert config.weight > 1.2  # Substantially increased

    def test_negative_sharpe_decreases_weight(self):
        """Signal with negative Sharpe should get lower weight."""
        record = _make_performance_record(
            signal_id="test.high_sharpe",
            sharpe_20=-1.5,
            total_firings=100,
        )
        report = _make_report([record])
        _, configs, _ = self.calibrator.calibrate(report)

        config = configs[0]
        assert config.weight < 1.0  # Weight decreased
        # Bayesian shrinkage: more conservative than the old formula
        # because alpha shrinks the change toward the prior
        assert config.weight > 0.5  # Less aggressive than old formula
        assert config.weight < 0.95  # But still meaningfully reduced

    def test_weight_clamped_min(self):
        """Weight should not go below clamp minimum."""
        record = _make_performance_record(
            signal_id="test.high_sharpe",
            sharpe_20=-10.0,  # Very negative
            total_firings=100,
        )
        report = _make_report([record])
        _, configs, _ = self.calibrator.calibrate(report)

        assert configs[0].weight >= 0.3  # Clamp min

    def test_weight_clamped_max(self):
        """Weight should not go above clamp maximum."""
        record = _make_performance_record(
            signal_id="test.high_sharpe",
            sharpe_20=15.0,  # Very positive
            total_firings=100,
        )
        report = _make_report([record])
        _, configs, _ = self.calibrator.calibrate(report)

        assert configs[0].weight <= 3.0  # Clamp max

    def test_insufficient_observations_no_change(self):
        """With too few firings, weight should stay at base."""
        record = _make_performance_record(
            signal_id="test.high_sharpe",
            sharpe_20=2.0,
            total_firings=10,  # Below min_observations=50
        )
        report = _make_report([record])
        _, configs, _ = self.calibrator.calibrate(report)

        # Bayesian: with n=10, alpha is very small (≈0.08)
        # so the weight barely moves from the prior of 1.0
        assert abs(configs[0].weight - 1.0) < 0.1  # Nearly unchanged

    def test_dynamic_confidence(self):
        """Confidence should be higher for high hit rate + high Sharpe."""
        high_perf = _make_performance_record(
            signal_id="test.high_sharpe",
            hit_rate_20=0.75,
            sharpe_20=2.0,
            total_firings=200,
        )
        low_perf = _make_performance_record(
            signal_id="test.high_sharpe",
            hit_rate_20=0.40,
            sharpe_20=-1.0,
            total_firings=20,
        )

        report_high = _make_report([high_perf])
        report_low = _make_report([low_perf])

        _, configs_high, _ = self.calibrator.calibrate(report_high)
        _, configs_low, _ = self.calibrator.calibrate(report_low)

        assert configs_high[0].confidence_score > configs_low[0].confidence_score

    def test_changes_detected(self):
        """Should detect weight and half-life changes."""
        record = _make_performance_record(
            signal_id="test.high_sharpe",
            sharpe_20=1.5,
            total_firings=100,
            empirical_half_life=5.0,  # Very different from default
        )
        report = _make_report([record])
        changes, _, _ = self.calibrator.calibrate(report)

        # Should have at least a weight change
        weight_changes = [c for c in changes if c.parameter == ParameterType.WEIGHT]
        assert len(weight_changes) >= 1


# ─── CalibrationGovernor Tests (Post-Audit) ──────────────────────────────────

class TestCalibrationGovernor:
    def setup_method(self):
        self.governor = CalibrationGovernor()

    # ── P0: Record = None → Reject ──────────────────────────────────────

    def test_no_record_rejected(self):
        """P0: Signal with no performance record must be rejected."""
        change = ParameterChange(
            signal_id="unknown.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.1, change_pct=0.10,
        )
        decisions = self.governor.review([change], {})  # Empty records

        assert decisions[0].action == GovernanceAction.REJECTED
        assert "No performance record" in decisions[0].reason

    # ── P0: FLAGGED ≠ APPROVED ──────────────────────────────────────────

    def test_get_approved_excludes_flagged(self):
        """P0: get_approved must NOT include FLAGGED changes."""
        change1 = ParameterChange(
            signal_id="s1", parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.1, change_pct=0.10,
        )
        change2 = ParameterChange(
            signal_id="s2", parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.18, change_pct=0.18,
        )
        records = {
            "s1": _make_performance_record(signal_id="s1", total_firings=100),
            "s2": _make_performance_record(signal_id="s2", total_firings=100),
        }
        decisions = self.governor.review([change1, change2], records)
        approved = self.governor.get_approved(decisions)
        flagged = self.governor.get_flagged(decisions)

        # s1 (10%) → APPROVED, s2 (18%) → FLAGGED
        assert len(approved) == 1
        assert approved[0].signal_id == "s1"
        assert len(flagged) >= 1

    # ── P0: Structured stability field ──────────────────────────────────

    def test_stability_from_structured_field(self):
        """P0: Governor reads stability from structured field, not evidence string."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.1, change_pct=0.10,
            stability=0.20,  # Below min_stability=0.3
            sharpe=0.5,
            hit_rate=0.60,
            sample_size=100,
        )
        record = _make_performance_record(total_firings=100, sharpe_20=0.5)
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.REJECTED
        assert "Unstable" in decisions[0].reason

    # ── P1: abs(change_pct) ─────────────────────────────────────────────

    def test_abs_change_pct_clamps_negative(self):
        """P1: Negative change_pct with large magnitude must be clamped."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=0.5,
            change_pct=0.50,  # 50% decrease
        )
        record = _make_performance_record(total_firings=100)
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.FLAGGED
        # Should be clamped to max 20%
        assert decisions[0].change.new_value >= 0.8  # 1.0 - 0.2 = 0.8

    # ── P1: Multi-metric quality gate ───────────────────────────────────

    def test_small_change_approved(self):
        """Changes within 15% with good metrics should be approved."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.1, change_pct=0.10,
        )
        record = _make_performance_record(total_firings=100)
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.APPROVED

    def test_negative_sharpe_weight_increase_rejected(self):
        """Cannot increase weight when Sharpe is below floor."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.1, change_pct=0.10,
        )
        record = _make_performance_record(
            total_firings=100,
            sharpe_20=-1.0,  # Below floor of -0.5
        )
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.REJECTED

    def test_low_hit_rate_weight_increase_flagged(self):
        """P1: Weight increase with HR < 52% should be flagged (outlier risk)."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.1, change_pct=0.10,
        )
        record = _make_performance_record(
            total_firings=100,
            sharpe_20=1.5,   # Good Sharpe
            hit_rate_20=0.48,  # Below 52% — outlier-driven
        )
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.FLAGGED
        assert "Hit rate near random" in decisions[0].reason

    def test_insignificant_sharpe_weight_increase_flagged(self):
        """P1: Positive but insignificant Sharpe (t < 1.65) should be flagged."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.1, change_pct=0.10,
        )
        record = _make_performance_record(
            total_firings=50,  # n=50, sharpe=0.15 → t = 0.15 × √50 ≈ 1.06 < 1.65
            sharpe_20=0.15,
            hit_rate_20=0.55,
        )
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.FLAGGED
        assert "significance proxy" in decisions[0].reason

    # ── P2: Downside protection ─────────────────────────────────────────

    def test_strong_signal_reduction_flagged(self):
        """P2: Weight reduction of a strong long-horizon signal should be flagged."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=0.90, change_pct=0.10,
        )
        # Strong HR@60d with sufficient observations → downside protection
        record = _make_performance_record(
            total_firings=120,
            sharpe_20=0.5,
            hit_rate_20=0.55,
        )
        # Override HR@60d to be strong
        record.hit_rate[60] = 0.70

        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.FLAGGED
        assert "Downside protection" in decisions[0].reason

    # ── P2: Hybrid clamp ───────────────────────────────────────────────

    def test_low_value_clamp_uses_absolute_floor(self):
        """P2: Clamping at low old_value should use absolute floor (±0.1)."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=0.3,   # Floor value
            new_value=0.5,   # Would be 66% increase
            change_pct=0.66,
        )
        record = _make_performance_record(total_firings=100)
        decisions = self.governor.review([change], {"test.sig": record})

        # Without absolute floor: max_delta = 0.3 × 0.2 = 0.06 → clamped to 0.36
        # With absolute floor: max_delta = max(0.06, 0.1) = 0.1 → clamped to 0.4
        assert decisions[0].change.new_value == pytest.approx(0.4, abs=0.01)

    # ── Phase 9: Precision fixes ─────────────────────────────────────────

    def test_clamped_change_pct_is_signed_correctly(self):
        """Clamped change_pct must reflect actual clamped delta, not max_change_pct."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=0.5,
            change_pct=0.50,  # 50% decrease, will be clamped
        )
        record = _make_performance_record(total_firings=100)
        decisions = self.governor.review([change], {"test.sig": record})

        clamped = decisions[0].change
        # clamped.new_value should be 0.8 (1.0 - 0.2), pct = -0.2 (signed)
        assert clamped.change_pct == pytest.approx(-0.20, abs=0.01)

    def test_half_life_uses_own_delta_floor(self):
        """Half-life parameter should use floor=1.0 day, not weight's 0.1."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.HALF_LIFE,
            old_value=3.0,    # Small half-life
            new_value=10.0,   # 233% increase
            change_pct=2.33,
        )
        record = _make_performance_record(total_firings=100)
        decisions = self.governor.review([change], {"test.sig": record})

        clamped = decisions[0].change
        # half_life limits: max_change_pct=0.20, floor=1.0
        # max_delta = max(3.0 × 0.20, 1.0) = max(0.6, 1.0) = 1.0
        # clamped = 3.0 + 1.0 = 4.0
        assert clamped.new_value == pytest.approx(4.0, abs=0.01)

    def test_threshold_uses_stricter_max_change(self):
        """Threshold parameter uses 15% max change (stricter than weight's 20%)."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.THRESHOLD,
            old_value=20.0, new_value=30.0,
            change_pct=0.50,  # 50% increase
        )
        record = _make_performance_record(total_firings=100)
        decisions = self.governor.review([change], {"test.sig": record})

        clamped = decisions[0].change
        # threshold limits: max_change_pct=0.15, floor=0.5
        # max_delta = max(20.0 × 0.15, 0.5) = max(3.0, 0.5) = 3.0
        # clamped = 20.0 + 3.0 = 23.0
        assert clamped.new_value == pytest.approx(23.0, abs=0.1)

    def test_low_sample_regime_flagged(self):
        """Changes from low-sample regimes should be flagged."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.1, change_pct=0.10,
            regime="bear",
            sample_size=10,  # Below min_regime_sample=20
        )
        record = _make_performance_record(total_firings=100)
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.FLAGGED
        assert "Low-confidence regime" in decisions[0].reason

    def test_significance_proxy_reason_text(self):
        """Reason text should say 'significance proxy', not 't-stat'."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.1, change_pct=0.10,
        )
        record = _make_performance_record(
            total_firings=50,
            sharpe_20=0.15,
            hit_rate_20=0.55,
        )
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.FLAGGED
        assert "significance proxy" in decisions[0].reason
        assert "t-stat" not in decisions[0].reason
        assert "t=" not in decisions[0].reason

    # ── Existing tests (unchanged) ─────────────────────────────────────

    def test_insufficient_observations_rejected(self):
        """Should reject if insufficient observations."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.1, change_pct=0.10,
        )
        record = _make_performance_record(total_firings=20)  # < 50
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.REJECTED

    # ── Phase 12: Hardening tests ────────────────────────────────────────

    def test_change_pct_signed_positive(self):
        """Increase: change_pct must be positive."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.1,
        )
        assert change.change_pct > 0
        assert change.change_pct == pytest.approx(0.1, abs=0.001)

    def test_change_pct_signed_negative(self):
        """Decrease: change_pct must be negative."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=0.9,
        )
        assert change.change_pct < 0
        assert change.change_pct == pytest.approx(-0.1, abs=0.001)

    def test_change_pct_always_overwritten(self):
        """Explicit change_pct is ignored — always auto-computed."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.2,
            change_pct=999.0,  # Bogus value
        )
        # Must be overwritten to actual (1.2 - 1.0) / 1.0 = 0.2
        assert change.change_pct == pytest.approx(0.2, abs=0.001)

    def test_unsupported_parameter_rejected(self):
        """Governor must explicitly reject parameter types not in PARAMETER_LIMITS."""
        from src.engines.backtesting.calibration_models import PARAMETER_LIMITS
        # We can't create a ParameterType not in the enum, but we can
        # verify the _SUPPORTED_PARAMETERS frozenset matches PARAMETER_LIMITS keys
        from src.engines.backtesting.calibration_governor import _SUPPORTED_PARAMETERS
        assert _SUPPORTED_PARAMETERS == frozenset(PARAMETER_LIMITS.keys())
        # Verify all enum members that exist are in PARAMETER_LIMITS
        for pt in ParameterType:
            assert pt in _SUPPORTED_PARAMETERS, f"{pt} not in _SUPPORTED_PARAMETERS"

    def test_low_sample_regime_does_not_short_circuit(self):
        """Low-sample regime warning must not skip quality gate checks."""
        # If regime is low-sample AND Sharpe < floor, should be REJECTED (not FLAGGED)
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.1,
            regime="bear",
            sample_size=5,  # Low-sample
        )
        record = _make_performance_record(
            total_firings=100,
            sharpe_20=-1.0,  # Below sharpe_floor=0.0
        )
        decisions = self.governor.review([change], {"test.sig": record})
        # Quality gate (Sharpe floor) should override the regime warning
        assert decisions[0].action == GovernanceAction.REJECTED
        assert "Sharpe gate" in decisions[0].reason

    def test_clamp_preserves_accumulated_warnings(self):
        """Clamped change must include regime warning in reason if present."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=2.0,  # 100% increase → will be clamped
            regime="bear",
            sample_size=5,  # Low-sample warning
        )
        record = _make_performance_record(total_firings=100)
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.FLAGGED
        reason = decisions[0].reason
        assert "Low-confidence regime" in reason
        assert "Clamped" in reason

    def test_change_pct_zero_old_value(self):
        """When old_value is ~0, change_pct should be 0.0 (avoid division by zero)."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.THRESHOLD,
            old_value=0.0, new_value=5.0,
        )
        assert change.change_pct == 0.0

    def test_regime_weight_table_sample_size_is_days(self):
        """RegimeWeightTable.sample_size is trading days (documented)."""
        from src.engines.backtesting.calibration_models import RegimeWeightTable
        rt = RegimeWeightTable(regime="bull", sample_size=250)
        assert rt.sample_size == 250
        # Verify field description mentions trading days
        desc = RegimeWeightTable.model_fields["sample_size"].description
        assert "trading days" in desc


# ─── CalibrationStore Tests ─────────────────────────────────────────────────

class TestCalibrationStore:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = CalibrationStore(store_dir=self.tmpdir)

    def test_save_and_load(self):
        """Round-trip: save a version then load it back."""
        version = CalibrationVersion(
            version="v1.0",
            lookback_days=250,
            universe_name="test",
            universe_size=10,
            signals_calibrated=5,
            signal_configs=[
                CalibratedSignalConfig(signal_id="test.hi", weight=1.5),
                CalibratedSignalConfig(signal_id="test.lo", weight=0.5),
            ],
        )

        path = self.store.save_version(version)
        assert path.exists()

        loaded = self.store.load_version("v1.0")
        assert loaded is not None
        assert loaded.version == "v1.0"
        assert loaded.signals_calibrated == 5
        assert len(loaded.signal_configs) == 2

    def test_load_latest(self):
        """Should load the most recent version."""
        v1 = CalibrationVersion(version="v1.0")
        v2 = CalibrationVersion(version="v1.1")
        self.store.save_version(v1)
        self.store.save_version(v2)

        latest = self.store.load_latest()
        assert latest is not None
        assert latest.version == "v1.1"

    def test_get_history(self):
        """Should list all versions."""
        self.store.save_version(CalibrationVersion(version="v1.0"))
        self.store.save_version(CalibrationVersion(version="v1.1"))
        self.store.save_version(CalibrationVersion(version="v2.0"))

        history = self.store.get_history()
        assert len(history) == 3
        assert history[0][0] == "v1.0"
        assert history[2][0] == "v2.0"

    def test_next_version_tag(self):
        """Should auto-increment version."""
        assert self.store.get_next_version_tag() == "v1.0"

        self.store.save_version(CalibrationVersion(version="v1.0"))
        assert self.store.get_next_version_tag() == "v1.1"

    def test_apply_to_registry(self):
        """Should update registry weights."""
        reg = SignalRegistry()
        sig = _make_signal_def("test.calibrated", weight=1.0)
        reg.register(sig)

        version = CalibrationVersion(
            version="v1.0",
            signal_configs=[
                CalibratedSignalConfig(signal_id="test.calibrated", weight=2.0),
            ],
        )

        updated = self.store.apply_to_registry(version, reg)
        assert updated == 1
        assert reg.get("test.calibrated").weight == 2.0

    def test_missing_version(self):
        """Should return None for missing version."""
        assert self.store.load_version("v99.0") is None


# ─── Registry Enhancement Tests ─────────────────────────────────────────────

class TestRegistryEnhancements:
    def test_update_weight(self):
        reg = SignalRegistry()
        sig = _make_signal_def("test.w", weight=1.0)
        reg.register(sig)

        assert reg.update_weight("test.w", 1.5) is True
        assert reg.get("test.w").weight == 1.5

    def test_update_weight_nonexistent(self):
        reg = SignalRegistry()
        assert reg.update_weight("nonexistent", 1.5) is False

    def test_update_threshold(self):
        reg = SignalRegistry()
        sig = _make_signal_def("test.t", weight=1.0)
        reg.register(sig)

        assert reg.update_threshold("test.t", 20.0) is True
        assert reg.get("test.t").threshold == 20.0

    def test_snapshot_restore(self):
        """Snapshot and restore should round-trip."""
        reg = SignalRegistry()
        sig1 = _make_signal_def("s1", weight=1.0)
        sig2 = _make_signal_def("s2", weight=2.0)
        reg.register(sig1)
        reg.register(sig2)

        snap = reg.snapshot()
        assert "s1" in snap
        assert snap["s1"]["weight"] == 1.0

        # Modify
        reg.update_weight("s1", 5.0)
        assert reg.get("s1").weight == 5.0

        # Restore
        restored = reg.restore(snap)
        assert restored == 2
        assert reg.get("s1").weight == 1.0
