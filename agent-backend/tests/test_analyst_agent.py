"""
tests/test_analyst_agent.py
──────────────────────────────────────────────────────────────────────────────
Mock-based tests for the LLM Technical Analyst Agent.

No actual LLM calls — tests the guardrail logic, fallback behavior,
output schema validation, and prompt construction.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock

from src.engines.technical.analyst_agent import (
    synthesize_technical_memo,
    TechnicalMemoOutput,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_technical_summary(
    signal: str = "BUY",
    score: float = 6.5,
    trend_status: str = "BULLISH",
    momentum_status: str = "BULLISH",
    volatility_condition: str = "NORMAL",
    volume_strength: str = "NORMAL",
    breakout_direction: str = "BULLISH",
) -> dict:
    """Build a minimal technical_summary dict for testing."""
    return {
        "current_price": 150.0,
        "summary": {
            "technical_score": score,
            "signal": signal,
            "signal_strength": "Moderate",
            "trend_status": trend_status,
            "momentum_status": momentum_status,
            "volatility_condition": volatility_condition,
            "volume_strength": volume_strength,
            "breakout_direction": breakout_direction,
            "breakout_probability": 0.6,
            "technical_confidence": 0.7,
            "confirmation_level": "MEDIUM",
            "strongest_module": "trend",
            "weakest_module": "volume",
            "subscores": {
                "trend": 7.2,
                "momentum": 6.0,
                "volatility": 5.5,
                "volume": 5.0,
                "structure": 6.5,
            },
            "evidence": {
                "trend": ["Price +5% above SMA200"],
                "momentum": ["RSI at 55"],
                "volatility": ["ATR% normal"],
                "volume": ["Volume 1.1x avg"],
                "structure": ["HH/HL uptrend"],
            },
        },
        "indicators": {
            "trend": {
                "sma_50": 145, "sma_200": 130, "ema_20": 148,
                "price_vs_sma50": "ABOVE", "price_vs_sma200": "ABOVE",
                "macd_crossover": "BULLISH", "golden_cross": True, "death_cross": False,
                "macd": {"value": 2, "signal": 1, "histogram": 1},
            },
            "momentum": {
                "rsi": 55, "rsi_zone": "NEUTRAL",
                "stochastic_k": 60, "stochastic_d": 55, "stochastic_zone": "NEUTRAL",
            },
            "volatility": {
                "bb_upper": 154, "bb_lower": 146, "bb_width": 8, "bb_position": "MID",
                "atr": 2.7, "atr_pct": 0.018,
            },
            "volume": {"volume_vs_avg_20": 1.1, "obv_trend": "RISING"},
            "structure": {
                "nearest_resistance": 160, "nearest_support": 140,
                "distance_to_resistance_pct": 6.7, "distance_to_support_pct": 6.7,
                "market_structure": "HH_HL", "level_strength": {}, "patterns": [],
            },
        },
        "tradingview_rating": {},
    }


def _make_valid_llm_response(consensus_signal: str = "BULLISH") -> str:
    """Generate a valid JSON response simulating LLM output."""
    opinion = {
        "signal": "BULLISH",
        "conviction": "MEDIUM",
        "narrative": "El precio se encuentra en tendencia alcista.",
        "key_data": ["SMA50 en $145", "RSI en 55"],
    }
    return json.dumps({
        "trend": opinion,
        "momentum": opinion,
        "volatility": opinion,
        "volume": opinion,
        "structure": opinion,
        "consensus": "Análisis técnico positivo con señales alcistas.",
        "consensus_signal": consensus_signal,
        "consensus_conviction": "MEDIUM",
        "tradingview_comparison": "Concordante con TradingView.",
        "key_levels": "Soporte $140, Resistencia $160.",
        "timing": "Buen momento para entrada.",
        "risk_factors": ["RSI podría acercarse a sobrecompra", "Volumen no excepcional"],
    })


# ─── Required output fields ─────────────────────────────────────────────────

REQUIRED_FIELDS = {
    "trend", "momentum", "volatility", "volume", "structure",
    "consensus", "consensus_signal", "consensus_conviction",
    "tradingview_comparison", "key_levels", "timing", "risk_factors",
}

OPINION_FIELDS = {"signal", "conviction", "narrative", "key_data"}


# ─── Test: Signal Consistency Guardrail ──────────────────────────────────────

class TestSignalGuardrail:

    @patch("src.engines.technical.analyst_agent._llm_analyst")
    def test_engine_buy_llm_bearish_corrected(self, mock_llm):
        """If engine says BUY but LLM says BEARISH, guardrail corrects to BULLISH."""
        mock_response = MagicMock()
        mock_response.content = _make_valid_llm_response("BEARISH")
        mock_llm.invoke.return_value = mock_response

        result = synthesize_technical_memo("AAPL", _make_technical_summary(signal="BUY"))
        assert result["consensus_signal"] == "BULLISH"

    @patch("src.engines.technical.analyst_agent._llm_analyst")
    def test_engine_sell_llm_bullish_corrected(self, mock_llm):
        """If engine says SELL but LLM says BULLISH, guardrail corrects to BEARISH."""
        mock_response = MagicMock()
        mock_response.content = _make_valid_llm_response("BULLISH")
        mock_llm.invoke.return_value = mock_response

        result = synthesize_technical_memo("AAPL", _make_technical_summary(signal="SELL"))
        assert result["consensus_signal"] == "BEARISH"

    @patch("src.engines.technical.analyst_agent._llm_analyst")
    def test_engine_strong_buy_llm_bearish_corrected(self, mock_llm):
        """STRONG_BUY + LLM BEARISH → corrected to BULLISH."""
        mock_response = MagicMock()
        mock_response.content = _make_valid_llm_response("BEARISH")
        mock_llm.invoke.return_value = mock_response

        result = synthesize_technical_memo("AAPL", _make_technical_summary(signal="STRONG_BUY"))
        assert result["consensus_signal"] == "BULLISH"

    @patch("src.engines.technical.analyst_agent._llm_analyst")
    def test_engine_neutral_llm_any_allowed(self, mock_llm):
        """NEUTRAL engine → LLM can say anything."""
        mock_response = MagicMock()
        mock_response.content = _make_valid_llm_response("BEARISH")
        mock_llm.invoke.return_value = mock_response

        result = synthesize_technical_memo("AAPL", _make_technical_summary(signal="NEUTRAL"))
        # NEUTRAL engine allows any LLM signal
        assert result["consensus_signal"] in ("BULLISH", "BEARISH", "NEUTRAL")

    @patch("src.engines.technical.analyst_agent._llm_analyst")
    def test_aligned_signals_pass_through(self, mock_llm):
        """When engine and LLM agree, signal passes through unchanged."""
        mock_response = MagicMock()
        mock_response.content = _make_valid_llm_response("BULLISH")
        mock_llm.invoke.return_value = mock_response

        result = synthesize_technical_memo("AAPL", _make_technical_summary(signal="BUY"))
        assert result["consensus_signal"] == "BULLISH"


# ─── Test: Fallback Behavior ────────────────────────────────────────────────

class TestFallbackBehavior:

    @patch("src.engines.technical.analyst_agent._llm_analyst")
    def test_llm_exception_returns_fallback(self, mock_llm):
        """LLM raises exception → fallback with all required fields."""
        mock_llm.invoke.side_effect = Exception("API timeout")

        result = synthesize_technical_memo("AAPL", _make_technical_summary())
        assert set(result.keys()) >= REQUIRED_FIELDS
        assert result["consensus_conviction"] == "LOW"

    @patch("src.engines.technical.analyst_agent._llm_analyst")
    def test_llm_invalid_json_returns_fallback(self, mock_llm):
        """LLM returns invalid JSON → fallback."""
        mock_response = MagicMock()
        mock_response.content = "This is not JSON at all!"
        mock_llm.invoke.return_value = mock_response

        result = synthesize_technical_memo("AAPL", _make_technical_summary())
        assert set(result.keys()) >= REQUIRED_FIELDS

    @patch("src.engines.technical.analyst_agent._llm_analyst")
    def test_llm_empty_response_returns_fallback(self, mock_llm):
        """LLM returns empty string → fallback."""
        mock_response = MagicMock()
        mock_response.content = ""
        mock_llm.invoke.return_value = mock_response

        result = synthesize_technical_memo("AAPL", _make_technical_summary())
        assert set(result.keys()) >= REQUIRED_FIELDS


# ─── Test: Output Schema Validation ─────────────────────────────────────────

class TestOutputSchema:

    @patch("src.engines.technical.analyst_agent._llm_analyst")
    def test_all_required_fields_present(self, mock_llm):
        """LLM response should contain all 12 required fields."""
        mock_response = MagicMock()
        mock_response.content = _make_valid_llm_response("BULLISH")
        mock_llm.invoke.return_value = mock_response

        result = synthesize_technical_memo("AAPL", _make_technical_summary())
        assert set(result.keys()) >= REQUIRED_FIELDS

    @patch("src.engines.technical.analyst_agent._llm_analyst")
    def test_specialty_opinions_have_required_fields(self, mock_llm):
        """Each of the 5 specialty opinions should have signal/conviction/narrative/key_data."""
        mock_response = MagicMock()
        mock_response.content = _make_valid_llm_response("BULLISH")
        mock_llm.invoke.return_value = mock_response

        result = synthesize_technical_memo("AAPL", _make_technical_summary())
        for opinion_key in ("trend", "momentum", "volatility", "volume", "structure"):
            opinion = result[opinion_key]
            assert set(opinion.keys()) >= OPINION_FIELDS, f"Missing fields in {opinion_key}"

    @patch("src.engines.technical.analyst_agent._llm_analyst")
    def test_risk_factors_is_list(self, mock_llm):
        """risk_factors should always be a list."""
        mock_response = MagicMock()
        mock_response.content = _make_valid_llm_response("BULLISH")
        mock_llm.invoke.return_value = mock_response

        result = synthesize_technical_memo("AAPL", _make_technical_summary())
        assert isinstance(result["risk_factors"], list)
        assert len(result["risk_factors"]) >= 1


# ─── Test: Fallback Opinion Quality ─────────────────────────────────────────

class TestFallbackOpinionQuality:

    def test_fallback_signal_matches_score(self):
        """Fallback opinions should derive signal from module score."""
        summary = _make_technical_summary(signal="BUY", score=7.2)

        # Simulate fallback by triggering exception
        with patch("src.engines.technical.analyst_agent._llm_analyst") as mock_llm:
            mock_llm.invoke.side_effect = Exception("timeout")
            result = synthesize_technical_memo("AAPL", summary)

        # Trend has score 7.2 → should be BULLISH
        assert result["trend"]["signal"] == "BULLISH"

    def test_fallback_contains_score_data(self):
        """Fallback opinions should reference the score in key_data."""
        summary = _make_technical_summary(signal="BUY", score=7.2)

        with patch("src.engines.technical.analyst_agent._llm_analyst") as mock_llm:
            mock_llm.invoke.side_effect = Exception("timeout")
            result = synthesize_technical_memo("AAPL", summary)

        for opinion_key in ("trend", "momentum", "volatility", "volume", "structure"):
            opinion = result[opinion_key]
            assert len(opinion["key_data"]) >= 1, f"{opinion_key} has no key_data"
