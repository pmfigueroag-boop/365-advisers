"""
tests/test_calibration_integration.py
--------------------------------------------------------------------------
Integration smoke test: AdaptiveCalibrator → CalibrationGovernor → CalibrationStore

Validates that the full calibration chain produces consistent, governed,
and persistable results after all contract hardening (Phases 10–12).
"""

from __future__ import annotations

import tempfile
import pytest
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

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
    GovernanceDecision,
    ParameterChange,
    ParameterType,
    PARAMETER_LIMITS,
)
from src.engines.backtesting.models import (
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


def _make_record(
    signal_id: str = "test.signal",
    category: str = "value",
    total_firings: int = 100,
    sharpe_20: float = 0.5,
    hit_rate_20: float = 0.55,
) -> SignalPerformanceRecord:
    return SignalPerformanceRecord(
        signal_id=signal_id,
        signal_name=f"Test {signal_id}",
        category=SignalCategory(category),
        total_firings=total_firings,
        total_correct=int(total_firings * hit_rate_20),
        sharpe_ratio={5: 0.3, 20: sharpe_20, 60: sharpe_20 * 0.8},
        hit_rate={5: 0.52, 20: hit_rate_20, 60: hit_rate_20 * 0.95},
        avg_return={5: 0.002, 20: 0.005, 60: 0.010},
    )




# ─── Integration Tests ──────────────────────────────────────────────────────

class TestCalibrationIntegration:
    """Smoke tests for the full calibration → governance → persistence chain."""

    def test_full_chain_calibrate_govern_store(self):
        """
        End-to-end: calibrator produces changes → governor reviews → store persists.

        This is the critical integration test that validates the complete
        calibration pipeline works with hardened contracts.
        """
        # 1. Setup: registry with a signal, performance record
        registry = SignalRegistry()
        sig = _make_signal_def("test.value_signal", weight=1.0, category="value")
        registry.register(sig)

        record = _make_record(
            signal_id="test.value_signal",
            category="value",
            total_firings=100,
            sharpe_20=0.5,
            hit_rate_20=0.55,
        )

        # 2. Calibrate: produce proposed changes with ParameterType enum
        config = CalibrationConfig()
        governor = CalibrationGovernor(config)

        # Create a realistic weight change (small positive)
        change = ParameterChange(
            signal_id="test.value_signal",
            parameter=ParameterType.WEIGHT,
            old_value=1.0,
            new_value=1.08,  # +8% — within limits
            stability=0.65,
            hit_rate=0.55,
            sample_size=100,
            sharpe=0.5,
            evidence="Integration test: Sharpe=+0.50 HR=55% n=100",
        )

        # 3. Verify change_pct was auto-computed (signed)
        assert change.change_pct > 0
        assert change.change_pct == pytest.approx(0.08, abs=0.001)
        assert change.parameter == ParameterType.WEIGHT

        # 4. Governor reviews
        decisions = governor.review(
            [change],
            {"test.value_signal": record},
        )
        assert len(decisions) == 1
        decision = decisions[0]

        # Should be APPROVED (small change, good metrics)
        assert decision.action == GovernanceAction.APPROVED
        assert "passed" in decision.reason

        # 5. Verify extractors
        approved = governor.get_approved(decisions)
        flagged = governor.get_flagged(decisions)
        rejected = governor.get_rejected(decisions)
        assert len(approved) == 1
        assert len(flagged) == 0
        assert len(rejected) == 0

        # 6. Store: persist the calibration version
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CalibrationStore(store_dir=tmpdir)

            version = CalibrationVersion(
                version="v1.0",
                lookback_days=250,
                universe_name="test",
                universe_size=2,
                signals_calibrated=1,
                changes_applied=[decision.change],
                signal_configs=[
                    CalibratedSignalConfig(
                        signal_id="test.value_signal",
                        weight=decision.change.new_value,
                    ),
                ],
            )

            # Save and reload
            path = store.save_version(version)
            assert path.exists()

            loaded = store.load_version("v1.0")
            assert loaded is not None
            assert loaded.signals_calibrated == 1
            assert len(loaded.changes_applied) == 1

            # Verify the persisted change retained ParameterType
            persisted_change = loaded.changes_applied[0]
            assert persisted_change.parameter == ParameterType.WEIGHT
            assert persisted_change.change_pct == pytest.approx(0.08, abs=0.001)
            assert persisted_change.new_value == 1.08

    def test_flagged_change_not_in_approved(self):
        """Governor's get_approved() must never include FLAGGED changes."""
        governor = CalibrationGovernor()
        record = _make_record(total_firings=100, sharpe_20=-0.5)

        # Negative sharpe + weight increase → REJECTED
        change_rejected = ParameterChange(
            signal_id="s1", parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.1,
        )
        # Large change → FLAGGED (clamped)
        change_flagged = ParameterChange(
            signal_id="s2", parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=2.0,  # 100% increase
        )
        # Small change → APPROVED
        change_approved = ParameterChange(
            signal_id="s3", parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.05,
        )

        records = {
            "s1": record,
            "s2": _make_record(signal_id="s2", total_firings=100),
            "s3": _make_record(signal_id="s3", total_firings=100),
        }

        decisions = governor.review(
            [change_rejected, change_flagged, change_approved],
            records,
        )

        approved = governor.get_approved(decisions)
        flagged = governor.get_flagged(decisions)
        rejected = governor.get_rejected(decisions)

        # Only s3 should be approved
        assert len(approved) == 1
        assert approved[0].signal_id == "s3"

        # s2 clamped + flagged
        assert len(flagged) >= 1
        flagged_ids = {c.signal_id for c in flagged}
        assert "s2" in flagged_ids

        # s1 rejected
        assert len(rejected) >= 1
        rejected_ids = {d.change.signal_id for d in rejected}
        assert "s1" in rejected_ids

        # Critical: FLAGGED not in approved
        approved_ids = {c.signal_id for c in approved}
        assert not (approved_ids & flagged_ids)

    def test_governor_rejects_without_evidence(self):
        """Cannot calibrate signal without performance record."""
        governor = CalibrationGovernor()
        change = ParameterChange(
            signal_id="ghost.signal",
            parameter=ParameterType.WEIGHT,
            old_value=1.0, new_value=1.1,
        )

        decisions = governor.review([change], {})  # No records
        assert decisions[0].action == GovernanceAction.REJECTED
        assert "No performance record" in decisions[0].reason

    def test_store_round_trip_preserves_types(self):
        """CalibrationVersion serialization must preserve ParameterType enum."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = CalibrationStore(store_dir=tmpdir)

            change = ParameterChange(
                signal_id="test.sig",
                parameter=ParameterType.HALF_LIFE,
                old_value=30.0,
                new_value=25.0,
                evidence="Decay test",
            )

            version = CalibrationVersion(
                version="v2.0",
                changes_applied=[change],
                changes_rejected=[
                    GovernanceDecision(
                        change=change,
                        action=GovernanceAction.REJECTED,
                        reason="Test rejection",
                    ),
                ],
            )

            store.save_version(version)
            loaded = store.load_version("v2.0")

            assert loaded is not None
            # ParameterType preserved through serialization
            assert loaded.changes_applied[0].parameter == ParameterType.HALF_LIFE
            # Signed change_pct preserved
            assert loaded.changes_applied[0].change_pct < 0  # Decrease
            # GovernanceAction preserved
            assert loaded.changes_rejected[0].action == GovernanceAction.REJECTED

    def test_parameter_limits_cover_all_enum_members(self):
        """Every ParameterType member must have an entry in PARAMETER_LIMITS."""
        for pt in ParameterType:
            assert pt in PARAMETER_LIMITS, (
                f"ParameterType.{pt.name} has no entry in PARAMETER_LIMITS — "
                f"governor will reject it at Rule 0"
            )
