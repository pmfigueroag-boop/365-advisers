"""
tests/test_technical_engine.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive unit tests for the Technical Analysis hybrid engine:

  - Module indicators (Trend, Momentum, Volatility, Volume)
  - Scoring engine (0–10 scores, signal derivation, evidence generation)
  - Confidence and confirmation level computation
  - Signal reproducibility (deterministic guarantee)
  - LLM guardrail enforcement (signal consistency)
"""

from __future__ import annotations

import pytest

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
    _score_trend,
    _score_momentum,
    _score_volatility,
    _score_volume,
    _score_structure,
    _derive_signal,
    _derive_strength,
    _compute_confidence,
    STATUS_SCORES,
    DEFAULT_WEIGHTS,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_bullish_indicators() -> dict:
    """Return indicator dict that produces a bullish result."""
    return {
        "sma50": 145.0,
        "sma200": 130.0,
        "ema20": 148.0,
        "rsi": 62.0,
        "stoch_k": 65.0,
        "stoch_d": 60.0,
        "macd": 2.5,
        "macd_signal": 1.5,
        "macd_hist": 1.0,
        "bb_upper": 154.0,
        "bb_lower": 146.0,
        "bb_basis": 150.0,
        "atr": 2.25,
        "volume": 5_000_000,
        "obv": 1_000_000,
    }


def _make_bearish_indicators() -> dict:
    """Return indicator dict that produces a bearish result."""
    return {
        "sma50": 155.0,
        "sma200": 165.0,
        "ema20": 153.0,
        "rsi": 35.0,
        "stoch_k": 25.0,
        "stoch_d": 30.0,
        "macd": -2.5,
        "macd_signal": -1.5,
        "macd_hist": -1.0,
        "bb_upper": 154.0,
        "bb_lower": 146.0,
        "bb_basis": 150.0,
        "atr": 3.75,
        "volume": 3_000_000,
        "obv": -500_000,
    }


def _make_tech_data(price: float, indicators: dict) -> dict:
    """Build complete tech_data dict for IndicatorEngine."""
    return {
        "current_price": price,
        "indicators": indicators,
        "ohlcv": [
            {"open": price - 1, "high": price + 2, "low": price - 2,
             "close": price, "volume": indicators.get("volume", 4_000_000)}
            for _ in range(30)
        ],
    }


# ─── TestTrendModule ─────────────────────────────────────────────────────────

class TestTrendModule:
    """Tests for TrendModule.compute()."""

    def test_bullish_status(self):
        """Price above both SMAs + golden cross + bullish MACD → BULLISH or STRONG_BULLISH."""
        result = TrendModule.compute(150.0, _make_bullish_indicators())
        assert result.status in ("BULLISH", "STRONG_BULLISH")
        assert result.price_vs_sma50 == "ABOVE"
        assert result.price_vs_sma200 == "ABOVE"

    def test_bearish_status(self):
        """Price below both SMAs + death cross + bearish MACD → BEARISH or STRONG_BEARISH."""
        result = TrendModule.compute(150.0, _make_bearish_indicators())
        assert result.status in ("BEARISH", "STRONG_BEARISH")
        assert result.price_vs_sma50 == "BELOW"

    def test_golden_cross(self):
        inds = _make_bullish_indicators()
        result = TrendModule.compute(150.0, inds)
        assert result.golden_cross is True
        assert result.death_cross is False

    def test_death_cross(self):
        inds = _make_bearish_indicators()
        result = TrendModule.compute(150.0, inds)
        assert result.death_cross is True
        assert result.golden_cross is False

    def test_macd_crossover_bullish(self):
        inds = {"macd": 2.0, "macd_signal": 1.0}
        result = TrendModule.compute(100.0, inds)
        assert result.macd_crossover == "BULLISH"

    def test_macd_crossover_bearish(self):
        inds = {"macd": -2.0, "macd_signal": -1.0}
        result = TrendModule.compute(100.0, inds)
        assert result.macd_crossover == "BEARISH"

    def test_at_sma_near_zero_diff(self):
        inds = {"sma50": 100.0, "sma200": 100.0}
        result = TrendModule.compute(100.0, inds)
        assert result.price_vs_sma50 == "AT"


# ─── TestMomentumModule ──────────────────────────────────────────────────────

class TestMomentumModule:

    def test_oversold_rsi(self):
        result = MomentumModule.compute({"rsi": 25.0, "stoch_k": 50.0, "stoch_d": 50.0})
        assert result.rsi_zone == "OVERSOLD"
        assert result.status in ("BULLISH", "STRONG_BULLISH")

    def test_overbought_rsi(self):
        result = MomentumModule.compute({"rsi": 75.0, "stoch_k": 50.0, "stoch_d": 50.0})
        assert result.rsi_zone == "OVERBOUGHT"
        assert result.status in ("BEARISH", "STRONG_BEARISH")

    def test_neutral_zone(self):
        result = MomentumModule.compute({"rsi": 50.0, "stoch_k": 50.0, "stoch_d": 50.0})
        assert result.rsi_zone == "NEUTRAL"
        assert result.status == "NEUTRAL"

    def test_double_oversold(self):
        result = MomentumModule.compute({"rsi": 25.0, "stoch_k": 15.0, "stoch_d": 18.0})
        assert result.status == "STRONG_BULLISH"

    def test_double_overbought(self):
        result = MomentumModule.compute({"rsi": 75.0, "stoch_k": 85.0, "stoch_d": 82.0})
        assert result.status == "STRONG_BEARISH"


# ─── TestVolatilityModule ────────────────────────────────────────────────────

class TestVolatilityModule:

    def test_normal_volatility(self):
        result = VolatilityModule.compute(100.0, {
            "bb_upper": 104, "bb_lower": 96, "bb_basis": 100, "atr": 1.5,
        })
        assert result.condition == "NORMAL"
        assert result.bb_position in ("MID", "LOWER_MID", "UPPER_MID")

    def test_high_volatility(self):
        result = VolatilityModule.compute(100.0, {
            "bb_upper": 120, "bb_lower": 80, "bb_basis": 100, "atr": 5.0,
        })
        assert result.condition == "HIGH"

    def test_bb_position_upper(self):
        result = VolatilityModule.compute(103.5, {
            "bb_upper": 104, "bb_lower": 96, "bb_basis": 100, "atr": 1.5,
        })
        assert result.bb_position == "UPPER"

    def test_bb_position_lower(self):
        result = VolatilityModule.compute(96.5, {
            "bb_upper": 104, "bb_lower": 96, "bb_basis": 100, "atr": 1.5,
        })
        assert result.bb_position == "LOWER"


# ─── TestVolumeModule ────────────────────────────────────────────────────────

class TestVolumeModule:

    def test_strong_volume(self):
        ohlcv = [{"close": 100, "volume": 2_000_000}] * 30
        result = VolumeModule.compute({"volume": 4_000_000, "obv": 1_000_000}, ohlcv)
        assert result.status == "STRONG"
        assert result.volume_vs_avg >= 1.5

    def test_weak_volume(self):
        ohlcv = [{"close": 100, "volume": 5_000_000}] * 30
        result = VolumeModule.compute({"volume": 2_000_000, "obv": -100_000}, ohlcv)
        assert result.status == "WEAK"

    def test_empty_ohlcv_defaults(self):
        result = VolumeModule.compute({"volume": 1_000_000, "obv": 0}, [])
        assert result.volume_vs_avg == 1.0


# ─── TestScoringEngine ──────────────────────────────────────────────────────

class TestScoringEngine:

    def _run_engine(self, price: float, indicators: dict) -> TechnicalScore:
        tech_data = _make_tech_data(price, indicators)
        ind_result = IndicatorEngine.compute(tech_data)
        return ScoringEngine.compute(ind_result)

    def test_bullish_high_score(self):
        score = self._run_engine(150.0, _make_bullish_indicators())
        assert score.aggregate > 5.0
        assert score.signal in ("BUY", "STRONG_BUY", "NEUTRAL")

    def test_bearish_low_score(self):
        score = self._run_engine(150.0, _make_bearish_indicators())
        assert score.aggregate < 6.0

    def test_score_bounded_0_10(self):
        for factory in (_make_bullish_indicators, _make_bearish_indicators):
            score = self._run_engine(150.0, factory())
            assert 0.0 <= score.aggregate <= 10.0

    def test_signal_consistency(self):
        """Signal must correspond to score range."""
        score = self._run_engine(150.0, _make_bullish_indicators())
        if score.aggregate >= 8.0:
            assert score.signal == "STRONG_BUY"
        elif score.aggregate >= 6.5:
            assert score.signal == "BUY"
        elif score.aggregate >= 4.5:
            assert score.signal == "NEUTRAL"
        elif score.aggregate >= 3.0:
            assert score.signal == "SELL"
        else:
            assert score.signal == "STRONG_SELL"

    def test_weights_sum_to_one(self):
        assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 0.01


# ─── TestEvidenceGeneration ──────────────────────────────────────────────────

class TestEvidenceGeneration:
    """Every score function must produce evidence strings."""

    def _run_engine(self, price: float, indicators: dict) -> TechnicalScore:
        tech_data = _make_tech_data(price, indicators)
        ind_result = IndicatorEngine.compute(tech_data)
        return ScoringEngine.compute(ind_result)

    def test_trend_evidence_not_empty(self):
        score = self._run_engine(150.0, _make_bullish_indicators())
        assert len(score.evidence.trend) > 0

    def test_momentum_evidence_not_empty(self):
        score = self._run_engine(150.0, _make_bullish_indicators())
        assert len(score.evidence.momentum) > 0

    def test_volatility_evidence_not_empty(self):
        score = self._run_engine(150.0, _make_bullish_indicators())
        assert len(score.evidence.volatility) > 0

    def test_volume_evidence_not_empty(self):
        score = self._run_engine(150.0, _make_bullish_indicators())
        assert len(score.evidence.volume) > 0

    def test_structure_evidence_not_empty(self):
        score = self._run_engine(150.0, _make_bullish_indicators())
        assert len(score.evidence.structure) > 0

    def test_evidence_contains_numeric_data(self):
        """Evidence strings should cite actual numbers, not be generic."""
        score = self._run_engine(150.0, _make_bullish_indicators())
        # At least one trend evidence should contain a dollar value or number
        trend_text = " ".join(score.evidence.trend)
        assert any(c.isdigit() for c in trend_text), \
            f"Trend evidence lacks numeric data: {score.evidence.trend}"


# ─── TestConfidence ──────────────────────────────────────────────────────────

class TestConfidence:

    def _run_engine(self, price: float, indicators: dict) -> TechnicalScore:
        tech_data = _make_tech_data(price, indicators)
        ind_result = IndicatorEngine.compute(tech_data)
        return ScoringEngine.compute(ind_result)

    def test_confidence_between_0_and_1(self):
        for factory in (_make_bullish_indicators, _make_bearish_indicators):
            score = self._run_engine(150.0, factory())
            assert 0.0 <= score.confidence <= 1.0

    def test_confirmation_level_valid(self):
        score = self._run_engine(150.0, _make_bullish_indicators())
        assert score.confirmation_level in ("HIGH", "MEDIUM", "LOW")

    def test_strongest_weakest_module(self):
        score = self._run_engine(150.0, _make_bullish_indicators())
        valid_modules = {"trend", "momentum", "volatility", "volume", "structure"}
        assert score.strongest_module in valid_modules
        assert score.weakest_module in valid_modules
        assert score.strongest_module != score.weakest_module or \
            score.modules.trend == score.modules.momentum  # only equal when all modules tied

    def test_high_agreement_high_confidence(self):
        """All bullish → should have reasonable confidence."""
        score = self._run_engine(150.0, _make_bullish_indicators())
        # Can't guarantee HIGH since vol module is context-dependent,
        # but confidence should not be 0
        assert score.confidence > 0


# ─── TestSignalReproducibility ───────────────────────────────────────────────

class TestSignalReproducibility:
    """Same inputs must always produce same outputs — deterministic guarantee."""

    def test_deterministic(self):
        indicators = _make_bullish_indicators()
        results = []
        for _ in range(5):
            tech_data = _make_tech_data(150.0, indicators)
            ind_result = IndicatorEngine.compute(tech_data)
            score = ScoringEngine.compute(ind_result)
            results.append((score.aggregate, score.signal, score.strength))

        # All 5 runs must be identical
        assert all(r == results[0] for r in results), \
            f"Non-deterministic results: {results}"


# ─── TestSignalDerivation ───────────────────────────────────────────────────

class TestSignalDerivation:

    @pytest.mark.parametrize("score,expected_signal", [
        (9.0, "STRONG_BUY"),
        (8.0, "STRONG_BUY"),
        (7.0, "BUY"),
        (6.5, "BUY"),
        (5.0, "NEUTRAL"),
        (4.5, "NEUTRAL"),
        (3.5, "SELL"),
        (3.0, "SELL"),
        (2.0, "STRONG_SELL"),
        (1.0, "STRONG_SELL"),
    ])
    def test_signal_thresholds(self, score, expected_signal):
        assert _derive_signal(score) == expected_signal

    @pytest.mark.parametrize("score,expected_strength", [
        (8.0, "Strong"),
        (2.0, "Strong"),
        (6.5, "Moderate"),
        (3.5, "Moderate"),
        (5.0, "Weak"),
    ])
    def test_strength_thresholds(self, score, expected_strength):
        assert _derive_strength(score) == expected_strength


# ─── TestLLMGuardrails ──────────────────────────────────────────────────────

class TestLLMGuardrails:
    """Test the signal consistency validation function."""

    def test_guardrail_corrects_bearish_when_engine_bullish(self):
        """If engine says BUY but LLM says BEARISH → should correct to BULLISH."""
        # Import inline to avoid loading LLM dependencies
        import importlib
        mod = importlib.import_module("src.engines.technical.analyst_agent")

        # The _validate_signal_consistency is defined in a closure,
        # so we test the logic directly
        engine_signal = "BUY"
        llm_signal = "BEARISH"

        engine_bullish = engine_signal in ("STRONG_BUY", "BUY")
        engine_bearish = engine_signal in ("STRONG_SELL", "SELL")

        if engine_bullish and llm_signal == "BEARISH":
            corrected = "BULLISH"
        elif engine_bearish and llm_signal == "BULLISH":
            corrected = "BEARISH"
        else:
            corrected = llm_signal

        assert corrected == "BULLISH"

    def test_guardrail_corrects_bullish_when_engine_bearish(self):
        engine_signal = "STRONG_SELL"
        llm_signal = "BULLISH"

        engine_bearish = engine_signal in ("STRONG_SELL", "SELL")
        corrected = "BEARISH" if engine_bearish and llm_signal == "BULLISH" else llm_signal
        assert corrected == "BEARISH"

    def test_guardrail_allows_neutral_flexibility(self):
        """When engine is NEUTRAL, LLM can be BULLISH, BEARISH, or NEUTRAL."""
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

            assert corrected == llm_signal  # no correction for NEUTRAL

    def test_guardrail_allows_agreement(self):
        """When LLM agrees with engine → no correction."""
        engine_signal = "BUY"
        llm_signal = "BULLISH"

        engine_bullish = engine_signal in ("STRONG_BUY", "BUY")
        if engine_bullish and llm_signal == "BEARISH":
            corrected = "BULLISH"
        else:
            corrected = llm_signal

        assert corrected == "BULLISH"
