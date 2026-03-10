"""
tests/test_idea_generation.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive test suite for the Idea Generation Engine.

Coverage:
  1. IdeaType enum
  2. GrowthDetector
  3. Category mapping
  4. Detector exports
  5. ScanContext
  6. Engine uniform loop
  7. Deduplication
  8. Ranker
  9. Signal strength range
 10. JobStore
 11. Ticker limits
 12. API contract
 13. ScanContext serialization
 14. Detector field on models
 15. Detector Registry
 16. Confidence model
 17. Metrics / observability
 18. Integration
"""

from __future__ import annotations

import pytest
from src.engines.idea_generation.models import (
    IdeaType,
    ConfidenceLevel,
    SignalStrength,
    SignalDetail,
    DetectorResult,
    IdeaCandidate,
    IdeaScanResult,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. IDEA TYPE ENUM
# ═══════════════════════════════════════════════════════════════════════════════


class TestIdeaType:
    def test_growth_exists(self):
        assert IdeaType.GROWTH.value == "growth"

    def test_all_six_types_present(self):
        expected = {"value", "quality", "growth", "momentum", "reversal", "event"}
        actual = {t.value for t in IdeaType}
        assert actual == expected

    def test_types_are_string_enum(self):
        for t in IdeaType:
            assert isinstance(t.value, str)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. GROWTH DETECTOR
# ═══════════════════════════════════════════════════════════════════════════════


class TestGrowthDetector:
    def test_returns_growth_type_not_value(self):
        from src.engines.idea_generation.detectors.growth_detector import GrowthDetector
        from src.engines.idea_generation.detectors.base import _CATEGORY_TO_IDEA_TYPE
        d = GrowthDetector()
        mapped_type = _CATEGORY_TO_IDEA_TYPE[d.signal_category]
        assert mapped_type == IdeaType.GROWTH

    def test_detector_name(self):
        from src.engines.idea_generation.detectors.growth_detector import GrowthDetector
        d = GrowthDetector()
        assert d.name.lower() == "growth"

    def test_signal_category_is_growth(self):
        from src.engines.idea_generation.detectors.growth_detector import GrowthDetector
        from src.engines.alpha_signals.models import SignalCategory
        d = GrowthDetector()
        assert d.signal_category == SignalCategory.GROWTH


# ═══════════════════════════════════════════════════════════════════════════════
# 3. CATEGORY MAPPING
# ═══════════════════════════════════════════════════════════════════════════════


class TestCategoryMapping:
    def test_growth_is_mapped(self):
        from src.engines.idea_generation.detectors.base import _CATEGORY_TO_IDEA_TYPE
        from src.engines.alpha_signals.models import SignalCategory
        assert _CATEGORY_TO_IDEA_TYPE[SignalCategory.GROWTH] == IdeaType.GROWTH

    def test_macro_is_mapped(self):
        from src.engines.idea_generation.detectors.base import _CATEGORY_TO_IDEA_TYPE
        from src.engines.alpha_signals.models import SignalCategory
        assert _CATEGORY_TO_IDEA_TYPE[SignalCategory.MACRO] == IdeaType.EVENT

    def test_all_signal_categories_covered(self):
        from src.engines.idea_generation.detectors.base import _CATEGORY_TO_IDEA_TYPE
        from src.engines.alpha_signals.models import SignalCategory
        for cat in SignalCategory:
            assert cat in _CATEGORY_TO_IDEA_TYPE, f"{cat} not mapped"

    def test_mapping_values_are_valid_idea_types(self):
        from src.engines.idea_generation.detectors.base import _CATEGORY_TO_IDEA_TYPE
        for v in _CATEGORY_TO_IDEA_TYPE.values():
            assert isinstance(v, IdeaType)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. DETECTOR EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDetectorExports:
    def test_all_detectors_importable(self):
        from src.engines.idea_generation.detectors import __all__
        for name in __all__:
            assert name  # non-empty

    def test_all_list_has_six_entries(self):
        from src.engines.idea_generation.detectors import __all__
        assert len(__all__) == 6

    def test_all_detectors_subclass_base(self):
        from src.engines.idea_generation.detectors.base import BaseDetector
        from src.engines.idea_generation.detectors import (
            ValueDetector, QualityDetector, MomentumDetector,
            ReversalDetector, GrowthDetector, EventDetector,
        )
        for cls in [ValueDetector, QualityDetector, MomentumDetector,
                     ReversalDetector, GrowthDetector, EventDetector]:
            assert issubclass(cls, BaseDetector)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SCAN CONTEXT
# ═══════════════════════════════════════════════════════════════════════════════


class TestScanContext:
    def test_scan_context_creation(self):
        from src.engines.idea_generation.detectors.base import ScanContext
        ctx = ScanContext(previous_score=5.0, current_score=3.0)
        assert ctx.previous_score == 5.0
        assert ctx.current_score == 3.0

    def test_scan_context_defaults(self):
        from src.engines.idea_generation.detectors.base import ScanContext
        ctx = ScanContext()
        assert ctx.previous_score is None
        assert ctx.current_score is None
        assert ctx.extra == {}

    def test_event_detector_accepts_context(self):
        from src.engines.idea_generation.detectors.event_detector import EventDetector
        import inspect
        sig = inspect.signature(EventDetector.scan)
        assert "context" in sig.parameters

    def test_all_detectors_accept_context(self):
        import inspect
        from src.engines.idea_generation.detectors import (
            ValueDetector, QualityDetector, MomentumDetector,
            ReversalDetector, GrowthDetector, EventDetector,
        )
        for cls in [ValueDetector, QualityDetector, MomentumDetector,
                     ReversalDetector, GrowthDetector, EventDetector]:
            sig = inspect.signature(cls.scan)
            assert "context" in sig.parameters, (
                f"{cls.__name__}.scan() missing context parameter"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ENGINE UNIFORM LOOP
# ═══════════════════════════════════════════════════════════════════════════════


class TestEngineUniformLoop:
    def test_engine_has_six_detectors(self):
        from src.engines.idea_generation.engine import IdeaGenerationEngine
        engine = IdeaGenerationEngine()
        assert len(engine.detectors) == 6

    def test_no_separate_event_detector_attr(self):
        from src.engines.idea_generation.engine import IdeaGenerationEngine
        engine = IdeaGenerationEngine()
        assert not hasattr(engine, "event_detector")

    def test_all_detector_types_in_list(self):
        from src.engines.idea_generation.engine import IdeaGenerationEngine
        from src.engines.idea_generation.detectors import (
            ValueDetector, QualityDetector, MomentumDetector,
            ReversalDetector, GrowthDetector, EventDetector,
        )
        engine = IdeaGenerationEngine()
        class_names = {type(d).__name__ for d in engine.detectors}
        expected = {
            "ValueDetector", "QualityDetector", "MomentumDetector",
            "ReversalDetector", "GrowthDetector", "EventDetector",
        }
        assert class_names == expected


# ═══════════════════════════════════════════════════════════════════════════════
# 7. DEDUPLICATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeduplication:
    """Verify aggregator deduplication preserves distinct idea types and detectors."""

    def _make_candidate(
        self, ticker: str, idea_type: IdeaType,
        strength: float = 0.5, source: str = "legacy",
        detector: str = "unknown",
    ) -> IdeaCandidate:
        return IdeaCandidate(
            ticker=ticker,
            name=f"{ticker} Test",
            sector="Test",
            idea_type=idea_type,
            confidence=ConfidenceLevel.MEDIUM,
            signal_strength=strength,
            signals=[],
            detector=detector,
            metadata={"source": source},
        )

    def test_growth_and_value_coexist(self):
        from src.engines.idea_generation.distributed.aggregator import ResultAggregator
        ideas = [
            self._make_candidate("AAPL", IdeaType.VALUE, 0.6, detector="value"),
            self._make_candidate("AAPL", IdeaType.GROWTH, 0.7, detector="growth"),
        ]
        deduped = ResultAggregator._deduplicate(ideas)
        assert len(deduped) == 2

    def test_genuine_duplicates_consolidated(self):
        from src.engines.idea_generation.distributed.aggregator import ResultAggregator
        ideas = [
            self._make_candidate("AAPL", IdeaType.VALUE, 0.5, detector="value"),
            self._make_candidate("AAPL", IdeaType.VALUE, 0.8, detector="value"),
        ]
        deduped = ResultAggregator._deduplicate(ideas)
        assert len(deduped) == 1
        assert deduped[0].signal_strength == 0.8

    def test_different_sources_preserved(self):
        from src.engines.idea_generation.distributed.aggregator import ResultAggregator
        ideas = [
            self._make_candidate("MSFT", IdeaType.VALUE, 0.5, source="legacy", detector="value"),
            self._make_candidate("MSFT", IdeaType.VALUE, 0.6, source="alpha_signals_library", detector="value"),
        ]
        deduped = ResultAggregator._deduplicate(ideas)
        assert len(deduped) == 2

    def test_all_types_survive(self):
        from src.engines.idea_generation.distributed.aggregator import ResultAggregator
        ideas = [
            self._make_candidate("X", t, 0.5, detector=t.value)
            for t in IdeaType
        ]
        deduped = ResultAggregator._deduplicate(ideas)
        assert len(deduped) == 6

    def test_cross_detector_same_type_coexist(self):
        from src.engines.idea_generation.distributed.aggregator import ResultAggregator
        ideas = [
            self._make_candidate("AAPL", IdeaType.VALUE, 0.6, detector="value"),
            self._make_candidate("AAPL", IdeaType.VALUE, 0.7, detector="quality"),
        ]
        deduped = ResultAggregator._deduplicate(ideas)
        assert len(deduped) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 8. RANKER
# ═══════════════════════════════════════════════════════════════════════════════


class TestRanker:
    def test_rank_all_types(self):
        from src.engines.idea_generation.ranker import rank_ideas
        ideas = [
            IdeaCandidate(
                ticker=f"T{i}", idea_type=t,
                confidence=ConfidenceLevel.MEDIUM,
                signal_strength=0.5 + i * 0.05,
                signals=[], detector=t.value,
            )
            for i, t in enumerate(IdeaType)
        ]
        ranked = rank_ideas(ideas)
        assert ranked[0].priority == 1
        assert ranked[-1].priority == len(ideas)

    def test_ranking_is_deterministic(self):
        from src.engines.idea_generation.ranker import rank_ideas
        ideas = [
            IdeaCandidate(
                ticker="A", idea_type=IdeaType.VALUE,
                confidence=ConfidenceLevel.HIGH,
                signal_strength=0.8,
                signals=[], detector="value",
            ),
        ]
        r1 = rank_ideas(list(ideas))
        r2 = rank_ideas(list(ideas))
        assert r1[0].priority == r2[0].priority

    def test_confidence_score_affects_ranking(self):
        """Higher confidence_score should boost ranking over lower."""
        from src.engines.idea_generation.ranker import rank_ideas
        low_conf = IdeaCandidate(
            ticker="A", idea_type=IdeaType.VALUE,
            confidence=ConfidenceLevel.MEDIUM,
            signal_strength=0.7, confidence_score=0.2,
            signals=[], detector="value",
        )
        high_conf = IdeaCandidate(
            ticker="B", idea_type=IdeaType.VALUE,
            confidence=ConfidenceLevel.MEDIUM,
            signal_strength=0.7, confidence_score=0.9,
            signals=[], detector="value",
        )
        ranked = rank_ideas([low_conf, high_conf])
        # high_conf should rank first (priority 1)
        assert ranked[0].ticker == "B"

    def test_alpha_score_component(self):
        """Alpha score from metadata should influence ranking."""
        from src.engines.idea_generation.ranker import rank_ideas
        no_alpha = IdeaCandidate(
            ticker="A", idea_type=IdeaType.VALUE,
            confidence=ConfidenceLevel.MEDIUM,
            signal_strength=0.5, confidence_score=0.5,
            signals=[], detector="value",
        )
        with_alpha = IdeaCandidate(
            ticker="B", idea_type=IdeaType.VALUE,
            confidence=ConfidenceLevel.MEDIUM,
            signal_strength=0.5, confidence_score=0.5,
            signals=[], detector="value",
            metadata={"composite_alpha_score": 0.9},
        )
        ranked = rank_ideas([no_alpha, with_alpha])
        assert ranked[0].ticker == "B"


# ═══════════════════════════════════════════════════════════════════════════════
# 9. SIGNAL STRENGTH RANGE
# ═══════════════════════════════════════════════════════════════════════════════


class TestSignalStrengthRange:
    def test_growth_detector_strength_range(self):
        result = DetectorResult(
            idea_type=IdeaType.GROWTH,
            confidence=ConfidenceLevel.MEDIUM,
            signal_strength=0.75,
            signals=[],
        )
        assert 0.0 <= result.signal_strength <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# 10. JOB STORE
# ═══════════════════════════════════════════════════════════════════════════════


class TestJobStore:
    def test_save_and_get(self):
        from src.engines.idea_generation.distributed.dispatcher import InMemoryJobStore
        from src.engines.idea_generation.distributed.models import ScanJob
        store = InMemoryJobStore()
        job = ScanJob(scan_id="test123")
        store.save(job)
        assert store.get("test123") is not None

    def test_get_missing_returns_none(self):
        from src.engines.idea_generation.distributed.dispatcher import InMemoryJobStore
        store = InMemoryJobStore()
        assert store.get("nonexistent") is None

    def test_list_recent(self):
        from src.engines.idea_generation.distributed.dispatcher import InMemoryJobStore
        from src.engines.idea_generation.distributed.models import ScanJob
        store = InMemoryJobStore()
        for i in range(5):
            store.save(ScanJob(scan_id=f"s{i}"))
        recent = store.list_recent(limit=3)
        assert len(recent) <= 3


# ═══════════════════════════════════════════════════════════════════════════════
# 11. TICKER LIMITS
# ═══════════════════════════════════════════════════════════════════════════════


class TestTickerLimits:
    def test_scan_request_max_500(self):
        from src.routes.ideas import ScanRequest
        req = ScanRequest(tickers=["T"] * 500)
        assert len(req.tickers) == 500

    def test_scan_request_over_500_fails(self):
        from src.routes.ideas import ScanRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ScanRequest(tickers=["T"] * 501)

    def test_distributed_request_max_5000(self):
        from src.routes.ideas import DistributedScanRequest
        req = DistributedScanRequest(tickers=["T"] * 5000)
        assert len(req.tickers) == 5000

    def test_distributed_request_over_5000_fails(self):
        from src.routes.ideas import DistributedScanRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            DistributedScanRequest(tickers=["T"] * 5001)


# ═══════════════════════════════════════════════════════════════════════════════
# 12. API CONTRACT
# ═══════════════════════════════════════════════════════════════════════════════


class TestAPIContract:
    def test_idea_summary_id_is_string(self):
        from src.routes.ideas import IdeaSummary
        schema = IdeaSummary.model_json_schema()
        assert schema["properties"]["id"]["type"] == "string"

    def test_scan_response_schema(self):
        from src.routes.ideas import ScanResponse
        schema = ScanResponse.model_json_schema()
        assert "scan_id" in schema["properties"]
        assert "ideas_found" in schema["properties"]

    def test_idea_summary_has_confidence_score(self):
        from src.routes.ideas import IdeaSummary
        schema = IdeaSummary.model_json_schema()
        assert "confidence_score" in schema["properties"]


# ═══════════════════════════════════════════════════════════════════════════════
# 13. SCAN CONTEXT SERIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestScanContextSerialization:
    def test_round_trip(self):
        from src.engines.idea_generation.detectors.base import ScanContext
        original = ScanContext(previous_score=7.5, current_score=3.2, extra={"key": "val"})
        data = original.to_dict()
        restored = ScanContext.from_dict(data)
        assert restored.previous_score == 7.5
        assert restored.current_score == 3.2
        assert restored.extra == {"key": "val"}

    def test_from_none(self):
        from src.engines.idea_generation.detectors.base import ScanContext
        ctx = ScanContext.from_dict(None)
        assert ctx.previous_score is None

    def test_from_empty_dict(self):
        from src.engines.idea_generation.detectors.base import ScanContext
        ctx = ScanContext.from_dict({})
        assert ctx.previous_score is None
        assert ctx.extra == {}

    def test_to_dict_is_json_safe(self):
        import json
        from src.engines.idea_generation.detectors.base import ScanContext
        ctx = ScanContext(previous_score=1.0, current_score=2.0)
        data = ctx.to_dict()
        serialized = json.dumps(data)
        assert isinstance(serialized, str)


# ═══════════════════════════════════════════════════════════════════════════════
# 14. DETECTOR FIELD ON MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDetectorField:
    def test_detector_result_has_field(self):
        result = DetectorResult(
            idea_type=IdeaType.VALUE, confidence=ConfidenceLevel.HIGH,
            signal_strength=0.8, signals=[], detector="value",
        )
        assert result.detector == "value"

    def test_detector_defaults_empty(self):
        result = DetectorResult(
            idea_type=IdeaType.VALUE, confidence=ConfidenceLevel.HIGH,
            signal_strength=0.8, signals=[],
        )
        assert result.detector == ""

    def test_idea_candidate_has_field(self):
        idea = IdeaCandidate(
            ticker="AAPL", idea_type=IdeaType.GROWTH,
            confidence=ConfidenceLevel.MEDIUM,
            signal_strength=0.7, signals=[], detector="growth",
        )
        assert idea.detector == "growth"

    def test_detector_serializes(self):
        idea = IdeaCandidate(
            ticker="MSFT", idea_type=IdeaType.VALUE,
            confidence=ConfidenceLevel.HIGH,
            signal_strength=0.6, signals=[], detector="value",
        )
        data = idea.model_dump()
        assert data["detector"] == "value"


# ═══════════════════════════════════════════════════════════════════════════════
# 15. DETECTOR REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════


class TestDetectorRegistry:
    """Verify the Detector Registry system."""

    def test_default_registry_has_six_detectors(self):
        from src.engines.idea_generation.detector_registry import default_registry
        assert len(default_registry) == 6

    def test_all_expected_keys_registered(self):
        from src.engines.idea_generation.detector_registry import default_registry
        expected = {"value", "quality", "momentum", "reversal", "growth", "event"}
        actual = {s.key for s in default_registry.list_all()}
        assert actual == expected

    def test_duplicate_key_raises(self):
        from src.engines.idea_generation.detector_registry import (
            DetectorRegistry, DetectorSpec,
        )
        from src.engines.idea_generation.detectors.value_detector import ValueDetector
        reg = DetectorRegistry()
        spec = DetectorSpec(key="value", detector_class=ValueDetector, idea_type=IdeaType.VALUE)
        reg.register(spec)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(spec)

    def test_get_by_key(self):
        from src.engines.idea_generation.detector_registry import default_registry
        spec = default_registry.get_by_key("growth")
        assert spec is not None
        assert spec.idea_type == IdeaType.GROWTH

    def test_get_by_key_missing(self):
        from src.engines.idea_generation.detector_registry import default_registry
        assert default_registry.get_by_key("nonexistent") is None

    def test_get_active_returns_all_enabled(self):
        from src.engines.idea_generation.detector_registry import default_registry
        active = default_registry.get_active()
        assert len(active) == 6

    def test_whitelist_filtering(self):
        from src.engines.idea_generation.detector_registry import default_registry
        active = default_registry.get_active(enabled_keys={"value", "growth"})
        keys = {s.key for s in active}
        assert keys == {"value", "growth"}

    def test_blacklist_filtering(self):
        from src.engines.idea_generation.detector_registry import default_registry
        active = default_registry.get_active(disabled_keys={"event"})
        keys = {s.key for s in active}
        assert "event" not in keys
        assert len(keys) == 5

    def test_priority_ordering(self):
        from src.engines.idea_generation.detector_registry import default_registry
        specs = default_registry.list_all()
        priorities = [s.priority for s in specs]
        assert priorities == sorted(priorities)

    def test_build_active_detectors(self):
        from src.engines.idea_generation.detector_registry import build_active_detectors
        detectors = build_active_detectors()
        assert len(detectors) == 6

    def test_build_subset_detectors(self):
        from src.engines.idea_generation.detector_registry import build_active_detectors
        detectors = build_active_detectors(enabled_keys={"value", "growth"})
        assert len(detectors) == 2
        names = {d.name.lower() for d in detectors}
        assert "value" in names
        assert "growth" in names

    def test_engine_uses_registry(self):
        """Engine should build detectors from registry, not hardcoded list."""
        from src.engines.idea_generation.engine import IdeaGenerationEngine
        engine = IdeaGenerationEngine(detector_keys={"value", "growth"})
        assert len(engine.detectors) == 2

    def test_engine_disable_detector(self):
        from src.engines.idea_generation.engine import IdeaGenerationEngine
        engine = IdeaGenerationEngine(disabled_keys={"event"})
        names = {d.name.lower() for d in engine.detectors}
        assert "event" not in names
        assert len(engine.detectors) == 5

    def test_event_detector_has_requires_context(self):
        from src.engines.idea_generation.detector_registry import default_registry
        spec = default_registry.get_by_key("event")
        assert "requires_context" in spec.capabilities

    def test_contains_operator(self):
        from src.engines.idea_generation.detector_registry import default_registry
        assert "value" in default_registry
        assert "nonexistent" not in default_registry


# ═══════════════════════════════════════════════════════════════════════════════
# 16. CONFIDENCE MODEL
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfidenceModel:
    """Verify confidence_score computation, serialization, and separation."""

    def test_confidence_score_on_detector_result(self):
        result = DetectorResult(
            idea_type=IdeaType.VALUE, confidence=ConfidenceLevel.HIGH,
            signal_strength=0.8, confidence_score=0.75, signals=[],
        )
        assert result.confidence_score == 0.75

    def test_confidence_score_defaults_zero(self):
        result = DetectorResult(
            idea_type=IdeaType.VALUE, confidence=ConfidenceLevel.HIGH,
            signal_strength=0.8, signals=[],
        )
        assert result.confidence_score == 0.0

    def test_confidence_score_on_idea_candidate(self):
        idea = IdeaCandidate(
            ticker="AAPL", idea_type=IdeaType.VALUE,
            confidence=ConfidenceLevel.HIGH,
            signal_strength=0.8, confidence_score=0.9,
            signals=[], detector="value",
        )
        assert idea.confidence_score == 0.9

    def test_confidence_score_serializes(self):
        idea = IdeaCandidate(
            ticker="AAPL", idea_type=IdeaType.VALUE,
            confidence=ConfidenceLevel.HIGH,
            signal_strength=0.8, confidence_score=0.65,
            signals=[], detector="value",
        )
        data = idea.model_dump()
        assert data["confidence_score"] == 0.65

    def test_compute_confidence_all_strong(self):
        """All strong signals should yield high confidence."""
        from src.engines.idea_generation.engine import IdeaGenerationEngine
        result = DetectorResult(
            idea_type=IdeaType.VALUE, confidence=ConfidenceLevel.HIGH,
            signal_strength=0.8,
            signals=[
                SignalDetail(name="s1", value=1.0, threshold=0.5, strength=SignalStrength.STRONG),
                SignalDetail(name="s2", value=0.9, threshold=0.5, strength=SignalStrength.STRONG),
            ],
        )
        score = IdeaGenerationEngine._compute_confidence(result)
        assert score > 0.8  # high confidence for all-strong

    def test_compute_confidence_with_weak(self):
        """Weak signals should penalize confidence."""
        from src.engines.idea_generation.engine import IdeaGenerationEngine
        result = DetectorResult(
            idea_type=IdeaType.VALUE, confidence=ConfidenceLevel.MEDIUM,
            signal_strength=0.6,
            signals=[
                SignalDetail(name="s1", value=0.8, threshold=0.5, strength=SignalStrength.STRONG),
                SignalDetail(name="s2", value=0.3, threshold=0.5, strength=SignalStrength.WEAK),
            ],
        )
        score = IdeaGenerationEngine._compute_confidence(result)
        assert score < 0.8  # penalized by weak signal

    def test_compute_confidence_no_signals(self):
        from src.engines.idea_generation.engine import IdeaGenerationEngine
        result = DetectorResult(
            idea_type=IdeaType.VALUE, confidence=ConfidenceLevel.LOW,
            signal_strength=0.3, signals=[],
        )
        score = IdeaGenerationEngine._compute_confidence(result)
        assert score == 0.0

    def test_confidence_score_range(self):
        """confidence_score must be between 0 and 1."""
        from src.engines.idea_generation.engine import IdeaGenerationEngine
        result = DetectorResult(
            idea_type=IdeaType.VALUE, confidence=ConfidenceLevel.HIGH,
            signal_strength=0.9,
            signals=[
                SignalDetail(name=f"s{i}", value=1.0, threshold=0.5,
                             strength=SignalStrength.STRONG)
                for i in range(10)
            ],
        )
        score = IdeaGenerationEngine._compute_confidence(result)
        assert 0.0 <= score <= 1.0

    def test_three_scores_independent(self):
        """signal_strength, confidence_score, alpha are distinct fields."""
        idea = IdeaCandidate(
            ticker="X", idea_type=IdeaType.VALUE,
            confidence=ConfidenceLevel.HIGH,
            signal_strength=0.9,
            confidence_score=0.4,
            signals=[], detector="value",
            metadata={"composite_alpha_score": 0.7},
        )
        assert idea.signal_strength != idea.confidence_score
        assert idea.confidence_score != idea.metadata["composite_alpha_score"]


# ═══════════════════════════════════════════════════════════════════════════════
# 17. METRICS / OBSERVABILITY
# ═══════════════════════════════════════════════════════════════════════════════


class TestMetrics:
    """Verify the metrics adapter and instrumentation."""

    def test_noop_collector_no_error(self):
        from src.engines.idea_generation.metrics import NoOpCollector
        c = NoOpCollector()
        c.increment("test")
        c.timing("test", 100.0)
        c.gauge("test", 42.0)

    def test_in_memory_collector_increment(self):
        from src.engines.idea_generation.metrics import InMemoryCollector
        c = InMemoryCollector()
        c.increment("ideas_generated_total", tags={"detector": "value"})
        c.increment("ideas_generated_total", tags={"detector": "value"})
        assert c.get("ideas_generated_total", detector="value") == 2

    def test_in_memory_collector_timing(self):
        from src.engines.idea_generation.metrics import InMemoryCollector
        c = InMemoryCollector()
        c.timing("chunk_processing_ms", 150.0, tags={"mode": "distributed"})
        c.timing("chunk_processing_ms", 200.0, tags={"mode": "distributed"})
        timings = c.get_timing("chunk_processing_ms", mode="distributed")
        assert len(timings) == 2
        assert timings[0] == 150.0

    def test_in_memory_collector_gauge(self):
        from src.engines.idea_generation.metrics import InMemoryCollector
        c = InMemoryCollector()
        c.gauge("scan_ideas_total", 42.0, tags={"mode": "local"})
        assert c.get_gauge("scan_ideas_total", mode="local") == 42.0

    def test_in_memory_collector_total(self):
        from src.engines.idea_generation.metrics import InMemoryCollector
        c = InMemoryCollector()
        c.increment("ideas_generated_total", tags={"detector": "value"})
        c.increment("ideas_generated_total", tags={"detector": "growth"})
        c.increment("ideas_generated_total", tags={"detector": "value"})
        assert c.total("ideas_generated_total") == 3

    def test_in_memory_collector_reset(self):
        from src.engines.idea_generation.metrics import InMemoryCollector
        c = InMemoryCollector()
        c.increment("x")
        c.reset()
        assert c.get("x") == 0

    def test_set_and_get_collector(self):
        from src.engines.idea_generation.metrics import (
            set_collector, get_collector, InMemoryCollector, NoOpCollector,
        )
        original = get_collector()
        try:
            mem = InMemoryCollector()
            set_collector(mem)
            assert get_collector() is mem
        finally:
            set_collector(original)

    def test_dedup_emits_metrics(self):
        """Deduplication should emit dedup_rejected_total for removed ideas."""
        from src.engines.idea_generation.metrics import (
            set_collector, get_collector, InMemoryCollector,
        )
        from src.engines.idea_generation.distributed.aggregator import ResultAggregator
        original = get_collector()
        mem = InMemoryCollector()
        set_collector(mem)
        try:
            ideas = [
                IdeaCandidate(
                    ticker="AAPL", idea_type=IdeaType.VALUE,
                    confidence=ConfidenceLevel.MEDIUM,
                    signal_strength=0.5, signals=[],
                    detector="value", metadata={"source": "legacy"},
                ),
                IdeaCandidate(
                    ticker="AAPL", idea_type=IdeaType.VALUE,
                    confidence=ConfidenceLevel.MEDIUM,
                    signal_strength=0.8, signals=[],
                    detector="value", metadata={"source": "legacy"},
                ),
            ]
            deduped = ResultAggregator._deduplicate(ideas)
            assert len(deduped) == 1
            assert mem.get("dedup_rejected_total", idea_type="value", detector="value") == 1
        finally:
            set_collector(original)

    def test_different_tag_combinations(self):
        from src.engines.idea_generation.metrics import InMemoryCollector
        c = InMemoryCollector()
        c.increment("detector_errors_total", tags={"detector": "value", "error_type": "ValueError"})
        c.increment("detector_errors_total", tags={"detector": "growth", "error_type": "KeyError"})
        assert c.get("detector_errors_total", detector="value", error_type="ValueError") == 1
        assert c.get("detector_errors_total", detector="growth", error_type="KeyError") == 1
        assert c.total("detector_errors_total") == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 18. INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestIntegration:
    """Integration tests combining registry, confidence, and metrics."""

    def test_subset_scan_with_metrics(self):
        """Engine with subset of detectors should still work end-to-end."""
        from src.engines.idea_generation.engine import IdeaGenerationEngine
        engine = IdeaGenerationEngine(detector_keys={"value", "growth"})
        assert len(engine.detectors) == 2
        # Verify detector names match registry keys
        names = {d.name.lower() for d in engine.detectors}
        assert names == {"value", "growth"}

    def test_confidence_score_in_scan_result_schema(self):
        """IdeaScanResult should carry ideas with confidence_score."""
        result = IdeaScanResult(
            ideas=[
                IdeaCandidate(
                    ticker="AAPL", idea_type=IdeaType.VALUE,
                    confidence=ConfidenceLevel.HIGH,
                    signal_strength=0.8, confidence_score=0.9,
                    signals=[], detector="value",
                ),
            ],
        )
        assert result.ideas[0].confidence_score == 0.9

    def test_ranker_with_confidence_and_alpha(self):
        """Ranker should consider both confidence and alpha."""
        from src.engines.idea_generation.ranker import rank_ideas
        ideas = [
            IdeaCandidate(
                ticker="LOW", idea_type=IdeaType.VALUE,
                confidence=ConfidenceLevel.MEDIUM,
                signal_strength=0.7, confidence_score=0.3,
                signals=[], detector="value",
                metadata={"composite_alpha_score": 0.2},
            ),
            IdeaCandidate(
                ticker="HIGH", idea_type=IdeaType.VALUE,
                confidence=ConfidenceLevel.MEDIUM,
                signal_strength=0.7, confidence_score=0.9,
                signals=[], detector="value",
                metadata={"composite_alpha_score": 0.8},
            ),
        ]
        ranked = rank_ideas(ideas)
        assert ranked[0].ticker == "HIGH"

    def test_registry_keys_match_detector_names(self):
        """Registry keys should match detector .name for consistency."""
        from src.engines.idea_generation.detector_registry import (
            default_registry, build_active_detectors,
        )
        detectors = build_active_detectors()
        specs = default_registry.list_all()
        spec_keys = {s.key for s in specs}
        detector_names = {d.name.lower() for d in detectors}
        assert spec_keys == detector_names
