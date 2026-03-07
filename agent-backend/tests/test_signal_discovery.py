"""
tests/test_signal_discovery.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Signal Discovery Engine.

Covers:
  - FeatureGenerator (single, ratio, interaction, zscore candidates)
  - CandidateEvaluator (IC, hit rate, stability, spurious filtering)
  - SignalDiscoveryEngine (full pipeline)
  - Pydantic model contracts
  - DB table definition
"""

from __future__ import annotations

import numpy as np
import pytest

from src.engines.signal_discovery.generator import FeatureGenerator
from src.engines.signal_discovery.evaluator import CandidateEvaluator
from src.engines.signal_discovery.engine import SignalDiscoveryEngine
from src.engines.signal_discovery.models import (
    CandidateSignal,
    CandidateStatus,
    CandidateType,
    DiscoveryConfig,
    DiscoveryReport,
)


# ─── Generator Tests ────────────────────────────────────────────────────────

class TestFeatureGenerator:
    """Tests for feature combination generator."""

    def test_generates_candidates(self):
        gen = FeatureGenerator()
        candidates = gen.generate()
        assert len(candidates) > 0

    def test_single_candidates_created(self):
        gen = FeatureGenerator()
        candidates = gen.generate(
            features=["fundamental.pe_ratio"],
            include_ratios=False, include_interactions=False,
            include_zscores=False,
        )
        assert len(candidates) == 2  # above + below
        types = {c.candidate_type for c in candidates}
        assert types == {CandidateType.SINGLE.value}

    def test_ratio_candidates_created(self):
        gen = FeatureGenerator()
        candidates = gen.generate(
            features=["fundamental.pe_ratio", "fundamental.pb_ratio"],
            include_ratios=True, include_interactions=False,
            include_zscores=False,
        )
        ratio_count = sum(1 for c in candidates if c.candidate_type == CandidateType.RATIO.value)
        assert ratio_count >= 1

    def test_interaction_candidates_created(self):
        gen = FeatureGenerator()
        candidates = gen.generate(
            features=["fundamental.pe_ratio", "technical.rsi_14"],
            include_ratios=False, include_interactions=True,
            include_zscores=False,
        )
        interact_count = sum(
            1 for c in candidates
            if c.candidate_type == CandidateType.INTERACTION.value
        )
        assert interact_count >= 1

    def test_zscore_candidates_created(self):
        gen = FeatureGenerator()
        candidates = gen.generate(
            features=["fundamental.pe_ratio"],
            include_ratios=False, include_interactions=False,
            include_zscores=True,
        )
        zs_count = sum(1 for c in candidates if c.candidate_type == CandidateType.ZSCORE.value)
        assert zs_count == 1

    def test_max_candidates_limit(self):
        cfg = DiscoveryConfig(max_candidates=10)
        gen = FeatureGenerator(cfg)
        candidates = gen.generate()
        assert len(candidates) <= 10

    def test_deterministic_ids(self):
        gen = FeatureGenerator()
        c1 = gen.generate(features=["fundamental.pe_ratio"],
                          include_ratios=False, include_interactions=False,
                          include_zscores=False)
        c2 = gen.generate(features=["fundamental.pe_ratio"],
                          include_ratios=False, include_interactions=False,
                          include_zscores=False)
        assert c1[0].candidate_id == c2[0].candidate_id


# ─── Evaluator Tests ────────────────────────────────────────────────────────

class TestCandidateEvaluator:
    """Tests for candidate evaluation."""

    def test_strong_signal_promoted(self):
        np.random.seed(42)
        n = 200
        # Signal correlated with returns
        values = list(np.random.normal(0, 1, n))
        returns = [v * 0.02 + np.random.normal(0, 0.005) for v in values]

        candidate = CandidateSignal(
            candidate_id="test_strong", name="test",
            feature_formula="test.feature",
        )

        cfg = DiscoveryConfig(
            min_ic=0.02, min_hit_rate=0.50, min_stability=0.0,
            min_sample_size=10, use_bonferroni=False,
        )
        evaluator = CandidateEvaluator()
        result = evaluator.evaluate(
            [candidate], {"test_strong": values}, returns, cfg,
        )
        assert result[0].information_coefficient > 0
        assert result[0].status == CandidateStatus.PROMOTED.value

    def test_weak_signal_rejected(self):
        np.random.seed(42)
        n = 100
        values = list(np.random.normal(0, 1, n))
        returns = list(np.random.normal(0, 0.01, n))  # no correlation

        candidate = CandidateSignal(
            candidate_id="test_weak", name="noise",
        )

        cfg = DiscoveryConfig(
            min_ic=0.10, min_hit_rate=0.55,
            min_sample_size=10, use_bonferroni=True,
        )
        evaluator = CandidateEvaluator()
        result = evaluator.evaluate(
            [candidate], {"test_weak": values}, returns, cfg,
        )
        assert result[0].status == CandidateStatus.REJECTED.value

    def test_insufficient_samples_rejected(self):
        candidate = CandidateSignal(candidate_id="test_small")
        cfg = DiscoveryConfig(min_sample_size=50)
        evaluator = CandidateEvaluator()
        result = evaluator.evaluate(
            [candidate], {"test_small": [1.0, 2.0]}, [0.01, 0.02], cfg,
        )
        assert result[0].status == CandidateStatus.REJECTED.value

    def test_bonferroni_correction(self):
        np.random.seed(42)
        n = 100
        candidates = []
        signal_vals = {}
        for i in range(10):
            cid = f"cand_{i}"
            candidates.append(CandidateSignal(candidate_id=cid))
            signal_vals[cid] = list(np.random.normal(0, 1, n))

        returns = list(np.random.normal(0, 0.01, n))
        cfg = DiscoveryConfig(min_sample_size=10, use_bonferroni=True)
        evaluator = CandidateEvaluator()
        result = evaluator.evaluate(candidates, signal_vals, returns, cfg)

        # All adjusted p-values should be >= original
        for c in result:
            assert c.adjusted_p_value >= c.p_value

    def test_rank_ic_perfect_correlation(self):
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        ic = CandidateEvaluator._rank_ic(x, y)
        assert ic == pytest.approx(1.0, abs=0.01)

    def test_rank_ic_inverse_correlation(self):
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
        ic = CandidateEvaluator._rank_ic(x, y)
        assert ic == pytest.approx(-1.0, abs=0.01)


# ─── Engine Tests ────────────────────────────────────────────────────────────

class TestSignalDiscoveryEngine:
    """Tests for full pipeline."""

    def test_discover_empty_data(self):
        engine = SignalDiscoveryEngine()
        report = engine.discover({}, [])
        assert isinstance(report, DiscoveryReport)
        assert report.total_generated > 0
        assert report.total_promoted == 0

    def test_discover_from_candidates(self):
        np.random.seed(42)
        n = 200
        candidates = [
            CandidateSignal(candidate_id="c1", name="good"),
            CandidateSignal(candidate_id="c2", name="bad"),
        ]
        vals = list(np.random.normal(0, 1, n))
        signal_values = {
            "c1": vals,
            "c2": list(np.random.normal(0, 1, n)),
        }
        returns = [v * 0.02 + np.random.normal(0, 0.005) for v in vals]

        cfg = DiscoveryConfig(
            min_ic=0.02, min_hit_rate=0.50, min_stability=0.0,
            min_sample_size=10, use_bonferroni=False,
        )
        engine = SignalDiscoveryEngine(cfg)
        report = engine.discover_from_candidates(
            candidates, signal_values, returns,
        )
        assert report.total_evaluated == 2


# ─── Model Tests ─────────────────────────────────────────────────────────────

class TestSignalDiscoveryModels:
    """Tests for Pydantic models."""

    def test_config_defaults(self):
        cfg = DiscoveryConfig()
        assert cfg.min_ic == 0.03
        assert cfg.min_hit_rate == 0.52
        assert cfg.min_stability == 0.50
        assert cfg.max_candidates == 500

    def test_candidate_type_enum(self):
        assert len(CandidateType) == 4

    def test_candidate_status_enum(self):
        assert len(CandidateStatus) == 3

    def test_candidate_serialization(self):
        c = CandidateSignal(
            candidate_id="c1", name="test",
            information_coefficient=0.05, hit_rate=0.55,
        )
        d = c.model_dump()
        assert d["information_coefficient"] == 0.05

    def test_report_serialization(self):
        report = DiscoveryReport(
            total_generated=100, total_promoted=5, total_rejected=95,
        )
        d = report.model_dump()
        assert d["total_promoted"] == 5


# ─── DB Table Tests ──────────────────────────────────────────────────────────

class TestSignalDiscoveryDatabaseTable:
    """Verify signal_candidates table exists."""

    def test_table_exists(self):
        from src.data.database import SignalCandidateRecord
        assert SignalCandidateRecord.__tablename__ == "signal_candidates"
        cols = {c.name for c in SignalCandidateRecord.__table__.columns}
        assert "run_id" in cols
        assert "candidate_id" in cols
        assert "feature_formula" in cols
        assert "information_coefficient" in cols
        assert "hit_rate" in cols
        assert "stability" in cols
        assert "adjusted_p_value" in cols
        assert "status" in cols
