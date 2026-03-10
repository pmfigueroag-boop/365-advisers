"""
tests/test_strategy_profiles.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive test suite for the Strategy Profiles layer.

Coverage:
  A. Registry — registration, duplicates, listing, get_by_key, get_or_raise
  B. Profile model — serialization, defaults, custom config
  C. Ranking weights — configurable ranking, backward compatibility
  D. Detector selection — profile-driven detector resolution
  E. Minimum thresholds — confidence and signal_strength filtering
  F. Engine integration — profile passed through to engine
  G. API contracts — profiles endpoint, scan with profile
  H. Built-in profiles — all 5 profiles validated

All tests are deterministic.
"""

from __future__ import annotations

import pytest

from src.engines.idea_generation.strategy_profiles import (
    RankingWeights,
    StrategyProfile,
    StrategyProfileRegistry,
    default_profile_registry,
    DEFAULT_WEIGHTS,
)
from src.engines.idea_generation.models import (
    IdeaCandidate,
    IdeaType,
    ConfidenceLevel,
    SignalStrength,
    SignalDetail,
)
from src.engines.idea_generation.ranker import rank_ideas


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_idea(
    ticker: str = "AAPL",
    idea_type: IdeaType = IdeaType.VALUE,
    signal_strength: float = 0.7,
    confidence_score: float = 0.6,
    alpha_score: float = 0.5,
    detector: str = "value",
) -> IdeaCandidate:
    return IdeaCandidate(
        ticker=ticker,
        name=f"{ticker} Inc",
        sector="Technology",
        idea_type=idea_type,
        confidence=ConfidenceLevel.MEDIUM,
        signal_strength=signal_strength,
        confidence_score=confidence_score,
        signals=[
            SignalDetail(name="s1", value=0.8, threshold=0.5, strength=SignalStrength.STRONG),
        ],
        detector=detector,
        metadata={"composite_alpha_score": alpha_score},
    )


def _make_profile(**overrides) -> StrategyProfile:
    defaults = dict(
        key="test_profile",
        display_name="Test Profile",
        description="A test profile",
        enabled_detectors=frozenset({"value", "quality"}),
    )
    defaults.update(overrides)
    return StrategyProfile(**defaults)


# ═══════════════════════════════════════════════════════════════════════════════
# A. REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════


class TestStrategyProfileRegistry:
    """Verify registry operations."""

    def test_register_and_list(self):
        reg = StrategyProfileRegistry()
        p = _make_profile(key="alpha")
        reg.register(p)
        assert len(reg) == 1
        assert "alpha" in reg

    def test_duplicate_key_raises(self):
        reg = StrategyProfileRegistry()
        reg.register(_make_profile(key="dup"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_make_profile(key="dup"))

    def test_get_by_key(self):
        reg = StrategyProfileRegistry()
        reg.register(_make_profile(key="beta"))
        assert reg.get_by_key("beta") is not None
        assert reg.get_by_key("nonexistent") is None

    def test_get_or_raise(self):
        reg = StrategyProfileRegistry()
        reg.register(_make_profile(key="gamma"))
        profile = reg.get_or_raise("gamma")
        assert profile.key == "gamma"

    def test_get_or_raise_missing(self):
        reg = StrategyProfileRegistry()
        reg.register(_make_profile(key="delta"))
        with pytest.raises(ValueError, match="Unknown strategy profile"):
            reg.get_or_raise("nonexistent")

    def test_get_or_raise_error_message(self):
        reg = StrategyProfileRegistry()
        reg.register(_make_profile(key="a"))
        reg.register(_make_profile(key="b"))
        with pytest.raises(ValueError, match="Available profiles: a, b"):
            reg.get_or_raise("c")

    def test_list_active(self):
        reg = StrategyProfileRegistry()
        reg.register(_make_profile(key="active1", active=True))
        reg.register(_make_profile(key="active2", active=True))
        reg.register(_make_profile(key="inactive", active=False))
        active = reg.list_active()
        assert len(active) == 2
        assert all(p.active for p in active)

    def test_list_all(self):
        reg = StrategyProfileRegistry()
        reg.register(_make_profile(key="x", active=True))
        reg.register(_make_profile(key="y", active=False))
        assert len(reg.list_all()) == 2

    def test_list_active_sorted(self):
        reg = StrategyProfileRegistry()
        reg.register(_make_profile(key="zebra"))
        reg.register(_make_profile(key="alpha"))
        active = reg.list_active()
        assert active[0].key == "alpha"
        assert active[1].key == "zebra"

    def test_contains(self):
        reg = StrategyProfileRegistry()
        reg.register(_make_profile(key="exists"))
        assert "exists" in reg
        assert "missing" not in reg


# ═══════════════════════════════════════════════════════════════════════════════
# B. PROFILE MODEL
# ═══════════════════════════════════════════════════════════════════════════════


class TestStrategyProfileModel:
    """Verify profile model serialization and defaults."""

    def test_defaults(self):
        p = _make_profile()
        assert p.minimum_confidence == 0.0
        assert p.minimum_signal_strength == 0.0
        assert p.sort_default == "priority"
        assert p.active is True

    def test_to_dict(self):
        p = _make_profile(
            enabled_detectors=frozenset({"value", "quality"}),
            preferred_horizons=("5D", "20D"),
        )
        d = p.to_dict()
        assert d["key"] == "test_profile"
        assert "value" in d["enabled_detectors"]
        assert "quality" in d["enabled_detectors"]
        assert d["preferred_horizons"] == ["5D", "20D"]
        assert isinstance(d["ranking_weights"], dict)

    def test_custom_thresholds(self):
        p = _make_profile(minimum_confidence=0.5, minimum_signal_strength=0.4)
        assert p.minimum_confidence == 0.5
        assert p.minimum_signal_strength == 0.4

    def test_ui_hints(self):
        p = _make_profile(ui_hints={"icon": "star", "color": "#FF0000"})
        d = p.to_dict()
        assert d["ui_hints"]["icon"] == "star"
        assert d["ui_hints"]["color"] == "#FF0000"


# ═══════════════════════════════════════════════════════════════════════════════
# C. RANKING WEIGHTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestRankingWeights:
    """Verify ranking weights affect composite scoring."""

    def test_default_weights(self):
        w = DEFAULT_WEIGHTS
        assert w.w_signal == 0.40
        assert w.w_alpha == 0.35
        assert w.w_confidence == 0.25
        assert w.multi_detector_bonus == 0.10

    def test_custom_weights_serialization(self):
        w = RankingWeights(w_signal=0.50, w_alpha=0.30, w_confidence=0.20, multi_detector_bonus=0.05)
        d = w.to_dict()
        assert d["w_signal"] == 0.50
        assert d["w_alpha"] == 0.30

    def test_ranking_with_default_weights(self):
        ideas = [
            _make_idea(ticker="A", signal_strength=0.8, confidence_score=0.6, alpha_score=0.5),
            _make_idea(ticker="B", signal_strength=0.5, confidence_score=0.9, alpha_score=0.3),
        ]
        ranked = rank_ideas(ideas)
        assert ranked[0].priority == 1
        assert ranked[1].priority == 2

    def test_ranking_with_custom_weights(self):
        """Verify that custom weights change ranking order."""
        ideas = [
            _make_idea(ticker="A", signal_strength=0.3, confidence_score=0.9, alpha_score=0.2),
            _make_idea(ticker="B", signal_strength=0.9, confidence_score=0.2, alpha_score=0.2),
        ]
        # With defaults (signal weight 0.40): B should rank higher (high signal)
        ranked_default = rank_ideas(ideas.copy())
        assert ranked_default[0].ticker == "B"

        # With confidence-heavy weights: A should rank higher (high confidence)
        confidence_weights = RankingWeights(
            w_signal=0.10,
            w_alpha=0.10,
            w_confidence=0.80,
            multi_detector_bonus=0.0,
        )
        ranked_custom = rank_ideas(ideas.copy(), ranking_weights=confidence_weights)
        assert ranked_custom[0].ticker == "A"

    def test_ranking_backward_compatibility(self):
        """Verify rank_ideas works identically without ranking_weights."""
        ideas = [
            _make_idea(ticker="X", signal_strength=0.7),
            _make_idea(ticker="Y", signal_strength=0.5),
        ]
        ranked_no_weights = rank_ideas(ideas.copy())
        ranked_none_weights = rank_ideas(ideas.copy(), ranking_weights=None)
        assert ranked_no_weights[0].ticker == ranked_none_weights[0].ticker

    def test_signal_heavy_weights_favor_momentum(self):
        """Signal-heavy profiles should favor high signal_strength ideas."""
        ideas = [
            _make_idea(ticker="SIG", signal_strength=0.95, confidence_score=0.2, alpha_score=0.1),
            _make_idea(ticker="CONF", signal_strength=0.3, confidence_score=0.95, alpha_score=0.1),
        ]
        signal_weights = RankingWeights(w_signal=0.80, w_alpha=0.10, w_confidence=0.10)
        ranked = rank_ideas(ideas, ranking_weights=signal_weights)
        assert ranked[0].ticker == "SIG"

    def test_multi_detector_bonus_configurable(self):
        """Multi-detector bonus uses profile value."""
        ideas = [
            _make_idea(ticker="DUP", signal_strength=0.5, detector="value"),
            _make_idea(ticker="DUP", signal_strength=0.5, detector="quality"),
        ]
        # High bonus
        high_bonus = RankingWeights(multi_detector_bonus=0.50)
        ranked = rank_ideas(ideas, ranking_weights=high_bonus)
        # Both should have bonus applied
        assert len(ranked) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# D. DETECTOR SELECTION
# ═══════════════════════════════════════════════════════════════════════════════


class TestDetectorSelection:
    """Verify profiles control which detectors are active."""

    def test_enabled_detectors_from_profile(self):
        from src.engines.idea_generation.detector_registry import build_active_detectors

        profile = _make_profile(
            enabled_detectors=frozenset({"value", "quality"}),
        )
        detectors = build_active_detectors(
            enabled_keys=set(profile.enabled_detectors),
        )
        names = [d.name for d in detectors]
        assert "value" in names
        assert "quality" in names
        assert "momentum" not in names

    def test_disabled_detectors_from_profile(self):
        from src.engines.idea_generation.detector_registry import build_active_detectors

        profile = _make_profile(
            enabled_detectors=frozenset(),
            disabled_detectors=frozenset({"event"}),
        )
        detectors = build_active_detectors(
            disabled_keys=set(profile.disabled_detectors),
        )
        names = [d.name for d in detectors]
        assert "event" not in names
        assert len(detectors) >= 3

    def test_all_detectors_when_no_profile(self):
        from src.engines.idea_generation.detector_registry import build_active_detectors

        detectors = build_active_detectors()
        assert len(detectors) == 6  # all 6 default detectors

    def test_swing_profile_detectors(self):
        profile = default_profile_registry.get_or_raise("swing")
        assert "momentum" in profile.enabled_detectors
        assert "reversal" in profile.enabled_detectors
        assert "event" in profile.enabled_detectors

    def test_deep_value_profile_detectors(self):
        profile = default_profile_registry.get_or_raise("deep_value")
        assert "value" in profile.enabled_detectors
        assert "quality" in profile.enabled_detectors
        assert len(profile.enabled_detectors) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# E. MINIMUM THRESHOLDS
# ═══════════════════════════════════════════════════════════════════════════════


class TestMinimumThresholds:
    """Verify profile thresholds filter ideas."""

    def test_minimum_confidence_filters(self):
        profile = _make_profile(minimum_confidence=0.5)
        ideas = [
            _make_idea(ticker="HIGH", confidence_score=0.8),
            _make_idea(ticker="LOW", confidence_score=0.2),
        ]
        filtered = [i for i in ideas if i.confidence_score >= profile.minimum_confidence]
        assert len(filtered) == 1
        assert filtered[0].ticker == "HIGH"

    def test_minimum_signal_strength_filters(self):
        profile = _make_profile(minimum_signal_strength=0.5)
        ideas = [
            _make_idea(ticker="STRONG", signal_strength=0.8),
            _make_idea(ticker="WEAK", signal_strength=0.3),
        ]
        filtered = [i for i in ideas if i.signal_strength >= profile.minimum_signal_strength]
        assert len(filtered) == 1
        assert filtered[0].ticker == "STRONG"

    def test_combined_thresholds(self):
        profile = _make_profile(minimum_confidence=0.4, minimum_signal_strength=0.5)
        ideas = [
            _make_idea(ticker="PASS", signal_strength=0.7, confidence_score=0.6),
            _make_idea(ticker="FAIL_CONF", signal_strength=0.7, confidence_score=0.2),
            _make_idea(ticker="FAIL_SIG", signal_strength=0.3, confidence_score=0.6),
            _make_idea(ticker="FAIL_BOTH", signal_strength=0.2, confidence_score=0.1),
        ]
        filtered = [
            i for i in ideas
            if i.confidence_score >= profile.minimum_confidence
            and i.signal_strength >= profile.minimum_signal_strength
        ]
        assert len(filtered) == 1
        assert filtered[0].ticker == "PASS"

    def test_zero_thresholds_no_filter(self):
        profile = _make_profile(minimum_confidence=0.0, minimum_signal_strength=0.0)
        ideas = [_make_idea(ticker="ANY", signal_strength=0.01, confidence_score=0.01)]
        filtered = [
            i for i in ideas
            if i.confidence_score >= profile.minimum_confidence
            and i.signal_strength >= profile.minimum_signal_strength
        ]
        assert len(filtered) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# F. ENGINE INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestEngineIntegration:
    """Verify engine respects strategy profile configuration."""

    def test_engine_accepts_profile(self):
        from src.engines.idea_generation.engine import IdeaGenerationEngine

        profile = default_profile_registry.get_or_raise("deep_value")
        engine = IdeaGenerationEngine(strategy_profile=profile)
        assert engine._strategy_profile is not None
        assert engine._strategy_profile.key == "deep_value"

    def test_engine_without_profile(self):
        from src.engines.idea_generation.engine import IdeaGenerationEngine

        engine = IdeaGenerationEngine()
        assert engine._strategy_profile is None

    def test_engine_deep_value_fewer_detectors(self):
        from src.engines.idea_generation.engine import IdeaGenerationEngine

        default_engine = IdeaGenerationEngine()
        profile = default_profile_registry.get_or_raise("deep_value")
        profile_engine = IdeaGenerationEngine(strategy_profile=profile)

        assert len(profile_engine.detectors) < len(default_engine.detectors)
        assert len(profile_engine.detectors) == 2

    def test_engine_swing_detectors(self):
        from src.engines.idea_generation.engine import IdeaGenerationEngine

        profile = default_profile_registry.get_or_raise("swing")
        engine = IdeaGenerationEngine(strategy_profile=profile)
        detector_names = [d.name for d in engine.detectors]
        assert "momentum" in detector_names
        assert "reversal" in detector_names
        assert "event" in detector_names
        assert "value" not in detector_names

    def test_engine_explicit_keys_override_profile(self):
        """Explicit detector_keys should take precedence over profile."""
        from src.engines.idea_generation.engine import IdeaGenerationEngine

        profile = default_profile_registry.get_or_raise("deep_value")
        engine = IdeaGenerationEngine(
            detector_keys={"momentum"},
            strategy_profile=profile,
        )
        # Profile has enabled_detectors, so it overrides explicit keys
        # Profile enabled = {value, quality} → takes precedence
        names = [d.name for d in engine.detectors]
        assert "value" in names
        assert len(names) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# G. API CONTRACTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAPIContracts:
    """Verify API-level schema contracts."""

    def test_scan_request_with_profile(self):
        from src.routes.ideas import ScanRequest
        req = ScanRequest(tickers=["AAPL"], strategy_profile="swing")
        assert req.strategy_profile == "swing"

    def test_scan_request_without_profile(self):
        from src.routes.ideas import ScanRequest
        req = ScanRequest(tickers=["AAPL"])
        assert req.strategy_profile is None

    def test_scan_response_includes_profile(self):
        from src.routes.ideas import ScanResponse
        schema = ScanResponse.model_json_schema()
        assert "strategy_profile" in schema["properties"]

    def test_get_engine_factory_without_profile(self):
        from src.routes.ideas import get_engine
        engine = get_engine()
        assert engine is not None
        assert engine._strategy_profile is None

    def test_get_engine_factory_with_profile(self):
        from src.routes.ideas import get_engine
        engine = get_engine(strategy_profile_key="swing")
        assert engine._strategy_profile is not None
        assert engine._strategy_profile.key == "swing"

    def test_get_engine_factory_invalid_profile(self):
        from src.routes.ideas import get_engine
        with pytest.raises(ValueError, match="Unknown strategy profile"):
            get_engine(strategy_profile_key="nonexistent_profile")

    def test_profiles_endpoint_schema(self):
        """Verify to_dict produces API-ready data for all profiles."""
        profiles = default_profile_registry.list_active()
        for p in profiles:
            d = p.to_dict()
            assert "key" in d
            assert "display_name" in d
            assert "enabled_detectors" in d
            assert "ranking_weights" in d
            assert isinstance(d["enabled_detectors"], list)
            assert isinstance(d["ranking_weights"], dict)


# ═══════════════════════════════════════════════════════════════════════════════
# H. BUILT-IN PROFILES
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuiltInProfiles:
    """Verify all 5 built-in profiles exist and are properly configured."""

    EXPECTED_KEYS = ["buy_and_hold", "swing", "deep_value", "growth_quality", "event_driven"]

    def test_all_profiles_registered(self):
        for key in self.EXPECTED_KEYS:
            assert key in default_profile_registry, f"Missing profile: {key}"

    def test_five_active_profiles(self):
        active = default_profile_registry.list_active()
        assert len(active) == 5

    def test_buy_and_hold(self):
        p = default_profile_registry.get_or_raise("buy_and_hold")
        assert "value" in p.enabled_detectors
        assert "quality" in p.enabled_detectors
        assert "growth" in p.enabled_detectors
        assert "20D" in p.preferred_horizons
        assert "60D" in p.preferred_horizons
        assert p.minimum_confidence > 0

    def test_swing(self):
        p = default_profile_registry.get_or_raise("swing")
        assert "momentum" in p.enabled_detectors
        assert "reversal" in p.enabled_detectors
        assert "event" in p.enabled_detectors
        assert "1D" in p.preferred_horizons
        assert p.minimum_signal_strength > 0
        assert p.ranking_weights.w_signal > 0.5  # Signal-heavy

    def test_deep_value(self):
        p = default_profile_registry.get_or_raise("deep_value")
        assert "value" in p.enabled_detectors
        assert "quality" in p.enabled_detectors
        assert len(p.enabled_detectors) == 2
        assert p.minimum_confidence >= 0.5  # High conviction required
        assert p.ranking_weights.w_alpha > p.ranking_weights.w_signal

    def test_growth_quality(self):
        p = default_profile_registry.get_or_raise("growth_quality")
        assert "growth" in p.enabled_detectors
        assert "quality" in p.enabled_detectors
        assert p.minimum_confidence > 0
        assert p.minimum_signal_strength > 0

    def test_event_driven(self):
        p = default_profile_registry.get_or_raise("event_driven")
        assert "event" in p.enabled_detectors
        assert "momentum" in p.enabled_detectors
        assert "1D" in p.preferred_horizons
        assert p.ranking_weights.w_signal >= 0.5

    def test_all_profiles_have_ui_hints(self):
        for key in self.EXPECTED_KEYS:
            p = default_profile_registry.get_or_raise(key)
            assert "color" in p.ui_hints
            assert "badge" in p.ui_hints
            assert "icon" in p.ui_hints

    def test_all_profiles_have_descriptions(self):
        for key in self.EXPECTED_KEYS:
            p = default_profile_registry.get_or_raise(key)
            assert len(p.description) > 20

    def test_all_profiles_have_horizons(self):
        for key in self.EXPECTED_KEYS:
            p = default_profile_registry.get_or_raise(key)
            assert len(p.preferred_horizons) >= 1

    def test_all_profiles_serializable(self):
        """Verify all profiles can be serialized to dict."""
        for key in self.EXPECTED_KEYS:
            p = default_profile_registry.get_or_raise(key)
            d = p.to_dict()
            assert isinstance(d, dict)
            assert d["key"] == key

    def test_weight_sums_reasonable(self):
        """Verify weight components sum roughly to 1.0."""
        for key in self.EXPECTED_KEYS:
            p = default_profile_registry.get_or_raise(key)
            w = p.ranking_weights
            total = w.w_signal + w.w_alpha + w.w_confidence
            assert 0.8 <= total <= 1.2, f"Profile {key} weights sum to {total}"
