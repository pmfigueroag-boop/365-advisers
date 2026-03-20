"""
tests/test_ab_testing.py
─────────────────────────────────────────────────────────────────────────────
Tests for the A/B testing framework.
"""

import pytest
from src.services.ab_testing import (
    ABTestingEngine,
    PromptVariant,
    PromptExperiment,
)


def _make_variants():
    return [
        PromptVariant(name="baseline", prompt_template="You are an analyst v1"),
        PromptVariant(name="concise_v2", prompt_template="Be concise. Analyze:"),
    ]


class TestABTestingEngine:
    """Tests for the A/B testing experiment engine."""

    def setup_method(self):
        self.engine = ABTestingEngine()

    def test_create_experiment(self):
        exp = self.engine.create_experiment("Test", _make_variants())
        assert exp.name == "Test"
        assert exp.status == "active"
        assert len(exp.variants) == 2

    def test_create_experiment_requires_two_variants(self):
        with pytest.raises(ValueError, match="at least 2"):
            self.engine.create_experiment("Bad", [_make_variants()[0]])

    def test_create_experiment_validates_traffic_split(self):
        with pytest.raises(ValueError, match="sum to 1.0"):
            self.engine.create_experiment("Bad", _make_variants(), [0.3, 0.3])

    def test_create_experiment_mismatched_split(self):
        with pytest.raises(ValueError, match="must match"):
            self.engine.create_experiment("Bad", _make_variants(), [0.5])

    def test_select_variant_returns_variant(self):
        exp = self.engine.create_experiment("Test", _make_variants())
        v = self.engine.select_variant(exp.experiment_id)
        assert v is not None
        assert v.name in ("baseline", "concise_v2")

    def test_select_variant_deterministic_with_seed(self):
        exp = self.engine.create_experiment("Test", _make_variants())
        v1 = self.engine.select_variant(exp.experiment_id, seed="AAPL")
        v2 = self.engine.select_variant(exp.experiment_id, seed="AAPL")
        assert v1.variant_id == v2.variant_id

    def test_select_variant_not_found(self):
        assert self.engine.select_variant("nonexistent") is None

    def test_record_outcome(self):
        exp = self.engine.create_experiment("Test", _make_variants())
        v = self.engine.select_variant(exp.experiment_id)
        ok = self.engine.record_outcome(
            exp.experiment_id, v.variant_id,
            latency_ms=1200, tokens_used=500, quality_score=0.8,
        )
        assert ok is True
        assert len(exp.outcomes) == 1

    def test_record_outcome_not_found(self):
        assert self.engine.record_outcome("nonexistent", "v1") is False

    def test_get_results_with_stats(self):
        exp = self.engine.create_experiment("Test", _make_variants())
        v = exp.variants[0]
        for i in range(5):
            self.engine.record_outcome(
                exp.experiment_id, v.variant_id,
                latency_ms=1000 + i * 100, tokens_used=500, quality_score=0.7,
            )
        results = self.engine.get_results(exp.experiment_id)
        assert results is not None
        assert results.total_observations == 5
        stats = [s for s in results.variant_stats if s.variant_id == v.variant_id][0]
        assert stats.observations == 5
        assert stats.avg_quality == 0.7

    def test_complete_experiment(self):
        exp = self.engine.create_experiment("Test", _make_variants())
        v = exp.variants[0]
        for _ in range(10):
            self.engine.record_outcome(
                exp.experiment_id, v.variant_id,
                quality_score=0.9,
            )
        result = self.engine.complete_experiment(exp.experiment_id)
        assert result.status == "completed"
        assert result.winner is not None

    def test_pause_and_resume(self):
        exp = self.engine.create_experiment("Test", _make_variants())
        assert self.engine.pause_experiment(exp.experiment_id) is True
        assert self.engine.select_variant(exp.experiment_id) is None  # Paused
        assert self.engine.resume_experiment(exp.experiment_id) is True
        assert self.engine.select_variant(exp.experiment_id) is not None

    def test_list_experiments(self):
        self.engine.create_experiment("Exp A", _make_variants())
        self.engine.create_experiment("Exp B", _make_variants())
        all_exps = self.engine.list_experiments()
        assert len(all_exps) == 2

    def test_list_experiments_filter_by_status(self):
        exp1 = self.engine.create_experiment("Active", _make_variants())
        exp2 = self.engine.create_experiment("Paused", _make_variants())
        self.engine.pause_experiment(exp2.experiment_id)
        active = self.engine.list_experiments(status="active")
        paused = self.engine.list_experiments(status="paused")
        assert len(active) == 1
        assert len(paused) == 1


class TestPromptVariant:
    """Tests for variant model."""

    def test_variant_has_id(self):
        v = PromptVariant(name="test", prompt_template="hello")
        assert v.variant_id is not None
        assert len(v.variant_id) == 8

    def test_variant_default_model(self):
        v = PromptVariant(name="test", prompt_template="hello")
        assert v.model == "gemini-2.5-pro"


class TestPromptExperiment:
    """Tests for experiment model."""

    def test_experiment_select_variant_random(self):
        exp = PromptExperiment(
            name="Test",
            variants=_make_variants(),
            traffic_split=[0.5, 0.5],
        )
        v = exp.select_variant()
        assert v.name in ("baseline", "concise_v2")

    def test_experiment_select_variant_deterministic(self):
        exp = PromptExperiment(
            name="Test",
            variants=_make_variants(),
            traffic_split=[0.5, 0.5],
        )
        v1 = exp.select_variant(seed="AAPL")
        v2 = exp.select_variant(seed="AAPL")
        assert v1.variant_id == v2.variant_id
