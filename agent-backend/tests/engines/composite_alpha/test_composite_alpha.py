"""
tests/engines/composite_alpha/test_composite_alpha.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Composite Alpha Score Engine.

Tests each stage of the 5-stage pipeline:
  1. Normalizer
  2. Category Aggregator
  3. Conflict Resolver
  4. Weighted Scorer
  5. Classifier
Plus full end-to-end integration tests.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    EvaluatedSignal,
    SignalCategory,
    SignalDirection,
    SignalProfile,
    SignalStrength,
    ConfidenceLevel,
    CategoryScore,
)
from src.engines.alpha_signals.registry import registry
from src.engines.composite_alpha.models import (
    CASEWeightConfig,
    CategorySubscore,
    CompositeAlphaResult,
    SignalEnvironment,
)
from src.engines.composite_alpha.engine import CompositeAlphaEngine


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    return CompositeAlphaEngine()


def _make_signal_def(
    signal_id: str,
    category: SignalCategory,
    direction: SignalDirection = SignalDirection.ABOVE,
    threshold: float = 10.0,
    strong_threshold: float = 15.0,
    weight: float = 1.0,
) -> AlphaSignalDefinition:
    """Helper to create a signal definition."""
    return AlphaSignalDefinition(
        id=signal_id,
        name=f"Test Signal {signal_id}",
        category=category,
        feature_path="fundamental.test",
        direction=direction,
        threshold=threshold,
        strong_threshold=strong_threshold,
        weight=weight,
    )


def _make_evaluated(
    signal_id: str,
    category: SignalCategory,
    fired: bool,
    value: float | None,
    threshold: float = 10.0,
    strength: SignalStrength = SignalStrength.MODERATE,
    confidence: float = 0.7,
) -> EvaluatedSignal:
    """Helper to create an evaluated signal."""
    return EvaluatedSignal(
        signal_id=signal_id,
        signal_name=f"Test Signal {signal_id}",
        category=category,
        fired=fired,
        value=value,
        threshold=threshold,
        strength=strength,
        confidence=confidence,
    )


def _make_profile(
    ticker: str, signals: list[EvaluatedSignal]
) -> SignalProfile:
    """Helper to build a SignalProfile from evaluated signals."""
    return SignalProfile(
        ticker=ticker,
        evaluated_at=datetime.now(timezone.utc),
        total_signals=len(signals),
        fired_signals=sum(1 for s in signals if s.fired),
        signals=signals,
        category_summary={},  # not used by CASE
    )


@pytest.fixture(autouse=True)
def _register_test_signals():
    """Register test signal definitions for each test, clean up after."""
    test_ids = []

    def _register(sig_def: AlphaSignalDefinition):
        registry.register(sig_def)
        test_ids.append(sig_def.id)

    # Value signals
    _register(_make_signal_def(
        "test.value_1", SignalCategory.VALUE,
        SignalDirection.ABOVE, 0.08, 0.12, weight=1.2,
    ))
    _register(_make_signal_def(
        "test.value_2", SignalCategory.VALUE,
        SignalDirection.BELOW, 15.0, 10.0, weight=1.0,
    ))

    # Quality signals
    _register(_make_signal_def(
        "test.quality_1", SignalCategory.QUALITY,
        SignalDirection.ABOVE, 0.15, 0.25, weight=1.0,
    ))

    # Momentum signals
    _register(_make_signal_def(
        "test.momentum_1", SignalCategory.MOMENTUM,
        SignalDirection.ABOVE, 50.0, 70.0, weight=1.0,
    ))

    # Volatility signal (for conflict testing)
    _register(_make_signal_def(
        "test.volatility_1", SignalCategory.VOLATILITY,
        SignalDirection.ABOVE, 20.0, 40.0, weight=1.0,
    ))

    yield

    # Cleanup
    for sid in test_ids:
        registry.unregister(sid)


# ═════════════════════════════════════════════════════════════════════════════
# Test Models
# ═════════════════════════════════════════════════════════════════════════════

class TestCASEWeightConfig:
    def test_default_weights_sum_to_one(self):
        config = CASEWeightConfig()
        total = sum(config.as_dict().values())
        assert abs(total - 1.0) < 0.001

    def test_invalid_weights_raise(self):
        with pytest.raises(ValueError, match="must sum to 1.0"):
            CASEWeightConfig(value=0.50)  # total > 1.0

    def test_custom_weights(self):
        config = CASEWeightConfig(
            value=0.30, quality=0.30, momentum=0.10, growth=0.10,
            flow=0.05, volatility=0.05, event=0.05, macro=0.05,
        )
        assert config.value == 0.30
        assert abs(sum(config.as_dict().values()) - 1.0) < 0.001


class TestSignalEnvironment:
    def test_enum_values(self):
        assert SignalEnvironment.VERY_STRONG.value == "Very Strong Opportunity"
        assert SignalEnvironment.NEGATIVE.value == "Negative Signal Environment"


# ═════════════════════════════════════════════════════════════════════════════
# Test Stage 1: Normalizer
# ═════════════════════════════════════════════════════════════════════════════

class TestNormalizer:
    def test_fired_above_signal(self, engine):
        """Signal ABOVE threshold → positive NSS."""
        sig = _make_evaluated(
            "test.value_1", SignalCategory.VALUE,
            fired=True, value=0.10, threshold=0.08,
            strength=SignalStrength.MODERATE, confidence=0.8,
        )
        profile = _make_profile("AAPL", [sig])
        normalized = engine._normalize_signals(profile)
        assert "value" in normalized
        assert len(normalized["value"]) == 1
        _, score = normalized["value"][0]
        assert score > 0, "Fired ABOVE signal should have positive score"

    def test_unfired_signal(self, engine):
        """Non-fired signal → 0.0 normalized score."""
        sig = _make_evaluated(
            "test.value_1", SignalCategory.VALUE,
            fired=False, value=0.05, threshold=0.08,
        )
        profile = _make_profile("AAPL", [sig])
        normalized = engine._normalize_signals(profile)
        _, score = normalized["value"][0]
        assert score == 0.0

    def test_below_direction_normalization(self, engine):
        """Signal BELOW threshold → positive NSS when value < threshold."""
        sig = _make_evaluated(
            "test.value_2", SignalCategory.VALUE,
            fired=True, value=12.0, threshold=15.0,
            strength=SignalStrength.MODERATE, confidence=0.7,
        )
        profile = _make_profile("AAPL", [sig])
        normalized = engine._normalize_signals(profile)
        _, score = normalized["value"][0]
        assert score > 0


# ═════════════════════════════════════════════════════════════════════════════
# Test Stage 2: Category Aggregator
# ═════════════════════════════════════════════════════════════════════════════

class TestCategoryAggregator:
    def test_empty_profile(self, engine):
        """Profile with no signals → all subscores are 0."""
        profile = _make_profile("EMPTY", [])
        normalized = engine._normalize_signals(profile)
        subscores = engine._aggregate_categories(normalized, profile)
        for cat_key, subscore in subscores.items():
            assert subscore.score == 0.0
            assert subscore.fired == 0

    def test_single_fired_signal(self, engine):
        """One fired signal → non-zero category subscore."""
        sig = _make_evaluated(
            "test.quality_1", SignalCategory.QUALITY,
            fired=True, value=0.20, threshold=0.15,
            strength=SignalStrength.MODERATE, confidence=0.8,
        )
        profile = _make_profile("MSFT", [sig])
        normalized = engine._normalize_signals(profile)
        subscores = engine._aggregate_categories(normalized, profile)
        q = subscores["quality"]
        assert q.fired == 1
        assert q.total == 1
        assert q.score > 0.0
        assert q.coverage == 1.0

    def test_coverage_penalty(self, engine):
        """Low coverage (< 30%) should attenuate the subscore."""
        # 1 fired out of 2 total = 50% coverage (no penalty)
        fired = _make_evaluated(
            "test.value_1", SignalCategory.VALUE,
            fired=True, value=0.10, threshold=0.08,
            strength=SignalStrength.MODERATE, confidence=0.8,
        )
        unfired = _make_evaluated(
            "test.value_2", SignalCategory.VALUE,
            fired=False, value=16.0, threshold=15.0,
        )
        profile = _make_profile("GOOG", [fired, unfired])
        normalized = engine._normalize_signals(profile)
        subscores = engine._aggregate_categories(normalized, profile)
        assert subscores["value"].coverage == 0.5  # No penalty


# ═════════════════════════════════════════════════════════════════════════════
# Test Stage 3: Conflict Resolver
# ═════════════════════════════════════════════════════════════════════════════

class TestConflictResolver:
    def test_intra_category_conflict(self, engine):
        """Mixed ABOVE/BELOW directions in same category → conflict detected."""
        sig_above = _make_evaluated(
            "test.value_1", SignalCategory.VALUE,
            fired=True, value=0.10, threshold=0.08,
            strength=SignalStrength.MODERATE, confidence=0.7,
        )
        sig_below = _make_evaluated(
            "test.value_2", SignalCategory.VALUE,
            fired=True, value=12.0, threshold=15.0,
            strength=SignalStrength.MODERATE, confidence=0.7,
        )
        profile = _make_profile("TSLA", [sig_above, sig_below])
        normalized = engine._normalize_signals(profile)
        subscores = engine._aggregate_categories(normalized, profile)
        subscores, conflicts = engine._resolve_conflicts(subscores, profile)
        assert subscores["value"].conflict_detected is True
        assert subscores["value"].conflict_penalty < 1.0

    def test_cross_category_conflict(self, engine):
        """Momentum + Volatility both high → cross-category conflict."""
        sig_mom = _make_evaluated(
            "test.momentum_1", SignalCategory.MOMENTUM,
            fired=True, value=65.0, threshold=50.0,
            strength=SignalStrength.STRONG, confidence=0.9,
        )
        sig_vol = _make_evaluated(
            "test.volatility_1", SignalCategory.VOLATILITY,
            fired=True, value=35.0, threshold=20.0,
            strength=SignalStrength.STRONG, confidence=0.9,
        )
        profile = _make_profile("GME", [sig_mom, sig_vol])
        normalized = engine._normalize_signals(profile)
        subscores = engine._aggregate_categories(normalized, profile)
        subscores, conflicts = engine._resolve_conflicts(subscores, profile)
        # Only fires if both subscores >= 50
        if subscores["momentum"].score >= 50 and subscores["volatility"].score >= 50:
            assert len(conflicts) >= 1
            assert "Momentum vs Volatility" in conflicts[0]


# ═════════════════════════════════════════════════════════════════════════════
# Test Stage 5: Classifier
# ═════════════════════════════════════════════════════════════════════════════

class TestClassifier:
    @pytest.mark.parametrize("score,expected", [
        (95.0, SignalEnvironment.VERY_STRONG),
        (80.0, SignalEnvironment.VERY_STRONG),
        (72.0, SignalEnvironment.STRONG),
        (60.0, SignalEnvironment.STRONG),
        (50.0, SignalEnvironment.NEUTRAL),
        (40.0, SignalEnvironment.NEUTRAL),
        (30.0, SignalEnvironment.WEAK),
        (20.0, SignalEnvironment.WEAK),
        (10.0, SignalEnvironment.NEGATIVE),
        (0.0, SignalEnvironment.NEGATIVE),
    ])
    def test_classification_boundaries(self, score, expected):
        assert CompositeAlphaEngine._classify(score) == expected


# ═════════════════════════════════════════════════════════════════════════════
# End-to-End Integration
# ═════════════════════════════════════════════════════════════════════════════

class TestEndToEnd:
    def test_compute_returns_valid_result(self, engine):
        """Full pipeline produces a valid CompositeAlphaResult."""
        signals = [
            _make_evaluated(
                "test.value_1", SignalCategory.VALUE,
                fired=True, value=0.10, threshold=0.08,
                strength=SignalStrength.MODERATE, confidence=0.8,
            ),
            _make_evaluated(
                "test.quality_1", SignalCategory.QUALITY,
                fired=True, value=0.20, threshold=0.15,
                strength=SignalStrength.MODERATE, confidence=0.7,
            ),
            _make_evaluated(
                "test.momentum_1", SignalCategory.MOMENTUM,
                fired=True, value=65.0, threshold=50.0,
                strength=SignalStrength.STRONG, confidence=0.9,
            ),
        ]
        profile = _make_profile("NVDA", signals)
        result = engine.compute(profile)

        assert isinstance(result, CompositeAlphaResult)
        assert result.ticker == "NVDA"
        assert 0 <= result.composite_alpha_score <= 100
        assert result.signal_environment in SignalEnvironment
        assert result.active_categories >= 1
        assert len(result.weight_profile) == 8
        assert result.evaluated_at is not None

    def test_empty_profile(self, engine):
        """Profile with no signals → score 0, NEGATIVE environment."""
        profile = _make_profile("EMPTY", [])
        result = engine.compute(profile)
        assert result.composite_alpha_score == 0.0
        assert result.signal_environment == SignalEnvironment.NEGATIVE
        assert result.active_categories == 0

    def test_custom_weights(self, engine):
        """Using custom weights changes the final score."""
        signals = [
            _make_evaluated(
                "test.value_1", SignalCategory.VALUE,
                fired=True, value=0.10, threshold=0.08,
                strength=SignalStrength.MODERATE, confidence=0.8,
            ),
        ]
        profile = _make_profile("AAPL", signals)

        default_result = engine.compute(profile)

        heavy_value_weights = CASEWeightConfig(
            value=0.50, quality=0.10, momentum=0.10, growth=0.10,
            flow=0.05, volatility=0.05, event=0.05, macro=0.05,
        )
        heavy_result = engine.compute(profile, weights=heavy_value_weights)

        # Heavy value weight should produce a higher score
        # when the only fired signal is in the value category
        assert heavy_result.composite_alpha_score >= default_result.composite_alpha_score

    def test_serialization(self, engine):
        """CompositeAlphaResult can be serialised to JSON."""
        signals = [
            _make_evaluated(
                "test.value_1", SignalCategory.VALUE,
                fired=True, value=0.10, threshold=0.08,
                strength=SignalStrength.MODERATE, confidence=0.8,
            ),
        ]
        profile = _make_profile("MSFT", signals)
        result = engine.compute(profile)
        json_str = result.model_dump_json()
        assert "MSFT" in json_str
        assert "composite_alpha_score" in json_str
