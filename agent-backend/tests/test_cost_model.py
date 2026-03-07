"""
tests/test_cost_model.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Transaction Cost & Slippage Model.

Covers:
  - SpreadEstimator (Corwin-Schultz, empirical fallback, fixed mode)
  - ImpactEstimator (square-root model)
  - CostModelEngine (event adjustment, profile computation)
  - Pydantic model contracts
  - DB table definition
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.engines.backtesting.models import SignalEvent
from src.engines.alpha_signals.models import SignalStrength
from src.engines.cost_model.estimators import ImpactEstimator, SpreadEstimator
from src.engines.cost_model.engine import CostModelEngine, _classify_resilience, _classify_tier
from src.engines.cost_model.models import (
    CostModelConfig,
    CostModelReport,
    CostResilience,
    SignalCostProfile,
    SpreadMethod,
    TradeCostBreakdown,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_ohlcv(n_days: int = 60, base_price: float = 100.0) -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    dates = pd.bdate_range(start="2024-01-02", periods=n_days)
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, n_days)
    prices = base_price * np.cumprod(1 + returns)
    highs = prices * (1 + np.abs(np.random.normal(0, 0.01, n_days)))
    lows = prices * (1 - np.abs(np.random.normal(0, 0.01, n_days)))
    volumes = np.random.randint(1_000_000, 10_000_000, n_days).astype(float)

    return pd.DataFrame({
        "Open": prices * 0.999,
        "High": highs,
        "Low": lows,
        "Close": prices,
        "Volume": volumes,
    }, index=dates)


def _make_signal_event(
    signal_id: str = "test.signal",
    ticker: str = "AAPL",
    price: float = 150.0,
    fwd_returns: dict[int, float] | None = None,
    excess_returns: dict[int, float] | None = None,
) -> SignalEvent:
    """Create a synthetic signal event."""
    return SignalEvent(
        signal_id=signal_id,
        ticker=ticker,
        fired_date=date(2024, 3, 15),
        strength=SignalStrength.MODERATE,
        confidence=0.7,
        value=65.0,
        price_at_fire=price,
        forward_returns=fwd_returns or {5: 0.02, 10: 0.035, 20: 0.05},
        benchmark_returns={5: 0.005, 10: 0.01, 20: 0.015},
        excess_returns=excess_returns or {5: 0.015, 10: 0.025, 20: 0.035},
    )


# ─── Spread Estimator Tests ─────────────────────────────────────────────────

class TestSpreadEstimator:
    """Tests for bid-ask spread estimation."""

    def test_empirical_fallback_high_volume(self):
        # High volume ($100M ADV) → tight spread
        spread = SpreadEstimator.empirical_fallback(100_000_000)
        assert 0.0001 < spread < 0.005  # 1–50 bps
        assert spread < SpreadEstimator.empirical_fallback(1_000_000)

    def test_empirical_fallback_low_volume(self):
        # Low volume ($100K ADV) → wide spread
        spread = SpreadEstimator.empirical_fallback(100_000)
        assert spread > 0.001  # > 10 bps

    def test_empirical_fallback_zero_volume(self):
        spread = SpreadEstimator.empirical_fallback(0)
        assert spread > 0  # Should not crash, returns a value

    def test_corwin_schultz_synthetic(self):
        ohlcv = _make_ohlcv(60)
        spread = SpreadEstimator.corwin_schultz(ohlcv, 50)
        # Should return a reasonable positive spread
        assert spread >= 0.0001
        assert spread <= 0.05

    def test_corwin_schultz_insufficient_data(self):
        ohlcv = _make_ohlcv(3)
        spread = SpreadEstimator.corwin_schultz(ohlcv, 1)
        # Should fallback gracefully
        assert spread >= 0

    def test_estimate_fixed_mode(self):
        est = SpreadEstimator()
        spread = est.estimate(_make_ohlcv(), 30, method="fixed", fixed_bps=15.0)
        assert spread == pytest.approx(15.0 / 10_000, rel=1e-6)

    def test_estimate_auto_mode(self):
        est = SpreadEstimator()
        spread = est.estimate(_make_ohlcv(), 40, method="auto")
        assert spread > 0


# ─── Impact Estimator Tests ─────────────────────────────────────────────────

class TestImpactEstimator:
    """Tests for market impact estimation."""

    def test_basic_impact(self):
        impact = ImpactEstimator.compute(
            daily_volatility=0.02,
            adv_shares=5_000_000,
            trade_usd=100_000,
            price=150.0,
            eta=0.1,
        )
        assert impact > 0
        assert impact < 0.01  # Should be small for liquid stock

    def test_higher_volume_lower_impact(self):
        high_vol = ImpactEstimator.compute(
            daily_volatility=0.02,
            adv_shares=10_000_000,
            trade_usd=100_000,
            price=150.0,
            eta=0.1,
        )
        low_vol = ImpactEstimator.compute(
            daily_volatility=0.02,
            adv_shares=100_000,
            trade_usd=100_000,
            price=150.0,
            eta=0.1,
        )
        assert high_vol < low_vol

    def test_zero_volume_no_crash(self):
        impact = ImpactEstimator.compute(
            daily_volatility=0.02, adv_shares=0,
            trade_usd=100_000, price=150.0,
        )
        assert impact == 0.0

    def test_zero_price_no_crash(self):
        impact = ImpactEstimator.compute(
            daily_volatility=0.02, adv_shares=5_000_000,
            trade_usd=100_000, price=0,
        )
        assert impact == 0.0


# ─── CostModelEngine Tests ──────────────────────────────────────────────────

class TestCostModelEngine:
    """Tests for the cost adjustment pipeline."""

    def test_adjust_events_produces_lower_returns(self):
        ohlcv = _make_ohlcv(300)
        event = _make_signal_event()
        ohlcv_data = {"AAPL": ohlcv}

        config = CostModelConfig(
            slippage_bps=5.0,
            commission_bps=5.0,
            spread_method=SpreadMethod.FIXED,
            fixed_spread_bps=10.0,
        )
        engine = CostModelEngine(config)
        adjusted, breakdowns = engine.adjust_events([event], ohlcv_data)

        assert len(adjusted) == 1
        assert len(breakdowns) == 1

        # Adjusted returns should be lower than raw
        for w in [5, 10, 20]:
            assert adjusted[0].forward_returns[w] < event.forward_returns[w]

    def test_cost_breakdown_components(self):
        ohlcv = _make_ohlcv(300)
        event = _make_signal_event()

        config = CostModelConfig(
            slippage_bps=10.0,
            commission_bps=8.0,
            spread_method=SpreadMethod.FIXED,
            fixed_spread_bps=20.0,
            round_trip=True,
        )
        engine = CostModelEngine(config)
        _, breakdowns = engine.adjust_events([event], {"AAPL": ohlcv})

        bd = breakdowns[0]
        assert bd.total_cost > 0
        assert bd.slippage_cost > 0
        assert bd.commission_cost > 0
        assert bd.spread_cost > 0
        # Total should be sum of components
        component_sum = bd.spread_cost + bd.impact_cost + bd.slippage_cost + bd.commission_cost
        assert abs(bd.total_cost - component_sum) < 1e-6

    def test_no_cost_when_all_zero(self):
        event = _make_signal_event()
        config = CostModelConfig(
            eta=0.0,
            slippage_bps=0.0,
            commission_bps=0.0,
            spread_method=SpreadMethod.FIXED,
            fixed_spread_bps=0.0,
        )
        engine = CostModelEngine(config)
        adjusted, breakdowns = engine.adjust_events([event], {})

        bd = breakdowns[0]
        assert bd.total_cost == 0.0
        # Returns should be unchanged
        for w in event.forward_returns:
            assert adjusted[0].forward_returns[w] == event.forward_returns[w]

    def test_build_report(self):
        event = _make_signal_event()
        config = CostModelConfig(
            spread_method=SpreadMethod.FIXED,
            fixed_spread_bps=10.0,
        )
        engine = CostModelEngine(config)
        adjusted, breakdowns = engine.adjust_events([event], {})

        report = engine.build_report(
            [event], adjusted, breakdowns, [5, 10, 20],
        )
        assert isinstance(report, CostModelReport)
        assert len(report.signal_profiles) == 1
        profile = report.signal_profiles[0]
        assert profile.signal_id == "test.signal"
        assert profile.total_events == 1


# ─── Classification Tests ───────────────────────────────────────────────────

class TestClassification:
    """Tests for cost resilience and tier classification."""

    def test_resilience_classes(self):
        assert _classify_resilience(0.80) == CostResilience.RESILIENT
        assert _classify_resilience(0.70) == CostResilience.RESILIENT
        assert _classify_resilience(0.50) == CostResilience.MODERATE
        assert _classify_resilience(0.40) == CostResilience.MODERATE
        assert _classify_resilience(0.39) == CostResilience.FRAGILE
        assert _classify_resilience(0.0) == CostResilience.FRAGILE

    def test_tier_classification(self):
        assert _classify_tier(2.0, 0.65) == "A"
        assert _classify_tier(1.0, 0.58) == "B"
        assert _classify_tier(0.5, 0.52) == "C"
        assert _classify_tier(0.1, 0.45) == "D"


# ─── Model Tests ─────────────────────────────────────────────────────────────

class TestCostModels:
    """Tests for Pydantic model contracts."""

    def test_config_defaults(self):
        cfg = CostModelConfig()
        assert cfg.eta == 0.1
        assert cfg.assumed_trade_usd == 100_000
        assert cfg.slippage_bps == 5.0
        assert cfg.commission_bps == 5.0
        assert cfg.spread_method == SpreadMethod.AUTO
        assert cfg.round_trip is True

    def test_trade_breakdown_serialization(self):
        bd = TradeCostBreakdown(
            signal_id="test.sig",
            ticker="AAPL",
            fired_date=date(2024, 3, 15),
            total_cost=0.003,
        )
        d = bd.model_dump()
        assert d["signal_id"] == "test.sig"
        assert d["total_cost"] == 0.003

    def test_signal_cost_profile_defaults(self):
        p = SignalCostProfile(signal_id="test")
        assert p.cost_resilience_class == CostResilience.FRAGILE
        assert p.cost_adjusted_tier == "D"
        assert p.avg_total_cost == 0.0


# ─── DB Table Tests ──────────────────────────────────────────────────────────

class TestCostDBTable:
    """Verify cost model table exists in the ORM."""

    def test_cost_model_profiles_table(self):
        from src.data.database import CostModelProfileRecord
        assert CostModelProfileRecord.__tablename__ == "cost_model_profiles"
        cols = {c.name for c in CostModelProfileRecord.__table__.columns}
        assert "run_id" in cols
        assert "signal_id" in cols
        assert "raw_sharpe_20" in cols
        assert "adjusted_sharpe_20" in cols
        assert "cost_resilience" in cols
        assert "breakeven_cost_bps" in cols
