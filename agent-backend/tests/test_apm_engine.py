"""
tests/test_apm_engine.py — Tests for Autonomous Portfolio Manager.
"""
from __future__ import annotations
import pytest
from src.engines.autonomous_pm.engine import AutonomousPortfolioManager
from src.engines.autonomous_pm.models import (
    APMDashboard, APMPortfolio, PortfolioObjective,
)
from src.engines.autonomous_pm.construction_engine import ConstructionEngine
from src.engines.autonomous_pm.allocation_engine import AllocationEngine


# ── Sample Data ──────────────────────────────────────────────────────────────

PROFILES = [
    {"ticker": "AAPL", "composite_alpha_score": 85, "tier": "A",
     "sector": "Technology", "factor_scores": {"momentum": 70, "growth": 65}},
    {"ticker": "MSFT", "composite_alpha_score": 80, "tier": "A",
     "sector": "Technology", "factor_scores": {"quality": 75, "momentum": 60}},
    {"ticker": "JNJ", "composite_alpha_score": 65, "tier": "B",
     "sector": "Healthcare", "factor_scores": {"quality": 80, "dividend": 70}},
    {"ticker": "JPM", "composite_alpha_score": 70, "tier": "B",
     "sector": "Financials", "factor_scores": {"value": 65, "earnings": 60}},
    {"ticker": "XOM", "composite_alpha_score": 55, "tier": "C",
     "sector": "Energy", "factor_scores": {"value": 55, "cashflow": 60}},
]


class TestConstructionEngine:

    def test_growth_portfolio(self):
        engine = ConstructionEngine()
        p = engine.construct(PortfolioObjective.GROWTH, PROFILES, "expansion")
        assert len(p.positions) > 0
        assert p.objective == PortfolioObjective.GROWTH

    def test_defensive_portfolio(self):
        engine = ConstructionEngine()
        p = engine.construct(PortfolioObjective.DEFENSIVE, PROFILES, "recession")
        assert p.objective == PortfolioObjective.DEFENSIVE

    def test_all_6_portfolios(self):
        engine = ConstructionEngine()
        portfolios = engine.construct_all(PROFILES, "expansion")
        assert len(portfolios) == 6

    def test_weights_sum_to_one(self):
        engine = ConstructionEngine()
        p = engine.construct(PortfolioObjective.BALANCED, PROFILES, "expansion")
        if p.positions:
            total = sum(pos.weight for pos in p.positions)
            assert abs(total - 1.0) < 0.01

    def test_single_position_capped(self):
        engine = ConstructionEngine()
        p = engine.construct(PortfolioObjective.GROWTH, PROFILES, "expansion")
        for pos in p.positions:
            assert pos.weight <= 0.28  # 25% cap + normalization tolerance

    def test_no_profiles_empty_portfolio(self):
        engine = ConstructionEngine()
        p = engine.construct(PortfolioObjective.GROWTH, [], "expansion")
        assert len(p.positions) == 0

    def test_regime_sector_alignment(self):
        engine = ConstructionEngine()
        p = engine.construct(PortfolioObjective.GROWTH, PROFILES, "expansion")
        # Tech should be favored in expansion
        tickers = [pos.ticker for pos in p.positions]
        assert "AAPL" in tickers or "MSFT" in tickers


class TestAllocationEngine:

    def _portfolio_with_positions(self):
        ce = ConstructionEngine()
        return ce.construct(PortfolioObjective.BALANCED, PROFILES, "expansion")

    def test_risk_parity_allocation(self):
        engine = AllocationEngine()
        p = self._portfolio_with_positions()
        vols = {pos.ticker: 0.15 + i * 0.05 for i, pos in enumerate(p.positions)}
        engine.optimise(p, vols, regime="expansion")
        total = sum(pos.weight for pos in p.positions)
        assert abs(total - 1.0) < 0.01

    def test_min_variance_favors_low_vol(self):
        engine = AllocationEngine()
        p = self._portfolio_with_positions()
        if len(p.positions) >= 2:
            vols = {p.positions[0].ticker: 0.10}
            for pos in p.positions[1:]:
                vols[pos.ticker] = 0.40
            from src.engines.autonomous_pm.models import AllocationMethodAPM
            engine.optimise(p, vols, method=AllocationMethodAPM.MIN_VARIANCE)
            # Lowest vol should have highest weight
            sorted_pos = sorted(p.positions, key=lambda x: x.weight, reverse=True)
            assert sorted_pos[0].ticker == p.positions[0].ticker

    def test_portfolio_vol_estimated(self):
        engine = AllocationEngine()
        p = self._portfolio_with_positions()
        vols = {pos.ticker: 0.20 for pos in p.positions}
        engine.optimise(p, vols)
        assert p.expected_volatility > 0


class TestAPMPipeline:

    def test_full_pipeline(self):
        apm = AutonomousPortfolioManager()
        dashboard = apm.manage(
            alpha_profiles=PROFILES, regime="expansion",
            portfolio_returns=[0.01, -0.005, 0.008, 0.003, -0.002] * 10,
            benchmark_returns=[0.005, -0.003, 0.006, 0.002, -0.001] * 10,
        )
        assert isinstance(dashboard, APMDashboard)
        assert len(dashboard.portfolios) > 0
        assert len(dashboard.explanations) > 0

    def test_recssion_regime(self):
        apm = AutonomousPortfolioManager()
        dashboard = apm.manage(alpha_profiles=PROFILES, regime="recession")
        assert dashboard.active_regime == "recession"

    def test_no_profiles_still_runs(self):
        apm = AutonomousPortfolioManager()
        dashboard = apm.manage(alpha_profiles=[], regime="expansion")
        assert isinstance(dashboard, APMDashboard)
