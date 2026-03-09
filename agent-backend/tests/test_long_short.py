"""
tests/test_long_short.py
──────────────────────────────────────────────────────────────────────────────
Tests for the Long/Short position architecture.
"""

import pytest
from src.engines.long_short.models import (
    PositionSide,
    LongShortPosition,
    ExposureMetrics,
    BorrowCostEstimate,
    LongShortPortfolio,
    LongShortResult,
    BorrowTier,
)
from src.engines.long_short.exposure import ExposureCalculator
from src.engines.long_short.borrow_cost import BorrowCostEstimator
from src.engines.long_short.engine import LongShortEngine


# ── Model Tests ──────────────────────────────────────────────────────────────

class TestModels:
    def test_position_side_enum(self):
        assert PositionSide.LONG == "long"
        assert PositionSide.SHORT == "short"

    def test_long_position_pnl(self):
        pos = LongShortPosition(
            ticker="AAPL", side=PositionSide.LONG, weight=0.05,
            entry_price=150.0, current_price=165.0,
        )
        assert pos.unrealized_pnl_pct == pytest.approx(0.10, abs=0.001)

    def test_short_position_pnl(self):
        pos = LongShortPosition(
            ticker="TSLA", side=PositionSide.SHORT, weight=0.05,
            entry_price=200.0, current_price=180.0,
        )
        # Short profits when price drops: -(180-200)/200 = +0.10
        assert pos.unrealized_pnl_pct == pytest.approx(0.10, abs=0.001)

    def test_short_position_loss(self):
        pos = LongShortPosition(
            ticker="TSLA", side=PositionSide.SHORT, weight=0.05,
            entry_price=200.0, current_price=220.0,
        )
        # Short loses when price rises: -(220-200)/200 = -0.10
        assert pos.unrealized_pnl_pct == pytest.approx(-0.10, abs=0.001)

    def test_daily_borrow_cost_long(self):
        pos = LongShortPosition(
            ticker="AAPL", side=PositionSide.LONG, weight=0.05,
            borrow_rate=0.01,
        )
        assert pos.daily_borrow_cost == 0.0  # longs don't pay borrow

    def test_daily_borrow_cost_short(self):
        pos = LongShortPosition(
            ticker="TSLA", side=PositionSide.SHORT, weight=0.05,
            borrow_rate=0.03,
        )
        assert pos.daily_borrow_cost == pytest.approx(0.03 / 252, abs=1e-6)


# ── Exposure Calculator Tests ────────────────────────────────────────────────

class TestExposureCalculator:
    def test_basic_exposure(self):
        longs = [
            LongShortPosition(ticker="A", side=PositionSide.LONG, weight=0.30, beta=1.0),
            LongShortPosition(ticker="B", side=PositionSide.LONG, weight=0.20, beta=1.2),
        ]
        shorts = [
            LongShortPosition(ticker="C", side=PositionSide.SHORT, weight=0.25, beta=0.8),
        ]
        exp = ExposureCalculator.calculate(longs, shorts)

        assert exp.long_exposure == pytest.approx(0.50, abs=0.01)
        assert exp.short_exposure == pytest.approx(0.25, abs=0.01)
        assert exp.gross_exposure == pytest.approx(0.75, abs=0.01)
        assert exp.net_exposure == pytest.approx(0.25, abs=0.01)
        assert exp.long_count == 2
        assert exp.short_count == 1

    def test_beta_exposure(self):
        longs = [LongShortPosition(ticker="A", side=PositionSide.LONG, weight=0.50, beta=1.2)]
        shorts = [LongShortPosition(ticker="B", side=PositionSide.SHORT, weight=0.50, beta=1.2)]
        exp = ExposureCalculator.calculate(longs, shorts)
        # Dollar-matched legs with same beta → beta-neutral
        assert exp.beta_exposure == pytest.approx(0.0, abs=0.01)

    def test_market_neutral_check(self):
        exp = ExposureMetrics(beta_exposure=0.05)
        assert ExposureCalculator.is_market_neutral(exp, threshold=0.10)
        assert not ExposureCalculator.is_market_neutral(exp, threshold=0.01)

    def test_dollar_neutral_check(self):
        exp = ExposureMetrics(net_exposure=0.02)
        assert ExposureCalculator.is_dollar_neutral(exp)


# ── Borrow Cost Tests ────────────────────────────────────────────────────────

class TestBorrowCost:
    def test_general_collateral(self):
        est = BorrowCostEstimator.estimate(
            "AAPL", market_cap=3e12, avg_daily_volume=80e6, short_interest_pct=0.01
        )
        assert est.tier == BorrowTier.GENERAL_COLLATERAL
        assert est.annual_rate < 0.005

    def test_hard_to_borrow(self):
        est = BorrowCostEstimator.estimate(
            "MEME", market_cap=500e6, avg_daily_volume=300e3, short_interest_pct=0.25
        )
        assert est.tier in (BorrowTier.HARD_TO_BORROW, BorrowTier.SPECIAL)

    def test_special_very_high_si(self):
        est = BorrowCostEstimator.estimate(
            "GME", market_cap=5e9, avg_daily_volume=5e6, short_interest_pct=0.50
        )
        assert est.tier == BorrowTier.SPECIAL

    def test_borrow_cost_daily_bps(self):
        est = BorrowCostEstimator.estimate("TEST")
        assert est.estimated_daily_cost_bps >= 0


# ── Engine Tests ─────────────────────────────────────────────────────────────

class TestLongShortEngine:
    def test_basic_construction(self):
        longs = [
            {"ticker": "AAPL", "weight": 0.08, "beta": 1.1, "sector": "Tech"},
            {"ticker": "MSFT", "weight": 0.07, "beta": 1.0, "sector": "Tech"},
        ]
        shorts = [
            {"ticker": "XOM", "weight": 0.06, "beta": 0.9, "sector": "Energy"},
        ]
        result = LongShortEngine.construct(longs, shorts)
        assert isinstance(result, LongShortResult)
        assert len(result.portfolio.long_positions) == 2
        assert len(result.portfolio.short_positions) == 1

    def test_single_position_cap(self):
        longs = [{"ticker": "AAPL", "weight": 0.25}]  # over 10% cap
        shorts = []
        result = LongShortEngine.construct(longs, shorts, max_single_position=0.10)
        assert result.portfolio.long_positions[0].weight <= 0.10
        assert any("capped" in c.lower() for c in result.constraints_applied)

    def test_gross_exposure_scaling(self):
        # Create positions that vastly exceed 200% gross
        longs = [{"ticker": f"L{i}", "weight": 0.50} for i in range(5)]  # 250% long
        shorts = [{"ticker": f"S{i}", "weight": 0.50} for i in range(5)]  # 250% short
        result = LongShortEngine.construct(longs, shorts, max_gross_exposure=2.0)
        assert result.exposure.gross_exposure <= 2.01  # within rounding

    def test_empty_candidates(self):
        result = LongShortEngine.construct([], [])
        assert len(result.violations) > 0
