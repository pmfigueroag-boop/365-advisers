"""
tests/test_allocation_learning.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Reinforcement-Style Allocation Learning Engine.

Covers:
  - RewardComputer (positive/negative/zero vol)
  - UCB1Bandit (exploration, exploitation, UCB formula, reset)
  - AllocationLearningEngine (full pipeline, cold start)
  - Pydantic model contracts
  - DB table definition
"""

from __future__ import annotations

import math

import pytest

from src.engines.allocation_learning.reward import RewardComputer
from src.engines.allocation_learning.bandit import UCB1Bandit
from src.engines.allocation_learning.engine import AllocationLearningEngine
from src.engines.allocation_learning.models import (
    AllocationConfig,
    AllocationOutcome,
    AllocationReport,
    BucketState,
)


# ─── Reward Tests ────────────────────────────────────────────────────────────

class TestRewardComputer:
    """Tests for the reward computer."""

    def test_positive_return_positive_reward(self):
        rc = RewardComputer()
        outcome = AllocationOutcome(
            ticker="AAPL", bucket_id="medium",
            allocation_pct=0.03, forward_return=0.05,
            volatility=0.02, max_drawdown=0.01,
        )
        reward = rc.compute(outcome)
        assert reward > 0

    def test_negative_return_negative_reward(self):
        rc = RewardComputer()
        outcome = AllocationOutcome(
            ticker="AAPL", bucket_id="medium",
            allocation_pct=0.03, forward_return=-0.05,
            volatility=0.02, max_drawdown=0.03,
        )
        reward = rc.compute(outcome)
        assert reward < 0

    def test_zero_vol_uses_epsilon(self):
        rc = RewardComputer()
        outcome = AllocationOutcome(
            ticker="AAPL", bucket_id="small",
            allocation_pct=0.02, forward_return=0.01,
            volatility=0.0, max_drawdown=0.0,
        )
        reward = rc.compute(outcome)
        assert math.isfinite(reward)

    def test_larger_return_larger_reward(self):
        rc = RewardComputer()
        small = AllocationOutcome(
            ticker="AAPL", bucket_id="small",
            forward_return=0.01, volatility=0.02, max_drawdown=0.01,
        )
        large = AllocationOutcome(
            ticker="AAPL", bucket_id="small",
            forward_return=0.05, volatility=0.02, max_drawdown=0.01,
        )
        assert rc.compute(large) > rc.compute(small)


# ─── UCB1 Bandit Tests ──────────────────────────────────────────────────────

class TestUCB1Bandit:
    """Tests for the multi-armed bandit."""

    def test_unexplored_arm_recommended_first(self):
        cfg = AllocationConfig(min_observations=5)
        bandit = UCB1Bandit(cfg)
        # All arms unexplored → first arm returned
        rec, _ = bandit.recommend()
        assert rec in cfg.bucket_names

    def test_exploration_phase(self):
        cfg = AllocationConfig(min_observations=3)
        bandit = UCB1Bandit(cfg)
        # Feed 2 observations to "micro" — still under min
        bandit.update("micro", 1.0)
        bandit.update("micro", 0.5)
        # Should still recommend an unexplored arm
        rec, _ = bandit.recommend()
        # micro has 2 < 3, so it or another unexplored arm is recommended
        assert rec in cfg.bucket_names

    def test_exploitation_after_warmup(self):
        cfg = AllocationConfig(min_observations=2)
        bandit = UCB1Bandit(cfg)
        # Give all arms minimum observations
        for name in cfg.bucket_names:
            bandit.update(name, 0.1)
            bandit.update(name, 0.1)

        # Give "large" a much better reward
        for _ in range(10):
            bandit.update("large", 5.0)

        rec, _ = bandit.recommend()
        assert rec == "large"

    def test_ucb_score_finite(self):
        cfg = AllocationConfig()
        bandit = UCB1Bandit(cfg)
        bandit.update("medium", 1.0)
        states = bandit.get_states()
        for s in states:
            if s.bucket_id == "medium":
                assert math.isfinite(s.ucb_score)

    def test_reset(self):
        bandit = UCB1Bandit()
        bandit.update("micro", 1.0)
        bandit.reset()
        for s in bandit.get_states():
            assert s.total_pulls == 0

    def test_unknown_bucket_ignored(self):
        bandit = UCB1Bandit()
        bandit.update("nonexistent", 1.0)  # should not crash
        assert sum(s.total_pulls for s in bandit.get_states()) == 0

    def test_best_worst_return_tracked(self):
        bandit = UCB1Bandit()
        bandit.update("medium", 1.0, forward_return=0.05)
        bandit.update("medium", -0.5, forward_return=-0.02)
        states = {s.bucket_id: s for s in bandit.get_states()}
        assert states["medium"].best_return == 0.05
        assert states["medium"].worst_return == -0.02


# ─── Engine Tests ────────────────────────────────────────────────────────────

class TestAllocationLearningEngine:
    """Tests for full pipeline."""

    def test_cold_start_recommendation(self):
        engine = AllocationLearningEngine()
        rec_bucket, rec_alloc = engine.recommend()
        assert rec_bucket in AllocationConfig().bucket_names

    def test_process_outcomes(self):
        engine = AllocationLearningEngine()
        outcomes = [
            AllocationOutcome(
                ticker="AAPL", bucket_id="medium",
                allocation_pct=0.03, forward_return=0.04,
                volatility=0.02, max_drawdown=0.01,
            ),
            AllocationOutcome(
                ticker="MSFT", bucket_id="small",
                allocation_pct=0.02, forward_return=-0.01,
                volatility=0.015, max_drawdown=0.02,
            ),
        ]
        report = engine.process_outcomes(outcomes)
        assert isinstance(report, AllocationReport)
        assert report.total_observations == 2
        assert report.recommended_bucket != ""

    def test_learning_improves(self):
        engine = AllocationLearningEngine(AllocationConfig(min_observations=1))

        # Train "large" with consistent good outcomes
        for _ in range(20):
            engine.process_outcomes([
                AllocationOutcome(
                    ticker="AAPL", bucket_id="large",
                    forward_return=0.08, volatility=0.02, max_drawdown=0.01,
                ),
            ])

        # Train others with bad outcomes
        for name in ["micro", "small", "medium", "concentrated"]:
            for _ in range(5):
                engine.process_outcomes([
                    AllocationOutcome(
                        ticker="AAPL", bucket_id=name,
                        forward_return=-0.02, volatility=0.03, max_drawdown=0.05,
                    ),
                ])

        rec, _ = engine.recommend()
        assert rec == "large"

    def test_reset(self):
        engine = AllocationLearningEngine()
        engine.process_outcomes([
            AllocationOutcome(
                ticker="AAPL", bucket_id="micro",
                forward_return=0.01,
            ),
        ])
        engine.reset()
        states = engine.get_states()
        assert all(s.total_pulls == 0 for s in states)


# ─── Model Tests ─────────────────────────────────────────────────────────────

class TestAllocationLearningModels:
    """Tests for Pydantic models."""

    def test_config_defaults(self):
        cfg = AllocationConfig()
        assert len(cfg.buckets) == 5
        assert len(cfg.bucket_names) == 5
        assert cfg.ucb_c == pytest.approx(1.41, abs=0.01)

    def test_outcome_model(self):
        o = AllocationOutcome(
            ticker="AAPL", bucket_id="large",
            allocation_pct=0.05, forward_return=0.03,
        )
        d = o.model_dump()
        assert d["ticker"] == "AAPL"

    def test_bucket_state_serialization(self):
        s = BucketState(
            bucket_id="medium", allocation_pct=0.03,
            total_pulls=10, avg_reward=1.5,
        )
        d = s.model_dump()
        assert d["total_pulls"] == 10

    def test_report_serialization(self):
        report = AllocationReport(
            recommended_bucket="large",
            recommended_allocation=0.05,
            total_observations=50,
        )
        d = report.model_dump()
        assert d["recommended_bucket"] == "large"


# ─── DB Table Tests ──────────────────────────────────────────────────────────

class TestAllocationLearningDatabaseTable:
    """Verify allocation_learning_outcomes table exists."""

    def test_table_exists(self):
        from src.data.database import AllocationLearningRecord
        assert AllocationLearningRecord.__tablename__ == "allocation_learning_outcomes"
        cols = {c.name for c in AllocationLearningRecord.__table__.columns}
        assert "run_id" in cols
        assert "ticker" in cols
        assert "bucket_id" in cols
        assert "allocation_pct" in cols
        assert "forward_return" in cols
        assert "reward" in cols
        assert "ucb_score" in cols
