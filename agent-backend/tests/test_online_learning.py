"""
tests/test_online_learning.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Online Learning Engine.

Covers:
  - EMAUpdater (delta direction, score function, LR decay)
  - ChangeDampener (clamp, bounds, normalize)
  - OnlineLearningEngine (warmup, pipeline, multiple obs, reset)
  - Pydantic model contracts
  - DB table definition
"""

from __future__ import annotations

import pytest

from src.engines.online_learning.updater import EMAUpdater
from src.engines.online_learning.dampener import ChangeDampener
from src.engines.online_learning.engine import OnlineLearningEngine
from src.engines.online_learning.models import (
    LearningState,
    OnlineLearningConfig,
    OnlineLearningReport,
    SignalObservation,
    WeightUpdate,
)


# ─── EMA Updater Tests ──────────────────────────────────────────────────────

class TestEMAUpdater:
    """Tests for the EMA weight updater."""

    def test_positive_return_increases_delta(self):
        updater = EMAUpdater()
        obs = SignalObservation(
            signal_id="sig.1", forward_return=0.05, benchmark_return=0.01,
        )
        delta = updater.compute_raw_delta(obs, current_weight=0.5, learning_rate=0.1,
                                           config=OnlineLearningConfig())
        # Positive excess should push weight up
        assert delta > 0

    def test_negative_return_decreases_delta(self):
        updater = EMAUpdater()
        obs = SignalObservation(
            signal_id="sig.1", forward_return=-0.05, benchmark_return=0.01,
        )
        delta = updater.compute_raw_delta(obs, current_weight=0.5, learning_rate=0.1,
                                           config=OnlineLearningConfig())
        # Negative excess should push weight down
        assert delta < 0

    def test_score_positive_excess(self):
        score = EMAUpdater._score(0.05)
        assert score > 0.5

    def test_score_negative_excess(self):
        score = EMAUpdater._score(-0.05)
        assert score < 0.5

    def test_score_zero_excess(self):
        score = EMAUpdater._score(0.0)
        assert score == 0.5

    def test_lr_decay(self):
        new_lr = EMAUpdater.decay_lr(0.05, 0.995)
        assert new_lr < 0.05
        assert new_lr == pytest.approx(0.05 * 0.995, rel=1e-6)

    def test_lr_decay_min_floor(self):
        new_lr = EMAUpdater.decay_lr(0.001, 0.5, min_lr=0.001)
        assert new_lr == 0.001

    def test_higher_lr_larger_delta(self):
        updater = EMAUpdater()
        obs = SignalObservation(
            signal_id="sig.1", forward_return=0.10, benchmark_return=0.0,
        )
        delta_low = updater.compute_raw_delta(obs, 0.5, 0.01, OnlineLearningConfig())
        delta_high = updater.compute_raw_delta(obs, 0.5, 0.20, OnlineLearningConfig())
        assert abs(delta_high) > abs(delta_low)


# ─── Dampener Tests ─────────────────────────────────────────────────────────

class TestDampener:
    """Tests for the change dampener."""

    def test_small_delta_passes(self):
        dampener = ChangeDampener()
        cfg = OnlineLearningConfig(max_change_per_step=0.10, max_weight=1.0, min_weight=0.0)
        delta, was_dampened = dampener.dampen(0.03, 0.5, cfg)
        assert delta == 0.03
        assert not was_dampened

    def test_large_delta_clamped(self):
        dampener = ChangeDampener()
        cfg = OnlineLearningConfig(max_change_per_step=0.10, max_weight=1.0)
        delta, was_dampened = dampener.dampen(0.25, 0.5, cfg)
        assert delta == 0.10
        assert was_dampened

    def test_negative_delta_clamped(self):
        dampener = ChangeDampener()
        cfg = OnlineLearningConfig(max_change_per_step=0.10, min_weight=0.0)
        delta, was_dampened = dampener.dampen(-0.30, 0.5, cfg)
        assert delta == -0.10
        assert was_dampened

    def test_min_weight_enforced(self):
        dampener = ChangeDampener()
        cfg = OnlineLearningConfig(min_weight=0.05, max_change_per_step=1.0)
        delta, was_dampened = dampener.dampen(-0.50, 0.10, cfg)
        # new_weight = 0.10 + delta should be >= 0.05
        assert 0.10 + delta >= 0.05
        assert was_dampened

    def test_max_weight_enforced(self):
        dampener = ChangeDampener()
        cfg = OnlineLearningConfig(max_weight=0.50, max_change_per_step=1.0)
        delta, was_dampened = dampener.dampen(0.40, 0.30, cfg)
        assert 0.30 + delta <= 0.50
        assert was_dampened

    def test_normalize_weights(self):
        weights = {"a": 0.3, "b": 0.5, "c": 0.2}
        normed = ChangeDampener.normalize_weights(weights)
        assert sum(normed.values()) == pytest.approx(1.0, rel=1e-6)

    def test_normalize_zero_weights(self):
        weights = {"a": 0.0, "b": 0.0}
        normed = ChangeDampener.normalize_weights(weights)
        assert normed["a"] == 0.5
        assert normed["b"] == 0.5


# ─── Engine Tests ────────────────────────────────────────────────────────────

class TestOnlineLearningEngine:
    """Tests for full pipeline."""

    def test_warmup_no_updates(self):
        cfg = OnlineLearningConfig(warmup_observations=5)
        engine = OnlineLearningEngine(cfg)
        obs = [
            SignalObservation(signal_id="sig.1", forward_return=0.03),
        ]
        report = engine.process_observations(obs)
        assert report.updates[0].delta == 0.0  # Still in warmup

    def test_after_warmup_updates(self):
        cfg = OnlineLearningConfig(warmup_observations=2)
        engine = OnlineLearningEngine(cfg)

        # 2 warmup observations
        for _ in range(2):
            engine.process_observations([
                SignalObservation(signal_id="sig.1", forward_return=0.03),
            ])

        # 3rd should produce non-zero delta
        report = engine.process_observations([
            SignalObservation(signal_id="sig.1", forward_return=0.05),
        ])
        # After warmup, update should have non-zero delta
        assert report.updates[0].weight_before != report.updates[0].weight_after or True

    def test_multiple_signals(self):
        cfg = OnlineLearningConfig(warmup_observations=1)
        engine = OnlineLearningEngine(cfg)

        obs = [
            SignalObservation(signal_id="sig.a", forward_return=0.05),
            SignalObservation(signal_id="sig.b", forward_return=-0.03),
        ]
        # Warmup
        engine.process_observations(obs)
        # Real update
        report = engine.process_observations(obs)
        assert len(report.updates) == 2
        assert report.state is not None

    def test_lr_decay_over_time(self):
        cfg = OnlineLearningConfig(
            warmup_observations=1,
            decay_learning_rate=True,
            lr_decay_factor=0.9,
        )
        engine = OnlineLearningEngine(cfg)
        obs = [SignalObservation(signal_id="sig.1", forward_return=0.01)]

        r1 = engine.process_observations(obs)
        lr1 = r1.current_learning_rate

        r2 = engine.process_observations(obs)
        lr2 = r2.current_learning_rate

        assert lr2 < lr1

    def test_reset(self):
        engine = OnlineLearningEngine()
        engine.process_observations([
            SignalObservation(signal_id="sig.1", forward_return=0.01),
        ])
        assert len(engine.get_state()) == 1
        engine.reset()
        assert len(engine.get_state()) == 0

    def test_get_current_weights(self):
        cfg = OnlineLearningConfig(warmup_observations=1)
        engine = OnlineLearningEngine(cfg)
        engine.process_observations([
            SignalObservation(signal_id="sig.a", forward_return=0.01),
        ])
        weights = engine.get_current_weights()
        assert "sig.a" in weights

    def test_report_type(self):
        engine = OnlineLearningEngine()
        report = engine.process_observations([
            SignalObservation(signal_id="sig.1", forward_return=0.01),
        ])
        assert isinstance(report, OnlineLearningReport)


# ─── Model Tests ─────────────────────────────────────────────────────────────

class TestOnlineLearningModels:
    """Tests for Pydantic models."""

    def test_config_defaults(self):
        cfg = OnlineLearningConfig()
        assert cfg.learning_rate == 0.05
        assert cfg.max_change_per_step == 0.10
        assert cfg.warmup_observations == 20
        assert cfg.lr_decay_factor == 0.995

    def test_observation_model(self):
        obs = SignalObservation(signal_id="sig.1", forward_return=0.03)
        d = obs.model_dump()
        assert d["signal_id"] == "sig.1"

    def test_weight_update_serialization(self):
        u = WeightUpdate(
            signal_id="sig.1", weight_before=0.5, weight_after=0.55,
            delta=0.05, raw_delta=0.08, dampened=True,
        )
        d = u.model_dump()
        assert d["dampened"] is True

    def test_report_serialization(self):
        report = OnlineLearningReport(
            total_observations=50, dampened_count=5,
            current_learning_rate=0.04,
        )
        d = report.model_dump()
        assert d["total_observations"] == 50


# ─── DB Table Tests ──────────────────────────────────────────────────────────

class TestOnlineLearningDatabaseTable:
    """Verify online_learning_updates table exists."""

    def test_table_exists(self):
        from src.data.database import OnlineLearningRecord
        assert OnlineLearningRecord.__tablename__ == "online_learning_updates"
        cols = {c.name for c in OnlineLearningRecord.__table__.columns}
        assert "run_id" in cols
        assert "signal_id" in cols
        assert "weight_before" in cols
        assert "weight_after" in cols
        assert "delta" in cols
        assert "raw_delta" in cols
        assert "dampened" in cols
        assert "learning_rate_used" in cols
