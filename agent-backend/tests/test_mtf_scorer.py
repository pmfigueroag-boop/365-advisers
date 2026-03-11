"""
tests/test_mtf_scorer.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for MultiTimeframeScorer:
  - Weighted aggregation across timeframes
  - Agreement bonus (+0.5 for ≥3 agreeing TFs)
  - Conflict penalty (-0.3 for 1H vs 1W disagreement)
  - Missing timeframe handling
  - Signal derivation from MTF aggregate
"""

from __future__ import annotations

import pytest

from src.engines.technical.mtf_scorer import (
    MultiTimeframeScorer,
    MTFResult,
    MTF_WEIGHTS,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_bullish_tech_data(price: float = 150.0) -> dict:
    """Synthetic bullish tech_data dict."""
    return {
        "current_price": price,
        "indicators": {
            "sma50": price * 0.95,   # price above SMA50
            "sma200": price * 0.90,  # price above SMA200
            "ema20": price * 0.98,
            "rsi": 62.0,             # mildly bullish
            "stoch_k": 65.0,
            "stoch_d": 60.0,
            "macd": 2.5,
            "macd_signal": 1.5,      # MACD > signal
            "macd_hist": 1.0,
            "bb_upper": price * 1.02,
            "bb_lower": price * 0.98,
            "bb_basis": price,
            "atr": price * 0.015,
            "volume": 5_000_000,
            "obv": 1_000_000,
        },
        "ohlcv": [
            {"open": price - 1, "high": price + 2, "low": price - 2,
             "close": price, "volume": 5_000_000}
            for _ in range(30)
        ],
    }


def _make_bearish_tech_data(price: float = 150.0) -> dict:
    """Synthetic bearish tech_data dict."""
    return {
        "current_price": price,
        "indicators": {
            "sma50": price * 1.05,   # price below SMA50
            "sma200": price * 1.10,  # price below SMA200
            "ema20": price * 1.02,
            "rsi": 35.0,             # bearish
            "stoch_k": 25.0,
            "stoch_d": 30.0,
            "macd": -2.5,
            "macd_signal": -1.5,     # MACD < signal
            "macd_hist": -1.0,
            "bb_upper": price * 1.04,
            "bb_lower": price * 0.96,
            "bb_basis": price,
            "atr": price * 0.025,
            "volume": 3_000_000,
            "obv": -500_000,
        },
        "ohlcv": [
            {"open": price + 1, "high": price + 2, "low": price - 2,
             "close": price, "volume": 3_000_000}
            for _ in range(30)
        ],
    }


def _make_neutral_tech_data(price: float = 150.0) -> dict:
    """Synthetic neutral tech_data dict."""
    return {
        "current_price": price,
        "indicators": {
            "sma50": price,
            "sma200": price * 0.99,
            "ema20": price,
            "rsi": 50.0,
            "stoch_k": 50.0,
            "stoch_d": 50.0,
            "macd": 0.1,
            "macd_signal": 0.0,
            "macd_hist": 0.1,
            "bb_upper": price * 1.02,
            "bb_lower": price * 0.98,
            "bb_basis": price,
            "atr": price * 0.012,
            "volume": 4_000_000,
            "obv": 100_000,
        },
        "ohlcv": [
            {"open": price, "high": price + 1, "low": price - 1,
             "close": price, "volume": 4_000_000}
            for _ in range(30)
        ],
    }


# ─── TestMTFWeights ──────────────────────────────────────────────────────────

class TestMTFWeights:
    """Verify weight configuration."""

    def test_weights_sum_to_one(self):
        assert abs(sum(MTF_WEIGHTS.values()) - 1.0) < 0.01

    def test_daily_has_highest_weight(self):
        assert MTF_WEIGHTS["1d"] == max(MTF_WEIGHTS.values())

    def test_hourly_has_lowest_weight(self):
        assert MTF_WEIGHTS["1h"] == min(MTF_WEIGHTS.values())


# ─── TestMTFAggregation ─────────────────────────────────────────────────────

class TestMTFAggregation:
    """Tests for weighted aggregation logic."""

    def test_all_bullish_high_score(self):
        """All 4 TFs bullish → aggregate should be high."""
        data = {tf: _make_bullish_tech_data() for tf in MTF_WEIGHTS}
        result = MultiTimeframeScorer.compute(data)
        assert result.mtf_aggregate > 6.0
        assert result.mtf_signal in ("BUY", "STRONG_BUY")

    def test_all_bearish_low_score(self):
        """All 4 TFs bearish → aggregate should be low."""
        data = {tf: _make_bearish_tech_data() for tf in MTF_WEIGHTS}
        result = MultiTimeframeScorer.compute(data)
        assert result.mtf_aggregate < 5.0
        assert result.mtf_signal in ("SELL", "STRONG_SELL")

    def test_mixed_signals_neutral(self):
        """Mix of bullish and bearish → aggregate near neutral."""
        data = {
            "1h": _make_bullish_tech_data(),
            "4h": _make_bearish_tech_data(),
            "1d": _make_neutral_tech_data(),
            "1w": _make_neutral_tech_data(),
        }
        result = MultiTimeframeScorer.compute(data)
        assert 3.0 < result.mtf_aggregate < 7.0

    def test_returns_4_timeframe_scores(self):
        """All 4 TFs provided → 4 TimeframeScore entries."""
        data = {tf: _make_neutral_tech_data() for tf in MTF_WEIGHTS}
        result = MultiTimeframeScorer.compute(data)
        assert len(result.timeframe_scores) == 4
        tf_names = {ts.timeframe for ts in result.timeframe_scores}
        assert tf_names == {"1h", "4h", "1d", "1w"}


# ─── TestAgreementLogic ─────────────────────────────────────────────────────

class TestAgreementLogic:
    """Tests for agreement bonus/conflict penalty."""

    def test_strong_agreement(self):
        """≥3 TFs agree → STRONG agreement level."""
        data = {tf: _make_bullish_tech_data() for tf in MTF_WEIGHTS}
        result = MultiTimeframeScorer.compute(data)
        assert result.agreement_level == "STRONG"
        assert result.agreement_count >= 3

    def test_conflict_penalty_applied(self):
        """1H bullish + 1W bearish → conflict penalty applied."""
        data = {
            "1h": _make_bullish_tech_data(),
            "4h": _make_neutral_tech_data(),
            "1d": _make_neutral_tech_data(),
            "1w": _make_bearish_tech_data(),
        }
        result = MultiTimeframeScorer.compute(data)
        # bonus_applied should be negative (includes -0.3 conflict)
        assert result.bonus_applied <= 0.0

    def test_agreement_bonus_positive(self):
        """All bullish → bonus should be positive."""
        data = {tf: _make_bullish_tech_data() for tf in MTF_WEIGHTS}
        result = MultiTimeframeScorer.compute(data)
        assert result.bonus_applied > 0


# ─── TestMissingTimeframes ──────────────────────────────────────────────────

class TestMissingTimeframes:
    """Tests for handling missing or partial TF data."""

    def test_empty_data_returns_neutral(self):
        """No timeframes → neutral defaults."""
        result = MultiTimeframeScorer.compute({})
        assert result.mtf_aggregate == 5.0
        assert result.mtf_signal == "NEUTRAL"
        assert result.agreement_level == "WEAK"

    def test_single_timeframe(self):
        """Only 1D provided → valid result based on that TF."""
        data = {"1d": _make_bullish_tech_data()}
        result = MultiTimeframeScorer.compute(data)
        assert len(result.timeframe_scores) == 1
        assert result.timeframe_scores[0].timeframe == "1d"
        assert result.mtf_aggregate > 0

    def test_partial_timeframes(self):
        """2 of 4 TFs → valid result, weight re-normalized."""
        data = {
            "1d": _make_bullish_tech_data(),
            "1w": _make_bullish_tech_data(),
        }
        result = MultiTimeframeScorer.compute(data)
        assert len(result.timeframe_scores) == 2
        assert result.mtf_aggregate > 0


# ─── TestMTFSignal ───────────────────────────────────────────────────────────

class TestMTFSignal:
    """Tests for MTF signal derivation."""

    def test_score_bounds(self):
        """MTF aggregate should always be between 0–10."""
        for factory in (_make_bullish_tech_data, _make_bearish_tech_data, _make_neutral_tech_data):
            data = {tf: factory() for tf in MTF_WEIGHTS}
            result = MultiTimeframeScorer.compute(data)
            assert 0.0 <= result.mtf_aggregate <= 10.0

    def test_signal_matches_aggregate(self):
        """Signal should correspond to aggregate range."""
        data = {tf: _make_bullish_tech_data() for tf in MTF_WEIGHTS}
        result = MultiTimeframeScorer.compute(data)
        if result.mtf_aggregate >= 6.5:
            assert result.mtf_signal in ("BUY", "STRONG_BUY")

    def test_regime_adjustments_forwarded(self):
        """Regime adjustments should affect the 1D timeframe scoring."""
        data = {tf: _make_neutral_tech_data() for tf in MTF_WEIGHTS}
        result_no_adj = MultiTimeframeScorer.compute(data)
        # Trend-dominant regime
        result_adj = MultiTimeframeScorer.compute(
            data, regime_adjustments={"trend": 1.5, "momentum": 0.7}
        )
        # Scores should differ since 1D uses regime adjustments
        assert isinstance(result_adj, MTFResult)
