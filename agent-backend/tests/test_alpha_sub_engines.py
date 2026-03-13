"""
tests/test_alpha_sub_engines.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the 5 Alpha sub-engines and shared utilities.
"""

import math
import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# 0. SHARED UTILS
# ═══════════════════════════════════════════════════════════════════════════════


class TestSharedUtils:

    def test_safe_float_int(self):
        from src.engines._utils import safe_float
        assert safe_float(42) == 42.0

    def test_safe_float_str(self):
        from src.engines._utils import safe_float
        assert safe_float("3.14") == pytest.approx(3.14)

    def test_safe_float_none(self):
        from src.engines._utils import safe_float
        assert safe_float(None) is None

    def test_safe_float_nan(self):
        from src.engines._utils import safe_float
        assert safe_float(float("nan")) is None

    def test_safe_float_inf(self):
        from src.engines._utils import safe_float
        assert safe_float(float("inf")) is None

    def test_safe_float_data_incomplete(self):
        from src.engines._utils import safe_float
        assert safe_float("DATA_INCOMPLETE") is None

    def test_safe_float_default(self):
        from src.engines._utils import safe_float
        assert safe_float(None, default=0.0) == 0.0

    def test_sigmoid_center(self):
        from src.engines._utils import sigmoid
        assert sigmoid(5.0, center=5.0, scale=1.0) == pytest.approx(5.0, abs=0.01)

    def test_sigmoid_above_center(self):
        from src.engines._utils import sigmoid
        assert sigmoid(10.0, center=5.0, scale=1.0) > 5.0

    def test_sigmoid_range(self):
        from src.engines._utils import sigmoid
        for val in [-100, -10, 0, 10, 100]:
            result = sigmoid(val, center=0.0, scale=1.0)
            assert 0.0 < result < 10.0

    def test_clamp_normal(self):
        from src.engines._utils import clamp
        assert clamp(50) == 50.0

    def test_clamp_below(self):
        from src.engines._utils import clamp
        assert clamp(-10) == 0.0

    def test_clamp_above(self):
        from src.engines._utils import clamp
        assert clamp(150) == 100.0

    def test_clamp_invalid(self):
        from src.engines._utils import clamp
        assert clamp("bad") == 50.0  # midpoint default


# ═══════════════════════════════════════════════════════════════════════════════
# 1. ALPHA SENTIMENT ENGINE — ADDITIONAL
# ═══════════════════════════════════════════════════════════════════════════════


class TestSentimentZScore:
    """Tests for the fixed z-score (Poisson σ proxy)."""

    def test_z_score_moderate_volume(self):
        from src.engines.alpha_sentiment.engine import AlphaSentimentEngine
        e = AlphaSentimentEngine()
        # avg_vol=100, σ=√100=10, vol_24h=120 → z=(120-100)/10=2.0
        r = e.analyze("T", {"bullish_pct": 50, "bearish_pct": 50,
                            "message_volume_24h": 120, "avg_volume_30d": 100})
        assert r.volume_z_score == pytest.approx(2.0, abs=0.1)

    def test_z_score_spike(self):
        from src.engines.alpha_sentiment.engine import AlphaSentimentEngine
        e = AlphaSentimentEngine()
        # avg_vol=100, σ=10, vol_24h=500 → z=(500-100)/10=40.0
        r = e.analyze("T", {"bullish_pct": 50, "bearish_pct": 50,
                            "message_volume_24h": 500, "avg_volume_30d": 100})
        assert r.volume_z_score > 10  # Very significant spike

    def test_z_score_low_volume(self):
        from src.engines.alpha_sentiment.engine import AlphaSentimentEngine
        e = AlphaSentimentEngine()
        r = e.analyze("T", {"bullish_pct": 50, "bearish_pct": 50,
                            "message_volume_24h": 5, "avg_volume_30d": 100})
        assert r.volume_z_score < 0  # Below average

    def test_neutral_sentiment_composite_near_zero(self):
        from src.engines.alpha_sentiment.engine import AlphaSentimentEngine
        e = AlphaSentimentEngine()
        r = e.analyze("T", {"bullish_pct": 50, "bearish_pct": 50,
                            "message_volume_24h": 100, "message_volume_7d": 700,
                            "avg_volume_30d": 100})
        assert abs(r.composite_score) < 30

    def test_regime_classification(self):
        from src.engines.alpha_sentiment.engine import AlphaSentimentEngine
        e = AlphaSentimentEngine()
        # Extreme fear
        r = e.analyze("T", {"bullish_pct": 5, "bearish_pct": 95,
                            "message_volume_24h": 1000, "avg_volume_30d": 100,
                            "news_count": 30})
        assert r.regime.value in ("panic", "fear")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ALPHA MACRO ENGINE — TRANSITIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestMacroTransitions:
    """Tests for regime transition memory."""

    def test_first_call_no_transition(self):
        from src.engines.alpha_macro.engine import AlphaMacroEngine
        e = AlphaMacroEngine()
        d = e.analyze({"gdp_growth": 4.0, "unemployment": 3.5, "pmi": 58})
        # First call — no transition signal
        assert not any("transition" in s.lower() for s in d.score.signals)

    def test_transition_detected(self):
        from src.engines.alpha_macro.engine import AlphaMacroEngine
        e = AlphaMacroEngine()
        # First: expansion
        e.analyze({"gdp_growth": 4.0, "unemployment": 3.5, "pmi": 58, "yield_curve_spread": 1.5})
        # Second: recession
        d2 = e.analyze({"gdp_growth": -1.0, "unemployment": 8.0, "pmi": 42, "yield_curve_spread": -0.5})
        assert any("transition" in s.lower() for s in d2.score.signals)

    def test_same_regime_no_transition(self):
        from src.engines.alpha_macro.engine import AlphaMacroEngine
        e = AlphaMacroEngine()
        e.analyze({"gdp_growth": 4.0, "unemployment": 3.5, "pmi": 58, "yield_curve_spread": 1.5})
        d2 = e.analyze({"gdp_growth": 3.5, "unemployment": 3.8, "pmi": 56, "yield_curve_spread": 1.2})
        assert not any("transition" in s.lower() for s in d2.score.signals)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ALPHA VOLATILITY ENGINE — MULTIVARIATE
# ═══════════════════════════════════════════════════════════════════════════════


class TestVolMultivariate:
    """Tests for multivariate composite risk formula."""

    def test_vix_only(self):
        from src.engines.alpha_volatility.engine import AlphaVolatilityEngine
        e = AlphaVolatilityEngine()
        d = e.analyze({"vix_current": 20.0})
        # VIX=20 → vix_component=33, others=50.0 default
        # risk = 0.4*33 + 0.3*50 + 0.2*35 + 0.1*0 = 35.2
        assert 30 < d.score.composite_risk < 50

    def test_all_components(self):
        from src.engines.alpha_volatility.engine import AlphaVolatilityEngine
        e = AlphaVolatilityEngine()
        d = e.analyze({"vix_current": 30.0, "iv_rank": 80, "iv_current": 35,
                       "realized_vol": 20, "term_structure_slope": -1.0})
        # VIX=30→66, IV=80, term=backwardation→90, IV-RV=15→75
        # risk = 0.4*66 + 0.3*80 + 0.2*90 + 0.1*75 = 76.9
        assert d.score.composite_risk > 70

    def test_calm_market(self):
        from src.engines.alpha_volatility.engine import AlphaVolatilityEngine
        e = AlphaVolatilityEngine()
        d = e.analyze({"vix_current": 12.0, "iv_rank": 15, "iv_current": 12,
                       "realized_vol": 11, "term_structure_slope": 1.0})
        assert d.score.composite_risk < 25

    def test_term_structure_contribution(self):
        from src.engines.alpha_volatility.engine import AlphaVolatilityEngine
        # Backwardation should increase risk vs contango with same VIX
        e = AlphaVolatilityEngine()
        d_back = e.analyze({"vix_current": 25.0, "term_structure_slope": -1.0})
        d_cont = e.analyze({"vix_current": 25.0, "term_structure_slope": 1.0})
        assert d_back.score.composite_risk > d_cont.score.composite_risk


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ALPHA FUNDAMENTAL ENGINE — SIGMOID SCORING
# ═══════════════════════════════════════════════════════════════════════════════


class TestFundamentalSigmoid:
    """Tests for sigmoid-based scoring in alpha_fundamental."""

    def test_excellent_company_high_score(self):
        from src.engines.alpha_fundamental.engine import AlphaFundamentalEngine
        e = AlphaFundamentalEngine()
        r = e.analyze("STAR", ratios={
            "pe_ratio": 8, "roe": 0.35, "roic": 0.30, "gross_margin": 0.75,
            "operating_margin": 0.35, "current_ratio": 3.0, "debt_to_equity": 0.2,
            "interest_coverage": 15,
        }, growth_data={"revenue_growth_yoy": 0.35, "earnings_growth_yoy": 0.40, "fcf_growth_yoy": 0.25})
        assert r.composite_score > 70
        assert r.grade.value in ("A+", "A")

    def test_poor_company_low_score(self):
        from src.engines.alpha_fundamental.engine import AlphaFundamentalEngine
        e = AlphaFundamentalEngine()
        r = e.analyze("BAD", ratios={
            "pe_ratio": 80, "roe": 0.02, "roic": 0.03, "gross_margin": 0.15,
            "debt_to_equity": 4.0, "current_ratio": 0.6,
        })
        assert r.composite_score < 50
        assert r.grade.value in ("D", "F", "C")

    def test_sigmoid_continuity(self):
        """Verify sigmoid scoring is continuous — no jumps."""
        from src.engines.alpha_fundamental.engine import AlphaFundamentalEngine
        e = AlphaFundamentalEngine()
        scores = []
        for roe in [0.05, 0.10, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30]:
            r = e.analyze("T", ratios={"roe": roe})
            scores.append(r.profitability.score)
        # Monotonically increasing
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i-1] - 0.5  # allow tiny float tolerance


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SIGNAL EVALUATOR — SIGMOID CONFIDENCE
# ═══════════════════════════════════════════════════════════════════════════════


class TestEvaluatorConfidence:
    """Tests for the new sigmoid-based confidence formula."""

    def test_confidence_at_threshold(self):
        from src.engines.alpha_signals.models import AlphaSignalDefinition, SignalDirection
        from src.engines.alpha_signals.evaluator import SignalEvaluator
        sig = AlphaSignalDefinition(
            id="t1", name="test", category="value", feature_path="fundamental.test",
            direction=SignalDirection.ABOVE, threshold=10.0, strong_threshold=15.0,
        )
        conf = SignalEvaluator._compute_confidence(sig, 10.0)
        # At threshold: confidence should be ~0.5
        assert 0.3 < conf < 0.6

    def test_confidence_at_strong(self):
        from src.engines.alpha_signals.models import AlphaSignalDefinition, SignalDirection
        from src.engines.alpha_signals.evaluator import SignalEvaluator
        sig = AlphaSignalDefinition(
            id="t2", name="test", category="value", feature_path="fundamental.test",
            direction=SignalDirection.ABOVE, threshold=10.0, strong_threshold=15.0,
        )
        conf = SignalEvaluator._compute_confidence(sig, 15.0)
        # At strong threshold: confidence should be high
        assert conf > 0.7

    def test_confidence_below_no_diverge(self):
        """BELOW direction with value→0 should NOT diverge to infinity."""
        from src.engines.alpha_signals.models import AlphaSignalDefinition, SignalDirection
        from src.engines.alpha_signals.evaluator import SignalEvaluator
        sig = AlphaSignalDefinition(
            id="t3", name="test", category="value", feature_path="fundamental.test",
            direction=SignalDirection.BELOW, threshold=20.0,
        )
        conf = SignalEvaluator._compute_confidence(sig, 0.001)
        assert 0.0 <= conf <= 1.0  # Must be bounded

    def test_confidence_range(self):
        """Confidence must always be in [0, 1]."""
        from src.engines.alpha_signals.models import AlphaSignalDefinition, SignalDirection
        from src.engines.alpha_signals.evaluator import SignalEvaluator
        sig = AlphaSignalDefinition(
            id="t4", name="test", category="value", feature_path="fundamental.test",
            direction=SignalDirection.ABOVE, threshold=10.0,
        )
        for val in [0.1, 1, 5, 10, 20, 50, 100, 1000]:
            conf = SignalEvaluator._compute_confidence(sig, val)
            assert 0.0 <= conf <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ALPHA DECAY ENGINE — FRESHNESS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAlphaDecay:

    def test_fresh_signal_no_decay(self):
        from src.engines.alpha_decay.engine import DecayEngine
        from src.engines.alpha_decay.tracker import ActivationTracker
        from src.engines.alpha_signals.models import (
            EvaluatedSignal, SignalCategory, SignalStrength, SignalProfile,
        )
        from datetime import datetime, timezone

        tracker = ActivationTracker()
        engine = DecayEngine(tracker)

        sig = EvaluatedSignal(
            signal_id="test.fresh", signal_name="Fresh", category=SignalCategory.VALUE,
            fired=True, value=10.0, threshold=5.0,
            strength=SignalStrength.MODERATE, confidence=0.8,
        )
        profile = SignalProfile(
            ticker="TEST", total_signals=1, fired_signals=1, signals=[sig],
        )
        result = engine.apply(profile)
        assert result.average_freshness > 0.9

    def test_decay_disabled_passthrough(self):
        from src.engines.alpha_decay.engine import DecayEngine
        from src.engines.alpha_decay.tracker import ActivationTracker
        from src.engines.alpha_decay.models import DecayConfig
        from src.engines.alpha_signals.models import SignalProfile

        config = DecayConfig(enabled=False)
        tracker = ActivationTracker()
        engine = DecayEngine(tracker, config)

        profile = SignalProfile(ticker="TEST", total_signals=0, fired_signals=0, signals=[])
        result = engine.apply(profile)
        assert result.average_freshness == 1.0
        assert result.overall_freshness.value == "fresh"
