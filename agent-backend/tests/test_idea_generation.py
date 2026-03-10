"""
tests/test_idea_generation.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive test suite for the Idea Generation Engine module.

Covers:
  - IdeaType enum completeness (including GROWTH)
  - GrowthDetector returns correct IdeaType
  - _CATEGORY_TO_IDEA_TYPE mapping coverage
  - Detector package exports
  - ScanContext + EventDetector polimorphism
  - Engine uniform detector loop
  - Deduplication strategy
  - Ranker with 6 types
  - API contract consistency (id type, signal_strength range)
"""

from __future__ import annotations

import pytest

from src.engines.idea_generation.models import (
    IdeaType,
    IdeaCandidate,
    DetectorResult,
    IdeaScanResult,
    ConfidenceLevel,
    SignalDetail,
    SignalStrength,
    IdeaStatus,
)
from src.engines.alpha_signals.models import SignalCategory


# ═════════════════════════════════════════════════════════════════════════════
# 1. IDEA TYPE ENUM
# ═════════════════════════════════════════════════════════════════════════════


class TestIdeaType:
    """Verify IdeaType enum has all 6 categories."""

    def test_growth_exists(self):
        assert hasattr(IdeaType, "GROWTH")
        assert IdeaType.GROWTH.value == "growth"

    def test_all_six_types_present(self):
        expected = {"value", "quality", "growth", "momentum", "reversal", "event"}
        actual = {e.value for e in IdeaType}
        assert actual == expected, f"Missing: {expected - actual}, Extra: {actual - expected}"

    def test_types_are_string_enum(self):
        for t in IdeaType:
            assert isinstance(t.value, str)
            assert t.value == t.value.lower()


# ═════════════════════════════════════════════════════════════════════════════
# 2. GROWTH DETECTOR
# ═════════════════════════════════════════════════════════════════════════════


class TestGrowthDetector:
    """Verify GrowthDetector returns IdeaType.GROWTH, never VALUE."""

    def test_returns_growth_type_not_value(self):
        from src.contracts.features import FundamentalFeatureSet
        from src.engines.idea_generation.detectors.growth_detector import GrowthDetector

        detector = GrowthDetector()
        # Build features that should trigger growth signals
        features = FundamentalFeatureSet(
            ticker="GROW",
            revenue_growth=0.4,        # >25% → fires
            earnings_surprise=0.15,     # >5% → fires
            margin_trend=0.05,          # >0 → fires
            roic=0.25,                  # >15% → fires
        )
        result = detector.scan(features, None)
        if result is not None:
            assert result.idea_type == IdeaType.GROWTH, (
                f"GrowthDetector returned {result.idea_type}, expected GROWTH"
            )
            assert result.idea_type != IdeaType.VALUE

    def test_detector_name(self):
        from src.engines.idea_generation.detectors.growth_detector import GrowthDetector
        detector = GrowthDetector()
        assert detector.name == "growth"

    def test_signal_category_is_growth(self):
        from src.engines.idea_generation.detectors.growth_detector import GrowthDetector
        detector = GrowthDetector()
        assert detector.signal_category == SignalCategory.GROWTH


# ═════════════════════════════════════════════════════════════════════════════
# 3. CATEGORY MAPPING
# ═════════════════════════════════════════════════════════════════════════════


class TestCategoryMapping:
    """Verify _CATEGORY_TO_IDEA_TYPE covers all relevant categories."""

    def test_growth_is_mapped(self):
        from src.engines.idea_generation.detectors.base import _CATEGORY_TO_IDEA_TYPE
        assert SignalCategory.GROWTH in _CATEGORY_TO_IDEA_TYPE
        assert _CATEGORY_TO_IDEA_TYPE[SignalCategory.GROWTH] == IdeaType.GROWTH

    def test_macro_is_mapped(self):
        from src.engines.idea_generation.detectors.base import _CATEGORY_TO_IDEA_TYPE
        assert SignalCategory.MACRO in _CATEGORY_TO_IDEA_TYPE
        assert _CATEGORY_TO_IDEA_TYPE[SignalCategory.MACRO] == IdeaType.EVENT

    def test_all_signal_categories_covered(self):
        from src.engines.idea_generation.detectors.base import _CATEGORY_TO_IDEA_TYPE
        for cat in SignalCategory:
            assert cat in _CATEGORY_TO_IDEA_TYPE, (
                f"SignalCategory.{cat.name} is not mapped in _CATEGORY_TO_IDEA_TYPE"
            )

    def test_mapping_values_are_valid_idea_types(self):
        from src.engines.idea_generation.detectors.base import _CATEGORY_TO_IDEA_TYPE
        for cat, idea_type in _CATEGORY_TO_IDEA_TYPE.items():
            assert isinstance(idea_type, IdeaType), (
                f"Mapping for {cat} → {idea_type} is not an IdeaType"
            )


# ═════════════════════════════════════════════════════════════════════════════
# 4. DETECTOR EXPORTS
# ═════════════════════════════════════════════════════════════════════════════


class TestDetectorExports:
    """Verify all 6 detectors are importable from the package."""

    def test_all_detectors_importable(self):
        from src.engines.idea_generation.detectors import (
            ValueDetector,
            QualityDetector,
            MomentumDetector,
            ReversalDetector,
            GrowthDetector,
            EventDetector,
        )
        assert ValueDetector is not None
        assert QualityDetector is not None
        assert MomentumDetector is not None
        assert ReversalDetector is not None
        assert GrowthDetector is not None
        assert EventDetector is not None

    def test_all_list_has_six_entries(self):
        from src.engines.idea_generation.detectors import __all__
        assert len(__all__) == 6
        assert "GrowthDetector" in __all__

    def test_all_detectors_subclass_base(self):
        from src.engines.idea_generation.detectors.base import BaseDetector
        from src.engines.idea_generation.detectors import (
            ValueDetector, QualityDetector, MomentumDetector,
            ReversalDetector, GrowthDetector, EventDetector,
        )
        for cls in [ValueDetector, QualityDetector, MomentumDetector,
                     ReversalDetector, GrowthDetector, EventDetector]:
            assert issubclass(cls, BaseDetector), f"{cls.__name__} is not a BaseDetector"


# ═════════════════════════════════════════════════════════════════════════════
# 5. SCAN CONTEXT + EVENT DETECTOR POLYMORPHISM
# ═════════════════════════════════════════════════════════════════════════════


class TestScanContext:
    """Verify ScanContext works and EventDetector accepts it properly."""

    def test_scan_context_creation(self):
        from src.engines.idea_generation.detectors.base import ScanContext
        ctx = ScanContext(previous_score=7.5, current_score=4.0)
        assert ctx.previous_score == 7.5
        assert ctx.current_score == 4.0

    def test_scan_context_defaults(self):
        from src.engines.idea_generation.detectors.base import ScanContext
        ctx = ScanContext()
        assert ctx.previous_score is None
        assert ctx.current_score is None
        assert ctx.extra == {}

    def test_event_detector_accepts_context(self):
        from src.engines.idea_generation.detectors.base import ScanContext
        from src.engines.idea_generation.detectors.event_detector import EventDetector
        from src.contracts.features import TechnicalFeatureSet

        detector = EventDetector()
        ctx = ScanContext(previous_score=8.0, current_score=4.0)
        tech = TechnicalFeatureSet(
            ticker="TEST",
            rsi=25.0,
            stochastic_k=15.0,
            bb_width=0.05,
            beta=1.5,
            earnings_surprise=0.12,
        )
        # Should not raise — EventDetector reads from context
        result = detector.scan(None, tech, context=ctx)
        # Result may or may not fire, but the interface works
        assert result is None or isinstance(result, DetectorResult)

    def test_all_detectors_accept_context(self):
        """Every detector should accept optional context without error."""
        from src.engines.idea_generation.detectors.base import ScanContext
        from src.engines.idea_generation.detectors import (
            ValueDetector, QualityDetector, MomentumDetector,
            ReversalDetector, GrowthDetector, EventDetector,
        )
        ctx = ScanContext()
        for DetectorClass in [ValueDetector, QualityDetector, MomentumDetector,
                               ReversalDetector, GrowthDetector, EventDetector]:
            detector = DetectorClass()
            # Should not raise even with no data
            result = detector.scan(None, None, context=ctx)
            assert result is None or isinstance(result, DetectorResult)


# ═════════════════════════════════════════════════════════════════════════════
# 6. ENGINE UNIFORM LOOP
# ═════════════════════════════════════════════════════════════════════════════


class TestEngineUniformLoop:
    """Verify engine has all 6 detectors in a single list, no special-casing."""

    def test_engine_has_six_detectors(self):
        from src.engines.idea_generation.engine import IdeaGenerationEngine
        engine = IdeaGenerationEngine()
        assert len(engine.detectors) == 6

    def test_no_separate_event_detector_attr(self):
        from src.engines.idea_generation.engine import IdeaGenerationEngine
        engine = IdeaGenerationEngine()
        assert not hasattr(engine, "event_detector"), (
            "EventDetector should be in engine.detectors, not a separate attribute"
        )

    def test_all_detector_types_in_list(self):
        from src.engines.idea_generation.engine import IdeaGenerationEngine
        engine = IdeaGenerationEngine()
        names = {d.name for d in engine.detectors}
        expected = {"value", "quality", "momentum", "reversal", "growth", "event"}
        assert names == expected, f"Missing: {expected - names}"


# ═════════════════════════════════════════════════════════════════════════════
# 7. DEDUPLICATION
# ═════════════════════════════════════════════════════════════════════════════


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
        assert len(deduped) == 2, (
            "Growth and Value for same ticker must coexist"
        )

    def test_genuine_duplicates_consolidated(self):
        from src.engines.idea_generation.distributed.aggregator import ResultAggregator
        ideas = [
            self._make_candidate("AAPL", IdeaType.VALUE, 0.5, detector="value"),
            self._make_candidate("AAPL", IdeaType.VALUE, 0.8, detector="value"),
        ]
        deduped = ResultAggregator._deduplicate(ideas)
        assert len(deduped) == 1
        assert deduped[0].signal_strength == 0.8  # keep strongest

    def test_different_sources_preserved(self):
        from src.engines.idea_generation.distributed.aggregator import ResultAggregator
        ideas = [
            self._make_candidate("MSFT", IdeaType.VALUE, 0.5, source="legacy", detector="value"),
            self._make_candidate("MSFT", IdeaType.VALUE, 0.6, source="alpha_signals_library", detector="value"),
        ]
        deduped = ResultAggregator._deduplicate(ideas)
        assert len(deduped) == 2, (
            "Same type but different sources should coexist"
        )

    def test_all_types_survive(self):
        from src.engines.idea_generation.distributed.aggregator import ResultAggregator
        ideas = [
            self._make_candidate("X", t, 0.5, detector=t.value)
            for t in IdeaType
        ]
        deduped = ResultAggregator._deduplicate(ideas)
        assert len(deduped) == 6

    def test_cross_detector_same_type_coexist(self):
        """Two different detectors producing the same idea_type must not collide."""
        from src.engines.idea_generation.distributed.aggregator import ResultAggregator
        ideas = [
            self._make_candidate("AAPL", IdeaType.VALUE, 0.6, detector="value"),
            self._make_candidate("AAPL", IdeaType.VALUE, 0.7, detector="quality"),
        ]
        deduped = ResultAggregator._deduplicate(ideas)
        assert len(deduped) == 2, (
            "Different detectors producing same idea_type must coexist"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 8. RANKER
# ═════════════════════════════════════════════════════════════════════════════


class TestRanker:
    """Verify ranker handles all 6 idea types correctly."""

    def test_rank_all_types(self):
        from src.engines.idea_generation.ranker import rank_ideas
        candidates = []
        for i, t in enumerate(IdeaType):
            candidates.append(IdeaCandidate(
                ticker=f"T{i}",
                name=f"Test {t.value}",
                sector="Test",
                idea_type=t,
                confidence=ConfidenceLevel.HIGH,
                signal_strength=round(0.3 + i * 0.1, 2),
                signals=[],
            ))
        ranked = rank_ideas(candidates)
        assert len(ranked) == 6
        # Higher strength should rank first (lower priority number)
        assert ranked[0].signal_strength >= ranked[-1].signal_strength

    def test_ranking_is_deterministic(self):
        from src.engines.idea_generation.ranker import rank_ideas
        candidates = [
            IdeaCandidate(
                ticker="A", name="A", sector="X",
                idea_type=IdeaType.GROWTH,
                confidence=ConfidenceLevel.HIGH,
                signal_strength=0.8,
                signals=[],
            ),
            IdeaCandidate(
                ticker="B", name="B", sector="X",
                idea_type=IdeaType.VALUE,
                confidence=ConfidenceLevel.LOW,
                signal_strength=0.3,
                signals=[],
            ),
        ]
        r1 = rank_ideas(candidates)
        r2 = rank_ideas(candidates)
        assert [x.ticker for x in r1] == [x.ticker for x in r2]


# ═════════════════════════════════════════════════════════════════════════════
# 9. SIGNAL STRENGTH RANGE
# ═════════════════════════════════════════════════════════════════════════════


class TestSignalStrengthRange:
    """Verify detectors produce signal_strength in [0, 1] range."""

    def test_growth_detector_strength_range(self):
        from src.contracts.features import FundamentalFeatureSet
        from src.engines.idea_generation.detectors.growth_detector import GrowthDetector

        detector = GrowthDetector()
        features = FundamentalFeatureSet(
            ticker="GROW",
            revenue_growth=0.5,
            earnings_surprise=0.2,
            margin_trend=0.1,
            roic=0.3,
        )
        result = detector.scan(features, None)
        if result is not None:
            assert 0.0 <= result.signal_strength <= 1.0


# ═════════════════════════════════════════════════════════════════════════════
# 10. JOB STORE PROTOCOL
# ═════════════════════════════════════════════════════════════════════════════


class TestJobStore:
    """Verify InMemoryJobStore implementation."""

    def test_save_and_get(self):
        from src.engines.idea_generation.distributed.dispatcher import InMemoryJobStore
        from src.engines.idea_generation.distributed.models import ScanJob, ScanStatus

        store = InMemoryJobStore()
        job = ScanJob(total_tickers=10, status=ScanStatus.PENDING)
        store.save(job)
        retrieved = store.get(job.scan_id)
        assert retrieved is not None
        assert retrieved.scan_id == job.scan_id

    def test_get_missing_returns_none(self):
        from src.engines.idea_generation.distributed.dispatcher import InMemoryJobStore
        store = InMemoryJobStore()
        assert store.get("nonexistent") is None

    def test_list_recent(self):
        from src.engines.idea_generation.distributed.dispatcher import InMemoryJobStore
        from src.engines.idea_generation.distributed.models import ScanJob, ScanStatus

        store = InMemoryJobStore()
        for _ in range(5):
            store.save(ScanJob(total_tickers=10, status=ScanStatus.PENDING))
        recent = store.list_recent(3)
        assert len(recent) == 3


# ═════════════════════════════════════════════════════════════════════════════
# 11. TICKER LIMITS
# ═════════════════════════════════════════════════════════════════════════════


class TestTickerLimits:
    """Verify scan request validation limits."""

    def test_scan_request_max_500(self):
        from src.routes.ideas import ScanRequest
        # 500 should be valid
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


# ═════════════════════════════════════════════════════════════════════════════
# 12. API CONTRACT — ID TYPE
# ═════════════════════════════════════════════════════════════════════════════


class TestAPIContract:
    """Verify API schema consistency."""

    def test_idea_summary_id_is_string(self):
        from src.routes.ideas import IdeaSummary
        schema = IdeaSummary.model_json_schema()
        assert schema["properties"]["id"]["type"] == "string"

    def test_scan_response_schema(self):
        from src.routes.ideas import ScanResponse
        schema = ScanResponse.model_json_schema()
        assert "scan_id" in schema["properties"]
        assert "ideas_found" in schema["properties"]


# ═════════════════════════════════════════════════════════════════════════════
# 13. SCAN CONTEXT SERIALIZATION
# ═════════════════════════════════════════════════════════════════════════════


class TestScanContextSerialization:
    """Verify ScanContext round-trips through dict serialization."""

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
        assert ctx.current_score is None

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
        # Must be JSON-serializable (Celery requirement)
        serialized = json.dumps(data)
        assert isinstance(serialized, str)


# ═════════════════════════════════════════════════════════════════════════════
# 14. DETECTOR FIELD ON MODELS
# ═════════════════════════════════════════════════════════════════════════════


class TestDetectorField:
    """Verify detector field exists on DetectorResult and IdeaCandidate."""

    def test_detector_result_has_field(self):
        result = DetectorResult(
            idea_type=IdeaType.VALUE,
            confidence=ConfidenceLevel.HIGH,
            signal_strength=0.8,
            signals=[],
            detector="value",
        )
        assert result.detector == "value"

    def test_detector_defaults_empty(self):
        result = DetectorResult(
            idea_type=IdeaType.VALUE,
            confidence=ConfidenceLevel.HIGH,
            signal_strength=0.8,
            signals=[],
        )
        assert result.detector == ""

    def test_idea_candidate_has_field(self):
        idea = IdeaCandidate(
            ticker="AAPL",
            idea_type=IdeaType.GROWTH,
            confidence=ConfidenceLevel.MEDIUM,
            signal_strength=0.7,
            signals=[],
            detector="growth",
        )
        assert idea.detector == "growth"

    def test_detector_serializes(self):
        idea = IdeaCandidate(
            ticker="MSFT",
            idea_type=IdeaType.VALUE,
            confidence=ConfidenceLevel.HIGH,
            signal_strength=0.6,
            signals=[],
            detector="value",
        )
        data = idea.model_dump()
        assert data["detector"] == "value"
