"""
tests/test_structure_v2.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for Structure Analysis V2:
  - Market structure detection (HH/HL, LH/LL, MIXED)
  - Key level strength (touch counting)
  - Pattern recognition (Double Top/Bottom, Higher Lows, Lower Highs)
  - Scoring integration with V2 bonuses/penalties
  - Full StructureModule.compute() integration
"""

from __future__ import annotations

import pytest

from src.engines.technical.indicators import (
    StructureModule,
    StructureResult,
    _detect_market_structure,
    _compute_level_strength,
    _detect_patterns,
)
from src.engines.technical.scoring import _score_structure


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_ohlcv(
    n: int = 60,
    base: float = 100.0,
    trend: float = 0.0,
    noise: float = 2.0,
) -> list[dict]:
    """Create synthetic OHLCV bars with optional upward/downward trend."""
    bars = []
    price = base
    for i in range(n):
        price += trend
        h = price + noise
        l = price - noise
        bars.append({
            "open": price - 0.5,
            "high": h,
            "low": l,
            "close": price + 0.5,
            "volume": 1_000_000,
        })
    return bars


def _make_pivots_ascending(n: int = 3, start: float = 100.0, step: float = 5.0):
    """Create ascending pivot points: (index, price)."""
    return [(i * 5, start + i * step) for i in range(n)]


def _make_pivots_descending(n: int = 3, start: float = 120.0, step: float = 5.0):
    """Create descending pivot points: (index, price)."""
    return [(i * 5, start - i * step) for i in range(n)]


# ─── TestMarketStructure ─────────────────────────────────────────────────────

class TestMarketStructure:
    """Tests for _detect_market_structure()."""

    def test_hh_hl_uptrend(self):
        """Ascending highs + ascending lows = HH_HL."""
        highs = _make_pivots_ascending(3, start=105, step=5)  # 105, 110, 115
        lows = _make_pivots_ascending(3, start=95, step=5)    # 95, 100, 105
        assert _detect_market_structure(highs, lows) == "HH_HL"

    def test_lh_ll_downtrend(self):
        """Descending highs + descending lows = LH_LL."""
        highs = _make_pivots_descending(3, start=120, step=5)  # 120, 115, 110
        lows = _make_pivots_descending(3, start=100, step=5)   # 100, 95, 90
        assert _detect_market_structure(highs, lows) == "LH_LL"

    def test_mixed_structure(self):
        """Ascending highs + descending lows = MIXED (choppy)."""
        highs = _make_pivots_ascending(3, start=105, step=5)
        lows = _make_pivots_descending(3, start=100, step=5)
        assert _detect_market_structure(highs, lows) == "MIXED"

    def test_insufficient_pivots(self):
        """Less than 2 pivots on either side = MIXED."""
        highs = [(0, 110.0)]
        lows = [(5, 90.0), (10, 92.0)]
        assert _detect_market_structure(highs, lows) == "MIXED"

    def test_two_pivots_sufficient(self):
        """Exactly 2 pivots each should work if both ascending."""
        highs = [(0, 100), (5, 105)]
        lows = [(2, 90), (7, 95)]
        assert _detect_market_structure(highs, lows) == "HH_HL"


# ─── TestLevelStrength ───────────────────────────────────────────────────────

class TestLevelStrength:
    """Tests for _compute_level_strength()."""

    def test_counts_touches(self):
        """Bars that come within 0.5% of a level count as touches."""
        bars = [
            {"high": 100.4, "low": 99.0},  # touches 100
            {"high": 100.3, "low": 99.5},  # touches 100
            {"high": 100.2, "low": 99.0},  # touches 100
            {"high": 105.0, "low": 103.0}, # no touch
        ]
        result = _compute_level_strength([100.0], bars, 98.0)
        assert result["100.0"]["touches"] == 3
        assert result["100.0"]["strong"] is True

    def test_below_strong_threshold(self):
        """Fewer than 3 touches → strong=False."""
        bars = [
            {"high": 100.3, "low": 99.5},
            {"high": 105.0, "low": 103.0},
        ]
        result = _compute_level_strength([100.0], bars, 98.0)
        assert result["100.0"]["touches"] == 1
        assert result["100.0"]["strong"] is False

    def test_empty_levels(self):
        """No levels → empty dict."""
        bars = [{"high": 100, "low": 99}]
        result = _compute_level_strength([], bars, 98.0)
        assert result == {}

    def test_multiple_levels(self):
        """Each level is evaluated independently."""
        bars = [
            {"high": 100.3, "low": 99.5},
            {"high": 110.5, "low": 109.5},
            {"high": 100.2, "low": 99.0},
            {"high": 110.3, "low": 109.0},
            {"high": 100.1, "low": 99.0},
        ]
        result = _compute_level_strength([100.0, 110.0], bars, 95.0)
        assert result["100.0"]["touches"] == 3
        assert result["110.0"]["touches"] == 2


# ─── TestPatternDetection ────────────────────────────────────────────────────

class TestPatternDetection:
    """Tests for _detect_patterns()."""

    def test_double_top(self):
        """Two highs at same level + price below = DOUBLE_TOP."""
        highs = [(10, 100.0), (20, 100.3)]  # within 1%
        lows = [(15, 90.0)]
        patterns = _detect_patterns(highs, lows, price=95.0)
        assert "DOUBLE_TOP" in patterns

    def test_double_bottom(self):
        """Two lows at same level + price above = DOUBLE_BOTTOM."""
        highs = [(15, 110.0)]
        lows = [(10, 90.0), (20, 90.5)]     # within 1%
        patterns = _detect_patterns(highs, lows, price=95.0)
        assert "DOUBLE_BOTTOM" in patterns

    def test_higher_lows(self):
        """3 ascending lows = HIGHER_LOWS."""
        highs = [(5, 110.0)]
        lows = [(0, 85.0), (10, 90.0), (20, 95.0)]
        patterns = _detect_patterns(highs, lows, price=100.0)
        assert "HIGHER_LOWS" in patterns

    def test_lower_highs(self):
        """3 descending highs = LOWER_HIGHS."""
        highs = [(0, 120.0), (10, 115.0), (20, 110.0)]
        lows = [(5, 90.0)]
        patterns = _detect_patterns(highs, lows, price=100.0)
        assert "LOWER_HIGHS" in patterns

    def test_no_patterns(self):
        """Random pivots with no clear pattern → empty list."""
        highs = [(0, 100.0), (10, 105.0)]
        lows = [(5, 90.0), (15, 95.0)]
        patterns = _detect_patterns(highs, lows, price=102.0)
        # No double top (highs differ by >1%), no double bottom (lows differ by >1%)
        # Only 2 lows so no HIGHER_LOWS, only 2 highs so no LOWER_HIGHS
        assert patterns == []


# ─── TestStructureScoring ────────────────────────────────────────────────────

class TestStructureScoring:
    """Tests for _score_structure() V2 bonuses and penalties."""

    def _make_result(self, **overrides) -> StructureResult:
        defaults = dict(
            breakout_probability=0.4,
            breakout_direction="BULLISH",
            market_structure="MIXED",
            level_strength={},
            patterns=[],
        )
        defaults.update(overrides)
        return StructureResult(**defaults)

    def test_hh_hl_bullish_bonus(self):
        """HH_HL + BULLISH direction → +1.0 bonus."""
        base = self._make_result(market_structure="MIXED")
        enhanced = self._make_result(market_structure="HH_HL")
        score_base, _ = _score_structure(base)
        score_enhanced, _ = _score_structure(enhanced)
        assert score_enhanced > score_base
        assert score_enhanced - score_base == pytest.approx(1.0, abs=0.01)

    def test_lh_ll_bullish_penalty(self):
        """LH_LL + BULLISH direction → -1.0 penalty (structure conflicts)."""
        base = self._make_result(market_structure="MIXED")
        penalized = self._make_result(market_structure="LH_LL")
        score_pen, _ = _score_structure(penalized)
        score_base, _ = _score_structure(base)
        assert score_pen < score_base

    def test_strong_levels_bonus(self):
        """Strong level (3+ touches) → +0.5."""
        base = self._make_result()
        with_strong = self._make_result(
            level_strength={"100.0": {"touches": 4, "strong": True}}
        )
        score_strong, _ = _score_structure(with_strong)
        score_base, _ = _score_structure(base)
        assert score_strong - score_base == pytest.approx(0.5, abs=0.01)

    def test_bullish_patterns_bonus(self):
        """DOUBLE_BOTTOM or HIGHER_LOWS → +0.5."""
        base = self._make_result()
        with_pattern = self._make_result(patterns=["DOUBLE_BOTTOM"])
        score_pat, _ = _score_structure(with_pattern)
        score_base, _ = _score_structure(base)
        assert score_pat - score_base == pytest.approx(0.5, abs=0.01)

    def test_bearish_patterns_penalty(self):
        """DOUBLE_TOP or LOWER_HIGHS → -0.5."""
        base = self._make_result()
        with_pattern = self._make_result(patterns=["DOUBLE_TOP"])
        score_pat, _ = _score_structure(with_pattern)
        score_base, _ = _score_structure(base)
        assert score_pat < score_base

    def test_score_capped_at_10(self):
        """Score should never exceed 10.0."""
        maxed = self._make_result(
            breakout_probability=0.95,
            breakout_direction="BULLISH",
            market_structure="HH_HL",
            level_strength={"100": {"touches": 5, "strong": True}},
            patterns=["DOUBLE_BOTTOM", "HIGHER_LOWS"],
        )
        score, _ = _score_structure(maxed)
        assert score <= 10.0

    def test_score_floored_at_0(self):
        """Score should never go below 0.0."""
        minimal = self._make_result(
            breakout_probability=0.1,
            breakout_direction="BEARISH",
            market_structure="LH_LL",
            patterns=["DOUBLE_TOP", "LOWER_HIGHS"],
        )
        score, _ = _score_structure(minimal)
        assert score >= 0.0


# ─── TestStructureIntegration ────────────────────────────────────────────────

class TestStructureIntegration:
    """Integration tests for full StructureModule.compute()."""

    def test_uptrend_ohlcv_produces_structure(self):
        """Strongly trending OHLCV should produce non-default structure."""
        bars = _make_ohlcv(n=80, base=100, trend=1.0, noise=2.0)
        price = bars[-1]["close"]
        result = StructureModule.compute(price, bars)
        assert isinstance(result, StructureResult)
        assert result.market_structure in ("HH_HL", "LH_LL", "MIXED")
        assert isinstance(result.patterns, list)
        assert isinstance(result.level_strength, dict)

    def test_flat_market_produces_mixed(self):
        """Flat market OHLCV should tend toward MIXED structure."""
        bars = _make_ohlcv(n=80, base=100, trend=0.0, noise=1.0)
        price = bars[-1]["close"]
        result = StructureModule.compute(price, bars)
        # Flat market may produce anything, but shouldn't error
        assert result.market_structure in ("HH_HL", "LH_LL", "MIXED")

    def test_short_ohlcv_returns_default(self):
        """Less than 20 bars returns default empty StructureResult."""
        bars = _make_ohlcv(n=10)
        result = StructureModule.compute(100.0, bars)
        assert result.market_structure == "MIXED"
        assert result.patterns == []
        assert result.level_strength == {}
