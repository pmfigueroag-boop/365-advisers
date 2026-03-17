"""
tests/test_institutional.py
--------------------------------------------------------------------------
Tests for AuditTrail, RebalancingEngine, LedoitWolfShrinkage.
"""

from __future__ import annotations

import math
import tempfile
import pytest
from datetime import datetime, timezone
from pathlib import Path

from src.engines.compliance.audit_trail import (
    AuditTrail,
    AuditEntryType,
    AuditEntry,
)
from src.engines.portfolio.rebalancing_engine import (
    RebalancingEngine,
    RebalanceConfig,
    TransitionPlan,
)
from src.engines.portfolio_optimisation.covariance_shrinkage import (
    LedoitWolfShrinkage,
    ShrinkageResult,
)


# ─── AuditTrail Tests ───────────────────────────────────────────────────────

class TestAuditTrail:

    def test_record_decision(self):
        """Records a governance decision."""
        trail = AuditTrail()
        entry = trail.record_decision(
            signal_id="sig.momentum",
            action="APPROVE",
            reason="IC=0.08, PRT=0.15, monotonic",
        )

        assert entry.entry_type == AuditEntryType.GOVERNANCE_DECISION
        assert entry.signal_id == "sig.momentum"
        assert entry.action == "APPROVE"
        assert entry.entry_id.startswith("AUD-")
        assert trail.entry_count == 1

    def test_record_rebalance(self):
        """Records a rebalance with turnover computation."""
        trail = AuditTrail()
        entry = trail.record_rebalance(
            old_weights={"AAPL": 0.30, "MSFT": 0.30, "GOOGL": 0.40},
            new_weights={"AAPL": 0.25, "MSFT": 0.35, "GOOGL": 0.40},
            reason="scheduled_monthly",
        )

        assert entry.entry_type == AuditEntryType.REBALANCE
        assert entry.details["turnover"] == pytest.approx(0.05, abs=0.01)

    def test_hash_chain_valid(self):
        """Hash chain is intact."""
        trail = AuditTrail()
        for i in range(5):
            trail.record_decision(
                signal_id=f"sig.{i}",
                action="APPROVE",
                reason=f"Test {i}",
            )

        is_valid, count = trail.verify_chain()
        assert is_valid is True
        assert count == 5

    def test_hash_chain_tamper_detected(self):
        """Tampering breaks the hash chain."""
        trail = AuditTrail()
        trail.record_decision(signal_id="sig.1", action="APPROVE", reason="ok")
        trail.record_decision(signal_id="sig.2", action="APPROVE", reason="ok")

        # Tamper with first entry
        trail._entries[0].action = "TAMPERED"

        is_valid, idx = trail.verify_chain()
        assert is_valid is False
        assert idx == 0

    def test_query_by_type(self):
        """Query filtered by entry type."""
        trail = AuditTrail()
        trail.record_decision(signal_id="sig.1", action="APPROVE", reason="ok")
        trail.record_rebalance(
            old_weights={"A": 0.5}, new_weights={"A": 0.4}, reason="test",
        )

        result = trail.query(entry_type=AuditEntryType.GOVERNANCE_DECISION)
        assert result.total_count == 1
        assert result.entries[0].signal_id == "sig.1"

    def test_query_by_signal(self):
        """Query filtered by signal ID."""
        trail = AuditTrail()
        trail.record_decision(signal_id="sig.value", action="APPROVE", reason="ok")
        trail.record_decision(signal_id="sig.momentum", action="FLAG", reason="low IC")

        result = trail.query(signal_id="sig.momentum")
        assert result.total_count == 1
        assert result.entries[0].action == "FLAG"

    def test_config_snapshot(self):
        """Config snapshot records full state."""
        trail = AuditTrail()
        entry = trail.record_config_snapshot(
            config={"min_ic": 0.03, "max_sensitivity": 0.50},
            version="2.1.0",
        )

        assert entry.entry_type == AuditEntryType.CONFIG_SNAPSHOT
        assert entry.details["version"] == "2.1.0"

    def test_persistence(self):
        """Entries persisted to JSONL files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trail = AuditTrail(storage_dir=tmpdir)
            trail.record_decision(signal_id="sig.1", action="APPROVE", reason="ok")
            trail.record_decision(signal_id="sig.2", action="FLAG", reason="low IC")

            # Check file exists
            files = list(Path(tmpdir).glob("audit_*.jsonl"))
            assert len(files) == 1

            # Check content
            with open(files[0]) as f:
                lines = f.readlines()
            assert len(lines) == 2


# ─── RebalancingEngine Tests ────────────────────────────────────────────────

class TestRebalancingEngine:

    def test_basic_transition(self):
        """Basic transition computes correct orders."""
        engine = RebalancingEngine()
        plan = engine.compute_transition(
            current={"AAPL": 0.30, "MSFT": 0.30, "GOOGL": 0.40},
            target={"AAPL": 0.25, "MSFT": 0.35, "GOOGL": 0.40},
        )

        assert plan.total_trades >= 2
        assert plan.total_turnover > 0

    def test_new_position(self):
        """New position detected and flagged."""
        engine = RebalancingEngine()
        plan = engine.compute_transition(
            current={"AAPL": 0.50, "MSFT": 0.50},
            target={"AAPL": 0.40, "MSFT": 0.40, "AMZN": 0.20},
        )

        new_orders = [o for o in plan.executable_orders if o.is_new_position]
        assert len(new_orders) >= 1
        assert any(o.ticker == "AMZN" for o in new_orders)
        assert plan.positions_added >= 1

    def test_exit_position(self):
        """Exiting a position detected."""
        config = RebalanceConfig(max_turnover=1.0, cost_threshold_bps=10000.0)
        engine = RebalancingEngine(config=config)
        plan = engine.compute_transition(
            current={"AAPL": 0.30, "MSFT": 0.30, "GOOGL": 0.40},
            target={"AAPL": 0.50, "MSFT": 0.50},
        )

        exits = [o for o in plan.executable_orders if o.is_exit]
        assert len(exits) == 1
        assert exits[0].ticker == "GOOGL"
        assert plan.positions_removed == 1

    def test_turnover_cap(self):
        """Turnover cap enforced."""
        config = RebalanceConfig(max_turnover=0.05)
        engine = RebalancingEngine(config=config)
        plan = engine.compute_transition(
            current={"AAPL": 0.50, "MSFT": 0.50},
            target={"AAPL": 0.10, "MSFT": 0.10, "GOOGL": 0.40, "AMZN": 0.40},
        )

        assert plan.total_turnover <= 0.05 + 0.01  # small tolerance
        assert len(plan.skipped_orders) > 0

    def test_dust_trades_skipped(self):
        """Tiny trades below threshold are skipped."""
        config = RebalanceConfig(min_trade_weight=0.01)
        engine = RebalancingEngine(config=config)
        plan = engine.compute_transition(
            current={"AAPL": 0.500, "MSFT": 0.500},
            target={"AAPL": 0.502, "MSFT": 0.498},  # Δ = 0.002 < 0.01
        )

        assert all(o.is_skipped for o in plan.orders)

    def test_gradual_transition(self):
        """Multi-period transition only moves a fraction."""
        config = RebalanceConfig(transition_periods=3)
        engine = RebalancingEngine(config=config)
        plan = engine.compute_transition(
            current={"AAPL": 0.50, "MSFT": 0.50},
            target={"AAPL": 0.20, "MSFT": 0.80},
        )

        # Transition completion ≈ 1/3
        assert plan.transition_completion < 0.5

    def test_post_rebalance_weights(self):
        """Post-rebalance weights are computed."""
        engine = RebalancingEngine()
        plan = engine.compute_transition(
            current={"AAPL": 0.50, "MSFT": 0.50},
            target={"AAPL": 0.40, "MSFT": 0.60},
        )

        assert "AAPL" in plan.post_rebalance_weights
        assert "MSFT" in plan.post_rebalance_weights

    def test_cost_computed(self):
        """Transaction costs are computed for the plan."""
        engine = RebalancingEngine()
        plan = engine.compute_transition(
            current={"AAPL": 0.50, "MSFT": 0.50},
            target={"AAPL": 0.30, "MSFT": 0.30, "GOOGL": 0.40},
        )

        assert plan.total_cost > 0
        assert plan.total_cost_bps > 0

    def test_identical_weights_no_trades(self):
        """Same weights → no trades."""
        engine = RebalancingEngine()
        plan = engine.compute_transition(
            current={"AAPL": 0.50, "MSFT": 0.50},
            target={"AAPL": 0.50, "MSFT": 0.50},
        )

        assert plan.total_trades == 0


# ─── LedoitWolfShrinkage Tests ──────────────────────────────────────────────

class TestLedoitWolfShrinkage:

    def _sample_cov(self) -> list[list[float]]:
        """3×3 sample covariance matrix."""
        return [
            [0.04, 0.01, 0.005],
            [0.01, 0.09, 0.02],
            [0.005, 0.02, 0.0625],
        ]

    def test_shrinkage_reduces_noise(self):
        """Shrunk matrix differs from sample."""
        result = LedoitWolfShrinkage.shrink(
            self._sample_cov(), n_observations=50,
        )

        assert result.shrinkage_intensity > 0
        assert result.shrinkage_intensity < 1
        assert result.n_assets == 3

    def test_shrunk_matrix_symmetric(self):
        """Shrunk matrix is symmetric."""
        result = LedoitWolfShrinkage.shrink(
            self._sample_cov(), n_observations=30,
        )
        cov = result.shrunk_covariance
        for i in range(3):
            for j in range(3):
                assert cov[i][j] == pytest.approx(cov[j][i], abs=1e-8)

    def test_shrunk_matrix_positive_diagonal(self):
        """Diagonal elements remain positive."""
        result = LedoitWolfShrinkage.shrink(
            self._sample_cov(), n_observations=20,
        )
        for i in range(3):
            assert result.shrunk_covariance[i][i] > 0

    def test_more_data_less_shrinkage(self):
        """More observations → less shrinkage needed."""
        result_few = LedoitWolfShrinkage.shrink(
            self._sample_cov(), n_observations=10,
        )
        result_many = LedoitWolfShrinkage.shrink(
            self._sample_cov(), n_observations=500,
        )

        assert result_few.shrinkage_intensity > result_many.shrinkage_intensity

    def test_identity_target(self):
        """Identity target shrinks off-diag toward zero."""
        result = LedoitWolfShrinkage.shrink(
            self._sample_cov(), n_observations=30, target="identity",
        )

        assert result.target_type == "identity"
        assert result.shrinkage_intensity > 0
        # Off-diag should be reduced
        sample = self._sample_cov()
        shrunk = result.shrunk_covariance
        assert abs(shrunk[0][1]) <= abs(sample[0][1]) + 0.001

    def test_single_asset_passthrough(self):
        """1×1 matrix → no shrinkage (passthrough)."""
        result = LedoitWolfShrinkage.shrink(
            [[0.04]], n_observations=100,
        )
        assert result.shrunk_covariance == [[0.04]]

    def test_constant_correlation_target(self):
        """Default target is constant correlation."""
        result = LedoitWolfShrinkage.shrink(
            self._sample_cov(), n_observations=50,
        )
        assert result.target_type == "constant_correlation"
