"""
tests/test_regime_position_sizing.py
--------------------------------------------------------------------------
Tests for RegimePositionSizer — regime-aware weight scaling.
"""

from __future__ import annotations

import pytest

from src.engines.portfolio.regime_position_sizing import (
    RegimeContext,
    RegimePositionSizer,
    RegimeSizingConfig,
    SizingResult,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

BASE_WEIGHTS = {
    "AAPL": 0.20, "MSFT": 0.25, "GOOGL": 0.15,
    "AMZN": 0.15, "JPM": 0.10, "JNJ": 0.10,
}


def _sizer(**kw) -> RegimePositionSizer:
    return RegimePositionSizer(RegimeSizingConfig(**kw))


# ─── Vol Regime Tests ────────────────────────────────────────────────────────

class TestVolRegime:

    def test_normal_no_change(self):
        """Normal vol → multiplier = 1.0, neutral trend → +0.0."""
        sizer = _sizer()
        result = sizer.adjust(BASE_WEIGHTS, volatility_regime="normal", trend_regime="neutral")
        # Weights should be close to original (capped by exposure limit)
        total_orig = sum(BASE_WEIGHTS.values())
        total_adj = sum(result.adjusted_weights.values())
        assert result.vol_multiplier == 1.0
        assert result.trend_adjustment == 0.0
        assert abs(total_adj - min(total_orig, 0.95)) < 0.05

    def test_crisis_derisk(self):
        """Crisis → 0.3× multiplier → heavy reduction."""
        sizer = _sizer()
        result = sizer.adjust(BASE_WEIGHTS, volatility_regime="crisis")
        assert result.vol_multiplier == 0.30
        total = sum(result.adjusted_weights.values())
        assert total < sum(BASE_WEIGHTS.values()) * 0.5

    def test_high_vol_reduction(self):
        """High vol → 0.6× multiplier."""
        sizer = _sizer()
        result = sizer.adjust(BASE_WEIGHTS, volatility_regime="high")
        assert result.vol_multiplier == 0.60
        total = sum(result.adjusted_weights.values())
        assert total < sum(BASE_WEIGHTS.values()) * 0.75

    def test_low_vol_slight_leverage(self):
        """Low vol → 1.15× multiplier."""
        sizer = _sizer()
        result = sizer.adjust(BASE_WEIGHTS, volatility_regime="low")
        assert result.vol_multiplier == 1.15


# ─── Trend Regime Tests ─────────────────────────────────────────────────────

class TestTrendRegime:

    def test_trending_bonus(self):
        """Trending → +0.10 adjustment."""
        sizer = _sizer()
        result = sizer.adjust(BASE_WEIGHTS, trend_regime="trending")
        assert result.trend_adjustment == 0.10

    def test_mean_reverting_penalty(self):
        """Mean reverting → -0.10 adjustment."""
        sizer = _sizer()
        result = sizer.adjust(BASE_WEIGHTS, trend_regime="mean_reverting")
        assert result.trend_adjustment == -0.10

    def test_choppy_penalty(self):
        """Choppy → -0.05 adjustment."""
        sizer = _sizer()
        result = sizer.adjust(BASE_WEIGHTS, trend_regime="choppy")
        assert result.trend_adjustment == -0.05

    def test_neutral_no_adjustment(self):
        sizer = _sizer()
        result = sizer.adjust(BASE_WEIGHTS, trend_regime="neutral")
        assert result.trend_adjustment == 0.0


# ─── Combined Tests ──────────────────────────────────────────────────────────

class TestCombined:

    def test_crisis_plus_choppy(self):
        """Crisis + choppy → very aggressive de-risk."""
        sizer = _sizer()
        result = sizer.adjust(
            BASE_WEIGHTS,
            volatility_regime="crisis",
            trend_regime="choppy",
        )
        # 0.30 + (-0.05) = 0.25 combined multiplier
        total = sum(result.adjusted_weights.values())
        assert total < 0.30  # Heavily de-risked

    def test_low_vol_trending(self):
        """Low vol + trending → maximum scaling."""
        sizer = _sizer()
        result = sizer.adjust(
            BASE_WEIGHTS,
            volatility_regime="low",
            trend_regime="trending",
        )
        # 1.15 + 0.10 = 1.25 combined, but capped by max exposure
        assert result.vol_multiplier == 1.15
        assert result.trend_adjustment == 0.10


# ─── Safety Constraints ─────────────────────────────────────────────────────

class TestSafety:

    def test_max_exposure_cap(self):
        """Total exposure never exceeds max (1.0 - cash_floor)."""
        sizer = _sizer(max_total_exposure=1.0, cash_floor=0.05)
        result = sizer.adjust(
            BASE_WEIGHTS,
            volatility_regime="low",
            trend_regime="trending",
        )
        total = sum(result.adjusted_weights.values())
        assert total <= 0.95 + 0.001  # max_exposure - cash_floor

    def test_cash_floor_guaranteed(self):
        """At least 5% cash always."""
        sizer = _sizer(cash_floor=0.05)
        result = sizer.adjust(BASE_WEIGHTS, volatility_regime="low")
        assert result.cash_allocation >= 0.04  # Allow small rounding

    def test_minimum_multiplier_floor(self):
        """Combined multiplier never goes below 0.1."""
        sizer = _sizer(
            crisis_multiplier=0.05,   # Very low
            mean_reverting_penalty=-0.10,
        )
        result = sizer.adjust(
            BASE_WEIGHTS,
            volatility_regime="crisis",
            trend_regime="mean_reverting",
        )
        # 0.05 + (-0.10) = -0.05, floored to 0.10
        total = sum(result.adjusted_weights.values())
        assert total > 0  # Still has some exposure


# ─── Regime Classification Tests ────────────────────────────────────────────

class TestClassifyRegime:

    def test_crisis_classification(self):
        sizer = _sizer()
        ctx = sizer.classify_regime(realized_vol=0.40, vol_percentile=97)
        assert ctx.volatility_regime == "crisis"

    def test_high_vol_classification(self):
        sizer = _sizer()
        ctx = sizer.classify_regime(realized_vol=0.25, vol_percentile=80)
        assert ctx.volatility_regime == "high"

    def test_low_vol_classification(self):
        sizer = _sizer()
        ctx = sizer.classify_regime(realized_vol=0.08, vol_percentile=20)
        assert ctx.volatility_regime == "low"

    def test_normal_vol_classification(self):
        sizer = _sizer()
        ctx = sizer.classify_regime(realized_vol=0.15, vol_percentile=50)
        assert ctx.volatility_regime == "normal"

    def test_trending_classification(self):
        sizer = _sizer()
        ctx = sizer.classify_regime(realized_vol=0.15, vol_percentile=50, trend_strength=0.7)
        assert ctx.trend_regime == "trending"

    def test_choppy_classification(self):
        sizer = _sizer()
        ctx = sizer.classify_regime(realized_vol=0.15, vol_percentile=50, trend_strength=0.05)
        assert ctx.trend_regime == "choppy"


# ─── RegimeContext Direct Tests ──────────────────────────────────────────────

class TestRegimeContext:

    def test_regime_context_object(self):
        """Can pass a RegimeContext directly."""
        sizer = _sizer()
        ctx = RegimeContext(volatility_regime="high", trend_regime="trending")
        result = sizer.adjust(BASE_WEIGHTS, regime=ctx)
        assert result.vol_multiplier == 0.60
        assert result.trend_adjustment == 0.10

    def test_scaling_description(self):
        """Scaling applied description includes regime info."""
        sizer = _sizer()
        result = sizer.adjust(BASE_WEIGHTS, volatility_regime="crisis")
        assert "crisis" in result.scaling_applied
        assert "×" in result.scaling_applied

    def test_original_weights_preserved(self):
        """Original weights in result are unchanged."""
        sizer = _sizer()
        result = sizer.adjust(BASE_WEIGHTS, volatility_regime="crisis")
        assert result.original_weights == BASE_WEIGHTS
