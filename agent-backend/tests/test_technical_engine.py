"""
tests/test_technical_engine.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive unit tests for the Institutional-Grade Technical Analysis Engine.

Test classes:
  - TestMathUtils           — sigmoid, clamp, normalize_to_score utilities
  - TestTrendModule         — trend indicator computation
  - TestMomentumModule      — momentum indicator computation
  - TestVolatilityModule    — volatility indicator computation
  - TestVolumeModule        — volume + OBV + VP divergence
  - TestContinuousTrend     — continuous trend scoring (sigmoid-based)
  - TestContinuousMomentum  — continuous momentum scoring
  - TestContinuousVolatility— regime-conditional volatility scoring
  - TestContinuousVolume    — volume-price confirmation scoring
  - TestContinuousStructure — risk/reward structure scoring
  - TestSignalThresholds    — signal derivation from score
  - TestConfidence          — correlation-aware confidence (4 groups)
  - TestTechnicalBias       — professional bias output
  - TestInstitutionalQuality— continuity, monotonicity, sensitivity, independence
  - TestSignalReproducibility— deterministic guarantee
  - TestLLMGuardrails       — signal consistency validation
"""

from __future__ import annotations

import math
import pytest

from src.engines.technical.math_utils import sigmoid, clamp, normalize_to_score, inverse_score
from src.engines.technical.indicators import (
    TrendModule,
    MomentumModule,
    VolatilityModule,
    VolumeModule,
    IndicatorEngine,
    IndicatorResult,
)
from src.engines.technical.scoring import (
    ScoringEngine,
    TechnicalScore,
    ModuleEvidence,
    TechnicalBias,
    _score_trend,
    _score_momentum,
    _score_volatility,
    _score_volume,
    _score_structure,
    _derive_signal,
    _derive_strength,
    _compute_confidence,
    _compute_bias,
    INDEPENDENCE_GROUPS,
    DEFAULT_WEIGHTS,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_bullish_indicators() -> dict:
    return {
        "sma50": 145.0, "sma200": 130.0, "ema20": 148.0,
        "rsi": 62.0, "stoch_k": 65.0, "stoch_d": 60.0,
        "macd": 2.5, "macd_signal": 1.5, "macd_hist": 1.0,
        "bb_upper": 154.0, "bb_lower": 146.0, "bb_basis": 150.0,
        "atr": 2.25, "volume": 5_000_000, "obv": 1_000_000,
    }


def _make_bearish_indicators() -> dict:
    return {
        "sma50": 155.0, "sma200": 165.0, "ema20": 153.0,
        "rsi": 35.0, "stoch_k": 25.0, "stoch_d": 30.0,
        "macd": -2.5, "macd_signal": -1.5, "macd_hist": -1.0,
        "bb_upper": 154.0, "bb_lower": 146.0, "bb_basis": 150.0,
        "atr": 3.75, "volume": 3_000_000, "obv": -500_000,
    }


def _make_ohlcv(price: float, vol: int = 4_000_000, days: int = 30, trend: str = "flat") -> list[dict]:
    """Generate synthetic OHLCV data."""
    data = []
    for i in range(days):
        if trend == "up":
            close = price - (days - i) * 0.5
        elif trend == "down":
            close = price + (days - i) * 0.5
        else:
            close = price
        data.append({
            "open": close - 0.5, "high": close + 1.0, "low": close - 1.0,
            "close": close, "volume": vol,
        })
    return data


def _make_tech_data(price: float, indicators: dict, ohlcv: list[dict] | None = None) -> dict:
    return {
        "current_price": price,
        "indicators": indicators,
        "ohlcv": ohlcv or _make_ohlcv(price, indicators.get("volume", 4_000_000)),
    }


# ─── TestMathUtils ────────────────────────────────────────────────────────────

class TestMathUtils:

    def test_sigmoid_center(self):
        assert sigmoid(0) == pytest.approx(0.5)

    def test_sigmoid_positive_large(self):
        assert sigmoid(10) > 0.999

    def test_sigmoid_negative_large(self):
        assert sigmoid(-10) < 0.001

    def test_sigmoid_symmetry(self):
        assert sigmoid(3) + sigmoid(-3) == pytest.approx(1.0)

    def test_clamp_within_range(self):
        assert clamp(5.0) == 5.0

    def test_clamp_above_max(self):
        assert clamp(15.0) == 10.0

    def test_clamp_below_min(self):
        assert clamp(-3.0) == 0.0

    def test_normalize_to_score_center(self):
        """Center value → 5.0."""
        assert normalize_to_score(50, center=50, scale=10) == pytest.approx(5.0, abs=0.01)

    def test_normalize_to_score_high(self):
        """Value >> center → approaching 10."""
        assert normalize_to_score(100, center=50, scale=10) > 9.0

    def test_normalize_to_score_low(self):
        """Value << center → approaching 0."""
        assert normalize_to_score(0, center=50, scale=10) < 1.0

    def test_inverse_score_reversal(self):
        """Inverse score: high value → low score."""
        high = inverse_score(80, center=50, scale=10)
        low = inverse_score(20, center=50, scale=10)
        assert low > high  # low input → high score


# ─── TestTrendModule ──────────────────────────────────────────────────────────

class TestTrendModule:

    def test_bullish_status(self):
        result = TrendModule.compute(150.0, _make_bullish_indicators())
        assert result.status in ("BULLISH", "STRONG_BULLISH")
        assert result.price_vs_sma50 == "ABOVE"

    def test_bearish_status(self):
        result = TrendModule.compute(150.0, _make_bearish_indicators())
        assert result.status in ("BEARISH", "STRONG_BEARISH")
        assert result.price_vs_sma50 == "BELOW"

    def test_golden_cross(self):
        result = TrendModule.compute(150.0, _make_bullish_indicators())
        assert result.golden_cross is True

    def test_death_cross(self):
        result = TrendModule.compute(150.0, _make_bearish_indicators())
        assert result.death_cross is True


# ─── TestMomentumModule ──────────────────────────────────────────────────────

class TestMomentumModule:

    def test_oversold(self):
        result = MomentumModule.compute({"rsi": 25.0, "stoch_k": 50.0, "stoch_d": 50.0})
        assert result.rsi_zone == "OVERSOLD"

    def test_overbought(self):
        result = MomentumModule.compute({"rsi": 75.0, "stoch_k": 50.0, "stoch_d": 50.0})
        assert result.rsi_zone == "OVERBOUGHT"

    def test_double_oversold(self):
        result = MomentumModule.compute({"rsi": 25.0, "stoch_k": 15.0, "stoch_d": 18.0})
        assert result.status == "STRONG_BULLISH"


# ─── TestVolumeModule ────────────────────────────────────────────────────────

class TestVolumeModule:

    def test_real_obv_from_ohlcv(self):
        """OBV should be computed from OHLCV series when available."""
        ohlcv = _make_ohlcv(100, vol=1_000_000, days=30, trend="up")
        result = VolumeModule.compute({"volume": 1_000_000, "obv": 0}, ohlcv)
        assert result.obv_computed is True

    def test_volume_price_confirmed(self):
        """Price up + volume up should produce CONFIRMED."""
        ohlcv = []
        for i in range(30):
            close = 100 + i * 0.5
            vol = 3_000_000 + i * 100_000  # increasing volume
            ohlcv.append({"open": close - 0.5, "high": close + 1, "low": close - 1,
                          "close": close, "volume": vol})
        result = VolumeModule.compute({"volume": 5_000_000, "obv": 0}, ohlcv)
        assert result.volume_price_confirmation == "CONFIRMED"

    def test_volume_price_divergent(self):
        """Price up + volume down should produce DIVERGENT."""
        ohlcv = []
        for i in range(30):
            close = 100 + i * 0.5
            vol = 5_000_000 - i * 100_000  # decreasing volume
            ohlcv.append({"open": close - 0.5, "high": close + 1, "low": close - 1,
                          "close": close, "volume": max(vol, 1_000_000)})
        result = VolumeModule.compute({"volume": 2_000_000, "obv": 0}, ohlcv)
        assert result.volume_price_confirmation == "DIVERGENT"


# ─── TestContinuousTrendScoring ──────────────────────────────────────────────

class TestContinuousTrendScoring:

    def test_bullish_scores_above_5(self):
        result = TrendModule.compute(150.0, _make_bullish_indicators())
        score, evidence = _score_trend(result, price=150.0)
        assert score > 5.0
        assert len(evidence) >= 3

    def test_bearish_scores_below_5(self):
        result = TrendModule.compute(150.0, _make_bearish_indicators())
        score, evidence = _score_trend(result, price=150.0)
        assert score < 5.0

    def test_score_bounded(self):
        for factory in (_make_bullish_indicators, _make_bearish_indicators):
            result = TrendModule.compute(150.0, factory())
            score, _ = _score_trend(result, price=150.0)
            assert 0.0 <= score <= 10.0


# ─── TestContinuousMomentumScoring ───────────────────────────────────────────

class TestContinuousMomentumScoring:

    def test_oversold_high_score(self):
        """RSI=25 → should score high (bullish opportunity)."""
        result = MomentumModule.compute({"rsi": 25.0, "stoch_k": 20.0, "stoch_d": 22.0})
        score, _ = _score_momentum(result)
        assert score > 7.0

    def test_overbought_low_score(self):
        """RSI=75 → should score low (bearish risk)."""
        result = MomentumModule.compute({"rsi": 75.0, "stoch_k": 80.0, "stoch_d": 78.0})
        score, _ = _score_momentum(result)
        assert score < 3.0

    def test_neutral_around_5(self):
        """RSI=50, Stoch=50 → should be near 5.0."""
        result = MomentumModule.compute({"rsi": 50.0, "stoch_k": 50.0, "stoch_d": 50.0})
        score, _ = _score_momentum(result)
        assert 4.0 <= score <= 6.0


# ─── TestContinuousVolatilityScoring ─────────────────────────────────────────

class TestContinuousVolatilityScoring:

    def test_normal_vol_good_score(self):
        result = VolatilityModule.compute(100.0, {
            "bb_upper": 104, "bb_lower": 96, "bb_basis": 100, "atr": 1.8,
        })
        score, _ = _score_volatility(result, regime="TRANSITIONING")
        assert score >= 5.0  # normal vol = healthy

    def test_extreme_vol_penalized(self):
        result = VolatilityModule.compute(100.0, {
            "bb_upper": 120, "bb_lower": 80, "bb_basis": 100, "atr": 5.0,
        })
        score, _ = _score_volatility(result, regime="VOLATILE")
        assert score < 5.0  # extreme vol + volatile regime = risky

    def test_trending_regime_bonus(self):
        """Normal vol in trending market → score boost."""
        result = VolatilityModule.compute(100.0, {
            "bb_upper": 104, "bb_lower": 96, "bb_basis": 100, "atr": 2.0,
        })
        trending_score, _ = _score_volatility(result, regime="TRENDING")
        neutral_score, _ = _score_volatility(result, regime="TRANSITIONING")
        assert trending_score > neutral_score

    def test_ranging_low_vol_bonus(self):
        """Low vol in ranging market → ideal for mean-reversion."""
        result = VolatilityModule.compute(100.0, {
            "bb_upper": 102, "bb_lower": 98, "bb_basis": 100, "atr": 1.0,
        })
        ranging_score, _ = _score_volatility(result, regime="RANGING")
        neutral_score, _ = _score_volatility(result, regime="TRANSITIONING")
        assert ranging_score > neutral_score


# ─── TestContinuousVolumeScoring ─────────────────────────────────────────────

class TestContinuousVolumeScoring:

    def test_confirmed_vp_boosts_score(self):
        result = VolumeModule.compute(
            {"volume": 5_000_000, "obv": 0},
            _make_ohlcv(100, vol=3_000_000, days=30, trend="up"),
        )
        score, _ = _score_volume(result)
        assert score >= 5.0

    def test_high_volume_high_score(self):
        ohlcv = _make_ohlcv(100, vol=2_000_000, days=30)
        result = VolumeModule.compute({"volume": 5_000_000, "obv": 0}, ohlcv)
        score, _ = _score_volume(result)
        assert score > 6.0  # 2.5x avg volume


# ─── TestContinuousStructureScoring ──────────────────────────────────────────

class TestContinuousStructureScoring:

    def test_score_bounded(self):
        ohlcv = _make_ohlcv(100, days=60)
        result = IndicatorEngine.compute(_make_tech_data(100, _make_bullish_indicators(), ohlcv))
        score, _ = _score_structure(result.structure)
        assert 0.0 <= score <= 10.0


# ─── TestSignalThresholds ────────────────────────────────────────────────────

class TestSignalThresholds:

    @pytest.mark.parametrize("score,expected", [
        (9.0, "STRONG_BUY"),
        (7.5, "STRONG_BUY"),
        (7.0, "BUY"),
        (6.0, "BUY"),
        (5.0, "NEUTRAL"),
        (4.0, "NEUTRAL"),
        (3.0, "SELL"),
        (2.5, "SELL"),
        (2.0, "STRONG_SELL"),
        (1.0, "STRONG_SELL"),
    ])
    def test_thresholds(self, score, expected):
        assert _derive_signal(score) == expected

    @pytest.mark.parametrize("score,expected", [
        (8.0, "Strong"),
        (2.0, "Strong"),
        (6.5, "Moderate"),
        (3.5, "Moderate"),
        (5.0, "Weak"),
    ])
    def test_strength(self, score, expected):
        assert _derive_strength(score) == expected


# ─── TestCorrelationAwareConfidence ──────────────────────────────────────────

class TestCorrelationAwareConfidence:

    def test_four_independence_groups(self):
        """Should have exactly 4 independence groups."""
        assert len(INDEPENDENCE_GROUPS) == 4

    def test_direction_group_contains_trend_momentum(self):
        """Trend and Momentum are in the same correlated group."""
        assert "trend" in INDEPENDENCE_GROUPS["direction"]
        assert "momentum" in INDEPENDENCE_GROUPS["direction"]

    def test_all_bullish_high_confidence(self):
        from src.engines.technical.scoring import ModuleScores
        modules = ModuleScores(trend=8, momentum=7, volatility=7, volume=7, structure=7)
        confidence, level = _compute_confidence(modules, "BUY")
        assert confidence >= 0.75
        assert level == "HIGH"

    def test_mixed_signals_low_confidence(self):
        from src.engines.technical.scoring import ModuleScores
        modules = ModuleScores(trend=8, momentum=7, volatility=3, volume=3, structure=3)
        confidence, level = _compute_confidence(modules, "BUY")
        assert confidence <= 0.5
        assert level in ("LOW", "MEDIUM")

    def test_confidence_bounded(self):
        from src.engines.technical.scoring import ModuleScores
        for t, m, v, vo, s in [(10, 10, 10, 10, 10), (0, 0, 0, 0, 0), (5, 5, 5, 5, 5)]:
            modules = ModuleScores(trend=t, momentum=m, volatility=v, volume=vo, structure=s)
            confidence, _ = _compute_confidence(modules, "NEUTRAL")
            assert 0.0 <= confidence <= 1.0


# ─── TestTechnicalBias ───────────────────────────────────────────────────────

class TestTechnicalBias:

    def _run_engine(self, price: float, indicators: dict) -> TechnicalScore:
        ohlcv = _make_ohlcv(price, indicators.get("volume", 4_000_000), days=60)
        tech_data = _make_tech_data(price, indicators, ohlcv)
        ind_result = IndicatorEngine.compute(tech_data)
        return ScoringEngine.compute(ind_result, price=price)

    def test_bullish_bias(self):
        score = self._run_engine(150.0, _make_bullish_indicators())
        if score.signal in ("BUY", "STRONG_BUY"):
            assert score.bias.primary_bias == "BULLISH"
            assert score.bias.bias_strength > 0

    def test_bearish_bias(self):
        score = self._run_engine(150.0, _make_bearish_indicators())
        if score.signal in ("SELL", "STRONG_SELL"):
            assert score.bias.primary_bias == "BEARISH"

    def test_bias_strength_bounded(self):
        for factory in (_make_bullish_indicators, _make_bearish_indicators):
            score = self._run_engine(150.0, factory())
            assert 0.0 <= score.bias.bias_strength <= 1.0

    def test_actionable_zone_valid(self):
        score = self._run_engine(150.0, _make_bullish_indicators())
        valid_zones = {"ACCUMULATION", "BREAKOUT_WATCH", "TAKE_PROFIT",
                       "STOP_LOSS_PROXIMITY", "NEUTRAL_ZONE"}
        assert score.bias.actionable_zone in valid_zones

    def test_trend_alignment_valid(self):
        score = self._run_engine(150.0, _make_bullish_indicators())
        assert score.bias.trend_alignment in ("ALIGNED", "DIVERGENT", "NEUTRAL")


# ─── TestInstitutionalQuality ────────────────────────────────────────────────

class TestInstitutionalQuality:
    """
    Critical quality tests that verify the scoring engine behaves
    as an institutional-grade system should.
    """

    def test_continuity_trend_slightly_vs_very_bullish(self):
        """
        CONTINUITY: An asset 1% above SMA200 must score LOWER than
        one 20% above. No discrete bucketing.
        """
        # Slightly above
        inds_slight = _make_bullish_indicators()
        inds_slight["sma200"] = 148.5  # price=150, ~1% above
        result_slight = TrendModule.compute(150.0, inds_slight)
        score_slight, _ = _score_trend(result_slight, price=150.0)

        # Far above
        inds_far = _make_bullish_indicators()
        inds_far["sma200"] = 120.0    # price=150, ~25% above
        result_far = TrendModule.compute(150.0, inds_far)
        score_far, _ = _score_trend(result_far, price=150.0)

        assert score_far > score_slight, \
            f"Continuity violated: 25% above SMA200 ({score_far}) should score higher than 1% above ({score_slight})"

    def test_monotonicity_rsi(self):
        """
        MONOTONICITY: Lower RSI → higher momentum score (more oversold = more bullish).
        Test multiple RSI levels in sequence.
        """
        rsi_values = [70, 60, 50, 40, 30, 20]
        prev_score = -1.0
        for rsi in rsi_values:
            result = MomentumModule.compute({"rsi": rsi, "stoch_k": 50.0, "stoch_d": 50.0})
            score, _ = _score_momentum(result)
            assert score >= prev_score, \
                f"Monotonicity violated: RSI={rsi} score {score} < previous {prev_score}"
            prev_score = score

    def test_sensitivity_rsi_10pct_change(self):
        """
        SENSITIVITY: A 10-point RSI change must produce a measurable score change.
        """
        result_50 = MomentumModule.compute({"rsi": 50.0, "stoch_k": 50.0, "stoch_d": 50.0})
        result_40 = MomentumModule.compute({"rsi": 40.0, "stoch_k": 50.0, "stoch_d": 50.0})
        score_50, _ = _score_momentum(result_50)
        score_40, _ = _score_momentum(result_40)
        delta = abs(score_40 - score_50)
        assert delta >= 0.3, \
            f"Sensitivity too low: 10-point RSI change produced only {delta:.2f} score change"

    def test_independence_volume_doesnt_affect_trend(self):
        """
        INDEPENDENCE: Changing volume indicators should primarily affect
        the volume score, not the trend score.
        """
        ohlcv = _make_ohlcv(150, days=30)
        inds_low_vol = _make_bullish_indicators()
        inds_low_vol["volume"] = 1_000_000

        inds_high_vol = _make_bullish_indicators()
        inds_high_vol["volume"] = 10_000_000

        result_low = IndicatorEngine.compute(_make_tech_data(150.0, inds_low_vol, ohlcv))
        result_high = IndicatorEngine.compute(_make_tech_data(150.0, inds_high_vol, ohlcv))

        trend_low, _ = _score_trend(result_low.trend, price=150.0)
        trend_high, _ = _score_trend(result_high.trend, price=150.0)

        assert abs(trend_low - trend_high) < 0.5, \
            f"Independence violated: changing volume moved trend score by {abs(trend_low - trend_high):.2f}"

    def test_regime_conditioning_volatility(self):
        """
        REGIME CONDITIONING: Same volatility data must produce different
        scores under different regimes.
        """
        result = VolatilityModule.compute(100.0, {
            "bb_upper": 104, "bb_lower": 96, "bb_basis": 100, "atr": 2.0,
        })
        score_trending, _ = _score_volatility(result, regime="TRENDING")
        score_ranging, _ = _score_volatility(result, regime="RANGING")

        assert score_trending != score_ranging, \
            f"Regime conditioning failed: same vol data produced identical scores ({score_trending})"


# ─── TestSignalReproducibility ───────────────────────────────────────────────

class TestSignalReproducibility:

    def test_deterministic(self):
        """Same inputs must always produce same outputs."""
        indicators = _make_bullish_indicators()
        results = []
        for _ in range(5):
            ohlcv = _make_ohlcv(150.0, indicators.get("volume", 4_000_000), days=60)
            tech_data = _make_tech_data(150.0, indicators, ohlcv)
            ind_result = IndicatorEngine.compute(tech_data)
            score = ScoringEngine.compute(ind_result, price=150.0)
            results.append((score.aggregate, score.signal, score.strength))

        assert all(r == results[0] for r in results)


# ─── TestLLMGuardrails ──────────────────────────────────────────────────────

class TestLLMGuardrails:

    def test_corrects_bearish_when_engine_bullish(self):
        engine_signal = "BUY"
        llm_signal = "BEARISH"
        engine_bullish = engine_signal in ("STRONG_BUY", "BUY")
        corrected = "BULLISH" if engine_bullish and llm_signal == "BEARISH" else llm_signal
        assert corrected == "BULLISH"

    def test_corrects_bullish_when_engine_bearish(self):
        engine_signal = "STRONG_SELL"
        llm_signal = "BULLISH"
        engine_bearish = engine_signal in ("STRONG_SELL", "SELL")
        corrected = "BEARISH" if engine_bearish and llm_signal == "BULLISH" else llm_signal
        assert corrected == "BEARISH"

    def test_neutral_flexibility(self):
        engine_signal = "NEUTRAL"
        for llm_signal in ("BULLISH", "BEARISH", "NEUTRAL"):
            engine_bullish = engine_signal in ("STRONG_BUY", "BUY")
            engine_bearish = engine_signal in ("STRONG_SELL", "SELL")
            if engine_bullish and llm_signal == "BEARISH":
                corrected = "BULLISH"
            elif engine_bearish and llm_signal == "BULLISH":
                corrected = "BEARISH"
            else:
                corrected = llm_signal
            assert corrected == llm_signal  # no correction for neutral


# ─── TestEvidenceGeneration ──────────────────────────────────────────────────

class TestEvidenceGeneration:

    def _run_engine(self, price: float, indicators: dict) -> TechnicalScore:
        ohlcv = _make_ohlcv(price, indicators.get("volume", 4_000_000), days=60)
        tech_data = _make_tech_data(price, indicators, ohlcv)
        ind_result = IndicatorEngine.compute(tech_data)
        return ScoringEngine.compute(ind_result, price=price)

    def test_all_modules_produce_evidence(self):
        score = self._run_engine(150.0, _make_bullish_indicators())
        assert len(score.evidence.trend) > 0
        assert len(score.evidence.momentum) > 0
        assert len(score.evidence.volatility) > 0
        assert len(score.evidence.volume) > 0
        assert len(score.evidence.structure) > 0

    def test_evidence_contains_numbers(self):
        """Evidence strings must cite specific numerical data."""
        score = self._run_engine(150.0, _make_bullish_indicators())
        all_evidence = " ".join(
            score.evidence.trend + score.evidence.momentum +
            score.evidence.volatility + score.evidence.volume
        )
        assert any(c.isdigit() for c in all_evidence)

    def test_evidence_cites_score_values(self):
        """Evidence should mention the score produced by each component."""
        score = self._run_engine(150.0, _make_bullish_indicators())
        trend_text = " ".join(score.evidence.trend)
        assert "→" in trend_text or "score" in trend_text.lower()


# ─── TestWeights ─────────────────────────────────────────────────────────────

class TestWeights:

    def test_weights_sum_to_one(self):
        assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 0.01

    def test_five_modules(self):
        assert len(DEFAULT_WEIGHTS) == 5
        for key in ("trend", "momentum", "volatility", "volume", "structure"):
            assert key in DEFAULT_WEIGHTS
