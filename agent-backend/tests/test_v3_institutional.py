"""
tests/test_v3_institutional.py
──────────────────────────────────────────────────────────────────────────────
Tests for V3 Senior-Grade features:
  - RSI/Price Divergence Detection
  - Signal Freshness Decay
  - Regime-Adaptive Weights
  - Self-Calibrating Asset Context
  - Position Sizing
  - Setup Quality Score
"""

from __future__ import annotations

import math
import pytest

from src.engines.technical.indicators import (
    MomentumModule,
    TrendModule,
    _detect_rsi_divergence,
    _detect_cross_age,
    _detect_macd_cross_age,
    _compute_rsi_series,
    _find_local_extrema,
)
from src.engines.technical.scoring import (
    ScoringEngine,
    _score_trend,
    _score_momentum,
    _compute_adaptive_weights,
    _compute_setup_quality,
    DEFAULT_WEIGHTS,
    REGIME_WEIGHT_PROFILES,
    TechnicalBias,
)
from src.engines.technical.calibration import (
    compute_asset_context,
    AssetContext,
    _percentile,
)
from src.engines.technical.position_sizing import (
    compute_position_sizing,
    PositionSuggestion,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_ohlcv_bearish_divergence(days: int = 30) -> list[dict]:
    """Price makes higher high, but RSI should show lower high (overbought declining)."""
    data = []
    for i in range(days):
        if i < days // 2:
            # First half: price rises to 110, strong momentum
            close = 100 + i * 0.5
        else:
            # Brief dip
            if i < days // 2 + 3:
                close = 100 + (days // 2) * 0.5 - (i - days // 2) * 2
            else:
                # New higher high but with slower momentum (wider range)
                close = 100 + (days // 2) * 0.5 + (i - days // 2 - 3) * 0.3
        data.append({
            "open": close - 0.5, "high": close + 1, "low": close - 1,
            "close": close, "volume": 3_000_000,
        })
    return data


def _make_ohlcv_bullish_divergence(days: int = 30) -> list[dict]:
    """Price makes lower low, but RSI should show higher low (less selling pressure)."""
    data = []
    for i in range(days):
        if i < days // 2:
            close = 100 - i * 0.5  # price drops
        else:
            if i < days // 2 + 3:
                close = 100 - (days // 2) * 0.5 + (i - days // 2) * 2
            else:
                # New lower low but gentler
                close = 100 - (days // 2) * 0.5 - (i - days // 2 - 3) * 0.2
        data.append({
            "open": close + 0.5, "high": close + 1, "low": close - 1,
            "close": close, "volume": 3_000_000,
        })
    return data


def _make_flat_ohlcv(price: float = 100.0, days: int = 60) -> list[dict]:
    return [
        {"open": price - 0.5, "high": price + 1, "low": price - 1,
         "close": price, "volume": 3_000_000}
        for _ in range(days)
    ]


def _make_trending_ohlcv(start: float = 100.0, days: int = 60, direction: str = "up") -> list[dict]:
    data = []
    for i in range(days):
        if direction == "up":
            close = start + i * 0.5
        else:
            close = start - i * 0.5
        data.append({
            "open": close - 0.5, "high": close + 1, "low": close - 1,
            "close": close, "volume": 3_000_000,
        })
    return data


# ─── TestDivergenceDetection ─────────────────────────────────────────────────

class TestDivergenceDetection:

    def test_rsi_series_computation(self):
        """RSI series from closes produces valid values."""
        closes = [100 + i * 0.3 for i in range(30)]  # trending up
        rsi = _compute_rsi_series(closes, 14)
        assert len(rsi) > 0
        assert all(0 <= r <= 100 for r in rsi)

    def test_find_local_highs(self):
        data = [1, 3, 2, 5, 4, 6, 3]
        highs = _find_local_extrema(data, "high")
        assert 3 in highs
        assert 5 in highs or 6 in highs

    def test_find_local_lows(self):
        data = [5, 3, 4, 2, 4, 1, 3]
        lows = _find_local_extrema(data, "low")
        assert 3 in lows or 2 in lows or 1 in lows

    def test_no_divergence_on_flat(self):
        """Flat OHLCV should produce no divergence."""
        ohlcv = _make_flat_ohlcv(100, 30)
        div_type, strength = _detect_rsi_divergence(ohlcv, 50.0)
        assert div_type == "NONE"

    def test_divergence_in_momentum_result(self):
        """MomentumModule.compute with OHLCV should populate divergence field."""
        result = MomentumModule.compute(
            {"rsi": 50, "stoch_k": 50, "stoch_d": 50},
            ohlcv=_make_flat_ohlcv(100, 30),
        )
        assert result.divergence in ("BULLISH_DIV", "BEARISH_DIV", "NONE")
        assert 0.0 <= result.divergence_strength <= 1.0

    def test_backward_compatible_no_ohlcv(self):
        """Without OHLCV, divergence should be NONE."""
        result = MomentumModule.compute({"rsi": 50, "stoch_k": 50, "stoch_d": 50})
        assert result.divergence == "NONE"
        assert result.divergence_strength == 0.0


# ─── TestSignalFreshness ─────────────────────────────────────────────────────

class TestSignalFreshness:

    def test_cross_age_from_trending(self):
        """Trending OHLCV with clear SMA cross should detect age."""
        ohlcv = _make_trending_ohlcv(100, 60, "up")
        result = TrendModule.compute(150.0, {"sma50": 140, "sma200": 120, "ema20": 148,
                                              "macd": 2, "macd_signal": 1, "macd_hist": 1}, ohlcv)
        assert result.cross_age_bars >= 0

    def test_macd_cross_age(self):
        """MACD cross age should be non-negative."""
        ohlcv = _make_trending_ohlcv(100, 60, "up")
        age = _detect_macd_cross_age(ohlcv)
        assert age >= 0

    def test_freshness_decay_in_scoring(self):
        """Fresh golden cross → higher score than stale one."""
        from src.engines.technical.indicators import TrendResult

        # Simulate fresh cross (age=1)
        fresh = TrendResult(
            sma_50=145, sma_200=130, ema_20=148,
            macd_value=2, macd_signal=1, macd_histogram=1,
            price_vs_sma50="ABOVE", price_vs_sma200="ABOVE",
            macd_crossover="BULLISH", golden_cross=True, death_cross=False,
            status="STRONG_BULLISH", cross_age_bars=1, macd_cross_age_bars=1,
        )
        # Simulate stale cross (age=40)
        stale = TrendResult(
            sma_50=145, sma_200=130, ema_20=148,
            macd_value=2, macd_signal=1, macd_histogram=1,
            price_vs_sma50="ABOVE", price_vs_sma200="ABOVE",
            macd_crossover="BULLISH", golden_cross=True, death_cross=False,
            status="STRONG_BULLISH", cross_age_bars=40, macd_cross_age_bars=40,
        )

        fresh_score, _ = _score_trend(fresh, price=150)
        stale_score, _ = _score_trend(stale, price=150)

        assert fresh_score >= stale_score, \
            f"Fresh golden cross ({fresh_score}) should score >= stale ({stale_score})"

    def test_backward_compatible_no_ohlcv(self):
        """Without OHLCV, cross_age should default to 0."""
        result = TrendModule.compute(150, {"sma50": 145, "sma200": 130, "ema20": 148,
                                            "macd": 2, "macd_signal": 1, "macd_hist": 1})
        assert result.cross_age_bars == 0
        assert result.macd_cross_age_bars == 0


# ─── TestAdaptiveWeights ─────────────────────────────────────────────────────

class TestAdaptiveWeights:

    def test_trending_boosts_trend_weight(self):
        w = _compute_adaptive_weights("TRENDING")
        assert w["trend"] > DEFAULT_WEIGHTS["trend"]

    def test_ranging_boosts_structure_weight(self):
        w = _compute_adaptive_weights("RANGING")
        assert w["structure"] > DEFAULT_WEIGHTS["structure"]

    def test_volatile_boosts_volatility_weight(self):
        w = _compute_adaptive_weights("VOLATILE")
        assert w["volatility"] > DEFAULT_WEIGHTS["volatility"]

    def test_transitioning_uses_defaults(self):
        w = _compute_adaptive_weights("TRANSITIONING")
        assert w == DEFAULT_WEIGHTS

    def test_unknown_regime_uses_defaults(self):
        w = _compute_adaptive_weights("UNKNOWN_REGIME")
        assert w == DEFAULT_WEIGHTS

    @pytest.mark.parametrize("regime", ["TRENDING", "RANGING", "VOLATILE", "TRANSITIONING"])
    def test_all_profiles_sum_to_one(self, regime):
        w = _compute_adaptive_weights(regime)
        assert abs(sum(w.values()) - 1.0) < 0.01


# ─── TestCalibration ─────────────────────────────────────────────────────────

class TestCalibration:

    def test_context_from_flat_ohlcv(self):
        ohlcv = _make_flat_ohlcv(100, 30)
        ctx = compute_asset_context(ohlcv, 100)
        assert ctx.bars_available == 30
        assert ctx.optimal_atr_pct > 0

    def test_context_from_trending_ohlcv(self):
        ohlcv = _make_trending_ohlcv(100, 60, "up")
        ctx = compute_asset_context(ohlcv, 130)
        assert ctx.optimal_atr_pct > 0
        assert ctx.volume_median > 0

    def test_context_from_empty(self):
        ctx = compute_asset_context([], 100)
        assert ctx.optimal_atr_pct == 1.8  # defaults

    def test_percentile_basic(self):
        assert _percentile([1, 2, 3, 4, 5], 50) == 3.0
        assert _percentile([1, 2, 3, 4, 5], 0) == 1.0
        assert _percentile([1, 2, 3, 4, 5], 100) == 5.0

    def test_high_vol_asset_higher_optimal_atr(self):
        """A high-volatility OHLCV should produce a higher optimal ATR%."""
        low_vol = [{"open": 100 - 0.3, "high": 100 + 0.5, "low": 100 - 0.5,
                     "close": 100, "volume": 3_000_000} for _ in range(30)]
        high_vol = [{"open": 100 - 2, "high": 100 + 5, "low": 100 - 5,
                      "close": 100, "volume": 3_000_000} for _ in range(30)]
        ctx_low = compute_asset_context(low_vol, 100)
        ctx_high = compute_asset_context(high_vol, 100)
        assert ctx_high.optimal_atr_pct > ctx_low.optimal_atr_pct


# ─── TestPositionSizing ──────────────────────────────────────────────────────

class TestPositionSizing:

    def test_buy_signal_produces_stop_below(self):
        ps = compute_position_sizing(
            price=100, atr=2.0, atr_pct=2.0,
            signal="BUY", confidence=0.7, risk_reward_ratio=2.0,
        )
        assert ps.stop_loss_price < 100
        assert ps.take_profit_price > 100
        assert ps.suggested_pct_of_portfolio > 0

    def test_sell_signal_produces_stop_above(self):
        ps = compute_position_sizing(
            price=100, atr=2.0, atr_pct=2.0,
            signal="SELL", confidence=0.7, risk_reward_ratio=2.0,
        )
        assert ps.stop_loss_price > 100
        assert ps.take_profit_price < 100

    def test_position_capped_at_25pct(self):
        ps = compute_position_sizing(
            price=100, atr=0.1, atr_pct=0.1,  # tiny ATR = enormous position
            signal="STRONG_BUY", confidence=1.0, risk_reward_ratio=3.0,
        )
        assert ps.suggested_pct_of_portfolio <= 0.25

    def test_low_confidence_halves_position(self):
        high_conf = compute_position_sizing(
            price=100, atr=2.0, atr_pct=2.0,
            signal="BUY", confidence=0.8, risk_reward_ratio=1.5,
        )
        low_conf = compute_position_sizing(
            price=100, atr=2.0, atr_pct=2.0,
            signal="BUY", confidence=0.2, risk_reward_ratio=1.5,
        )
        assert high_conf.suggested_pct_of_portfolio > low_conf.suggested_pct_of_portfolio

    def test_zero_price_returns_empty(self):
        ps = compute_position_sizing(
            price=0, atr=0, atr_pct=0,
            signal="BUY", confidence=0.5, risk_reward_ratio=1.0,
        )
        assert ps.suggested_pct_of_portfolio == 0

    def test_risk_reward_in_output(self):
        ps = compute_position_sizing(
            price=100, atr=2.0, atr_pct=2.0,
            signal="BUY", confidence=0.7, risk_reward_ratio=2.5,
        )
        assert ps.risk_reward_ratio == 2.5

    def test_rationale_not_empty(self):
        ps = compute_position_sizing(
            price=100, atr=2.0, atr_pct=2.0,
            signal="BUY", confidence=0.7, risk_reward_ratio=2.0,
        )
        assert len(ps.rationale) >= 2


# ─── TestSetupQuality ────────────────────────────────────────────────────────

class TestSetupQuality:

    def test_quality_bounded(self):
        bias = TechnicalBias(
            primary_bias="BULLISH", bias_strength=0.7,
            trend_alignment="ALIGNED", risk_reward_ratio=2.0,
        )
        from src.engines.technical.indicators import MomentumResult, TrendResult
        momentum = MomentumResult(rsi=55, rsi_zone="NEUTRAL", stoch_k=60, stoch_d=55,
                                   stoch_zone="NEUTRAL", status="BULLISH")
        trend = TrendResult(
            sma_50=145, sma_200=130, ema_20=148,
            macd_value=2, macd_signal=1, macd_histogram=1,
            price_vs_sma50="ABOVE", price_vs_sma200="ABOVE",
            macd_crossover="BULLISH", golden_cross=True, death_cross=False,
            status="STRONG_BULLISH", cross_age_bars=5,
        )
        quality = _compute_setup_quality(0.8, bias, momentum, trend, "TRENDING")
        assert 0.0 <= quality <= 1.0

    def test_high_quality_aligned_setup(self):
        """Aligned, no divergence, fresh, good R/R, clear regime → high quality."""
        bias = TechnicalBias(
            primary_bias="BULLISH", bias_strength=0.8,
            trend_alignment="ALIGNED", risk_reward_ratio=2.5,
        )
        from src.engines.technical.indicators import MomentumResult, TrendResult
        momentum = MomentumResult(rsi=55, rsi_zone="NEUTRAL", stoch_k=60, stoch_d=55,
                                   stoch_zone="NEUTRAL", status="BULLISH")
        trend = TrendResult(
            sma_50=145, sma_200=130, ema_20=148,
            macd_value=2, macd_signal=1, macd_histogram=1,
            price_vs_sma50="ABOVE", price_vs_sma200="ABOVE",
            macd_crossover="BULLISH", golden_cross=True, death_cross=False,
            status="STRONG_BULLISH", cross_age_bars=2,
        )
        quality = _compute_setup_quality(0.85, bias, momentum, trend, "TRENDING")
        assert quality >= 0.70, f"High-quality setup should score ≥0.70 but got {quality}"

    def test_low_quality_divergent_setup(self):
        """Divergent, stale, poor R/R, transitioning → low quality."""
        bias = TechnicalBias(
            primary_bias="BULLISH", bias_strength=0.3,
            trend_alignment="DIVERGENT", risk_reward_ratio=0.5,
        )
        from src.engines.technical.indicators import MomentumResult, TrendResult
        momentum = MomentumResult(rsi=55, rsi_zone="NEUTRAL", stoch_k=60, stoch_d=55,
                                   stoch_zone="NEUTRAL", status="BULLISH",
                                   divergence="BEARISH_DIV", divergence_strength=0.6)
        trend = TrendResult(
            sma_50=145, sma_200=130, ema_20=148,
            macd_value=2, macd_signal=1, macd_histogram=1,
            price_vs_sma50="ABOVE", price_vs_sma200="ABOVE",
            macd_crossover="BULLISH", golden_cross=True, death_cross=False,
            status="STRONG_BULLISH", cross_age_bars=50,
        )
        quality = _compute_setup_quality(0.3, bias, momentum, trend, "TRANSITIONING")
        assert quality < 0.50, f"Low-quality setup should score <0.50 but got {quality}"

    def test_setup_quality_in_e2e(self):
        """ScoringEngine.compute should populate setup_quality in bias."""
        from src.engines.technical.indicators import IndicatorEngine
        tech_data = {
            "current_price": 150,
            "indicators": {
                "sma50": 145, "sma200": 130, "ema20": 148,
                "rsi": 55, "stoch_k": 60, "stoch_d": 55,
                "macd": 2, "macd_signal": 1, "macd_hist": 1,
                "bb_upper": 154, "bb_lower": 146, "bb_basis": 150,
                "atr": 2.25, "volume": 5_000_000, "obv": 1_000_000,
            },
            "ohlcv": _make_trending_ohlcv(100, 60, "up"),
        }
        result = IndicatorEngine.compute(tech_data)
        score = ScoringEngine.compute(result, price=150.0, trend_regime="TRENDING")
        assert 0.0 <= score.bias.setup_quality <= 1.0
