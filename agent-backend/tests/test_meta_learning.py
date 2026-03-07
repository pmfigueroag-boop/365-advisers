"""
tests/test_meta_learning.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Meta-Learning Engine.

Covers:
  - MetaAnalyzer (signal/detector classification)
  - MetaRecommender (decision rules → recommendations)
  - MetaLearningEngine (full pipeline, apply recommendations)
  - Pydantic model contracts
  - DB table definition
"""

from __future__ import annotations

import pytest

from src.engines.meta_learning.analyzer import MetaAnalyzer
from src.engines.meta_learning.recommender import MetaRecommender
from src.engines.meta_learning.engine import MetaLearningEngine
from src.engines.meta_learning.models import (
    DetectorHealthSnapshot,
    MetaLearningConfig,
    MetaLearningReport,
    MetaRecommendation,
    RecommendationType,
    SignalHealthSnapshot,
    TrendDirection,
)


# ─── Analyzer Tests ─────────────────────────────────────────────────────────

class TestAnalyzer:
    """Tests for MetaAnalyzer classification."""

    def test_classify_top_performers(self):
        snapshots = [
            SignalHealthSnapshot(
                signal_id="sig.1", sharpe_current=2.0, sharpe_baseline=1.8,
                sharpe_decline_pct=0.0, hit_rate=0.65, sample_size=50,
            ),
            SignalHealthSnapshot(
                signal_id="sig.2", sharpe_current=0.5, sharpe_baseline=0.6,
                sharpe_decline_pct=0.17, hit_rate=0.50, sample_size=30,
            ),
        ]
        cfg = MetaLearningConfig(sharpe_boost_percentile=0.50)
        analyzer = MetaAnalyzer(cfg)
        result = analyzer.classify_signals(snapshots)
        assert len(result["top_performers"]) >= 1
        assert result["top_performers"][0].signal_id == "sig.1"

    def test_classify_degrading(self):
        snapshots = [
            SignalHealthSnapshot(
                signal_id="sig.1", sharpe_current=0.5, sharpe_baseline=1.5,
                sharpe_decline_pct=0.67, sample_size=40,
            ),
        ]
        analyzer = MetaAnalyzer()
        result = analyzer.classify_signals(snapshots)
        assert len(result["degrading"]) == 1
        assert result["degrading"][0].signal_id == "sig.1"

    def test_classify_insufficient(self):
        snapshots = [
            SignalHealthSnapshot(
                signal_id="sig.1", sharpe_current=1.0, sample_size=5,
            ),
        ]
        analyzer = MetaAnalyzer(MetaLearningConfig(min_sample_size=20))
        result = analyzer.classify_signals(snapshots)
        assert len(result["insufficient"]) == 1

    def test_classify_detectors_promoted(self):
        snapshots = [
            DetectorHealthSnapshot(
                detector_type="momentum", accuracy=0.70,
                total_ideas=20, avg_return=0.03,
            ),
        ]
        analyzer = MetaAnalyzer()
        result = analyzer.classify_detectors(snapshots)
        assert len(result["promoted"]) == 1

    def test_classify_detectors_demoted(self):
        snapshots = [
            DetectorHealthSnapshot(
                detector_type="contrarian", accuracy=0.30,
                total_ideas=15, avg_return=-0.01,
            ),
        ]
        analyzer = MetaAnalyzer()
        result = analyzer.classify_detectors(snapshots)
        assert len(result["demoted"]) == 1

    def test_empty_snapshots(self):
        analyzer = MetaAnalyzer()
        result = analyzer.classify_signals([])
        assert all(len(v) == 0 for v in result.values())


# ─── Recommender Tests ──────────────────────────────────────────────────────

class TestRecommender:
    """Tests for MetaRecommender decision rules."""

    def test_boost_recommendation(self):
        signal_classes = {
            "top_performers": [
                SignalHealthSnapshot(
                    signal_id="sig.1", sharpe_current=2.0,
                    hit_rate=0.7, sample_size=50, current_weight=1.0,
                ),
            ],
            "degrading": [],
            "stable": [],
            "insufficient": [],
        }
        detector_classes = {"promoted": [], "demoted": [], "stable": []}

        recommender = MetaRecommender()
        recs = recommender.generate(signal_classes, detector_classes)
        assert len(recs) == 1
        assert recs[0].recommendation == RecommendationType.BOOST_WEIGHT.value
        assert recs[0].suggested_value > recs[0].current_value

    def test_disable_recommendation(self):
        signal_classes = {
            "top_performers": [],
            "degrading": [
                SignalHealthSnapshot(
                    signal_id="sig.bad", sharpe_current=0.2,
                    sharpe_baseline=1.5, sharpe_decline_pct=0.87,
                    sample_size=40, current_weight=1.0,
                ),
            ],
            "stable": [],
            "insufficient": [],
        }
        detector_classes = {"promoted": [], "demoted": [], "stable": []}

        recommender = MetaRecommender()
        recs = recommender.generate(signal_classes, detector_classes)
        assert len(recs) == 1
        assert recs[0].recommendation == RecommendationType.DISABLE_SIGNAL.value
        assert recs[0].priority == 1

    def test_reduce_weight_recommendation(self):
        signal_classes = {
            "top_performers": [],
            "degrading": [
                SignalHealthSnapshot(
                    signal_id="sig.warn", sharpe_current=0.8,
                    sharpe_baseline=1.5, sharpe_decline_pct=0.47,
                    sample_size=30, current_weight=1.0,
                ),
            ],
            "stable": [],
            "insufficient": [],
        }
        detector_classes = {"promoted": [], "demoted": [], "stable": []}

        recommender = MetaRecommender()
        recs = recommender.generate(signal_classes, detector_classes)
        assert len(recs) == 1
        assert recs[0].recommendation == RecommendationType.REDUCE_WEIGHT.value
        assert recs[0].suggested_value < recs[0].current_value

    def test_detector_promote(self):
        signal_classes = {"top_performers": [], "degrading": [], "stable": [], "insufficient": []}
        detector_classes = {
            "promoted": [
                DetectorHealthSnapshot(
                    detector_type="value", accuracy=0.72, total_ideas=30,
                ),
            ],
            "demoted": [],
            "stable": [],
        }

        recommender = MetaRecommender()
        recs = recommender.generate(signal_classes, detector_classes)
        assert len(recs) == 1
        assert recs[0].recommendation == RecommendationType.PROMOTE_DETECTOR.value

    def test_detector_demote(self):
        signal_classes = {"top_performers": [], "degrading": [], "stable": [], "insufficient": []}
        detector_classes = {
            "promoted": [],
            "demoted": [
                DetectorHealthSnapshot(
                    detector_type="random", accuracy=0.25, total_ideas=20,
                ),
            ],
            "stable": [],
        }

        recommender = MetaRecommender()
        recs = recommender.generate(signal_classes, detector_classes)
        assert len(recs) == 1
        assert recs[0].recommendation == RecommendationType.DEMOTE_DETECTOR.value

    def test_priority_ordering(self):
        signal_classes = {
            "top_performers": [
                SignalHealthSnapshot(signal_id="good", sharpe_current=2.0,
                                    sample_size=50, current_weight=1.0),
            ],
            "degrading": [
                SignalHealthSnapshot(signal_id="bad", sharpe_current=0.1,
                                    sharpe_baseline=1.0, sharpe_decline_pct=0.90,
                                    sample_size=40, current_weight=1.0),
            ],
            "stable": [],
            "insufficient": [],
        }
        detector_classes = {"promoted": [], "demoted": [], "stable": []}

        recommender = MetaRecommender()
        recs = recommender.generate(signal_classes, detector_classes)
        # Priority 1 (urgent) should come first
        assert recs[0].priority <= recs[-1].priority


# ─── Engine Tests ────────────────────────────────────────────────────────────

class TestMetaLearningEngine:
    """Tests for the MetaLearningEngine orchestrator."""

    def test_run_analysis(self):
        engine = MetaLearningEngine()
        report = engine.run_analysis()
        assert isinstance(report, MetaLearningReport)
        assert isinstance(report.signal_health, list)
        assert isinstance(report.detector_health, list)
        assert isinstance(report.recommendations, list)

    def test_apply_dry_run(self):
        recs = [
            MetaRecommendation(
                target_id="sig.1",
                recommendation=RecommendationType.BOOST_WEIGHT.value,
                reason="Test boost",
                current_value=1.0,
                suggested_value=1.3,
                confidence=0.8,
            ),
        ]
        engine = MetaLearningEngine()
        results = engine.apply_recommendations(recs, dry_run=True)
        assert len(results) == 1
        assert results[0]["dry_run"] is True
        assert results[0]["applied"] is False

    def test_apply_no_dry_run(self):
        recs = [
            MetaRecommendation(
                target_id="sig.nonexistent",
                recommendation=RecommendationType.DISABLE_SIGNAL.value,
                reason="Test disable",
                current_value=1.0,
                suggested_value=0.0,
                confidence=0.9,
            ),
        ]
        engine = MetaLearningEngine()
        results = engine.apply_recommendations(recs, dry_run=False)
        assert len(results) == 1


# ─── Model Tests ─────────────────────────────────────────────────────────────

class TestMetaLearningModels:
    """Tests for Pydantic models."""

    def test_config_defaults(self):
        cfg = MetaLearningConfig()
        assert cfg.sharpe_decline_warn == 0.20
        assert cfg.sharpe_decline_critical == 0.40
        assert cfg.boost_multiplier == 1.3
        assert cfg.reduce_multiplier == 0.5

    def test_recommendation_types(self):
        assert len(RecommendationType) == 7

    def test_trend_directions(self):
        assert len(TrendDirection) == 3

    def test_signal_snapshot(self):
        snap = SignalHealthSnapshot(
            signal_id="sig.1", sharpe_current=1.5, hit_rate=0.6,
        )
        d = snap.model_dump()
        assert d["signal_id"] == "sig.1"
        assert d["trend"] == "stable"

    def test_report_serialization(self):
        report = MetaLearningReport(
            total_signals_analyzed=10,
            total_detectors_analyzed=3,
            urgent_actions=2,
        )
        d = report.model_dump()
        assert d["total_signals_analyzed"] == 10
        assert d["urgent_actions"] == 2

    def test_recommendation_serialization(self):
        rec = MetaRecommendation(
            target_id="sig.1",
            recommendation="boost_weight",
            reason="Good performance",
            confidence=0.85,
            priority=3,
        )
        d = rec.model_dump()
        assert d["confidence"] == 0.85


# ─── DB Table Tests ──────────────────────────────────────────────────────────

class TestMetaLearningDatabaseTable:
    """Verify meta_learning_recommendations table exists."""

    def test_table_exists(self):
        from src.data.database import MetaLearningRecord
        assert MetaLearningRecord.__tablename__ == "meta_learning_recommendations"
        cols = {c.name for c in MetaLearningRecord.__table__.columns}
        assert "run_id" in cols
        assert "target_id" in cols
        assert "recommendation" in cols
        assert "reason" in cols
        assert "confidence" in cols
        assert "priority" in cols
        assert "applied" in cols
        assert "suggested_value" in cols
