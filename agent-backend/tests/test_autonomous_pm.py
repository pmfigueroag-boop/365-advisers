"""
tests/test_autonomous_pm.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive test suite for the Autonomous Portfolio Manager (APM).

Covers: Models, Construction Engine, Allocation Engine, Rebalancing Engine,
        Risk Management Engine, Performance Engine, APM Facade.
"""

from __future__ import annotations

import math
import pytest

# ── Models ───────────────────────────────────────────────────────────────────

from src.engines.autonomous_pm.models import (
    AllocationMethodAPM,
    APMDashboard,
    APMPortfolio,
    APMPosition,
    PerformanceSnapshot,
    PortfolioObjective,
    PortfolioRiskReport,
    RebalanceRecommendation,
    RebalanceTrigger,
    RebalanceUrgency,
    RiskViolation,
    RiskViolationType,
    RiskViolationSeverity,
)


class TestModels:
    def test_portfolio_objective_values(self):
        assert PortfolioObjective.GROWTH.value == "growth"
        assert len(PortfolioObjective) == 6

    def test_allocation_methods(self):
        assert AllocationMethodAPM.RISK_PARITY.value == "risk_parity"
        assert len(AllocationMethodAPM) == 6

    def test_apm_portfolio_defaults(self):
        p = APMPortfolio(objective=PortfolioObjective.GROWTH)
        assert p.total_weight == 1.0
        assert p.positions == []

    def test_apm_position(self):
        pos = APMPosition(ticker="AAPL", weight=0.2, alpha_score=80)
        assert pos.ticker == "AAPL"
        assert pos.weight == 0.2

    def test_rebalance_triggers(self):
        assert RebalanceTrigger.REGIME_CHANGE.value == "regime_change"
        assert len(RebalanceTrigger) == 5

    def test_dashboard_defaults(self):
        d = APMDashboard()
        assert d.version == "1.0.0"
        assert d.portfolios == []


# ── Construction Engine ──────────────────────────────────────────────────────

from src.engines.autonomous_pm.construction_engine import ConstructionEngine


class TestConstructionEngine:
    def setup_method(self):
        self.engine = ConstructionEngine()
        self.profiles = [
            {"ticker": "NVDA", "composite_alpha_score": 88, "sector": "Technology", "factor_scores": {"momentum": 91, "growth": 85}, "tier": "elite"},
            {"ticker": "AAPL", "composite_alpha_score": 82, "sector": "Technology", "factor_scores": {"quality": 82, "momentum": 65}, "tier": "strong_alpha"},
            {"ticker": "JPM", "composite_alpha_score": 76, "sector": "Financials", "factor_scores": {"value": 82, "quality": 68}, "tier": "alpha"},
            {"ticker": "JNJ", "composite_alpha_score": 68, "sector": "Healthcare", "factor_scores": {"quality": 80, "value": 75}, "tier": "alpha"},
            {"ticker": "XOM", "composite_alpha_score": 58, "sector": "Energy", "factor_scores": {"value": 70, "macro": 50}, "tier": "alpha"},
            {"ticker": "KO", "composite_alpha_score": 52, "sector": "Consumer Staples", "factor_scores": {"quality": 85, "dividend": 90}, "tier": "alpha"},
        ]

    def test_construct_growth(self):
        p = self.engine.construct(PortfolioObjective.GROWTH, self.profiles, "expansion")
        assert p.objective == PortfolioObjective.GROWTH
        assert len(p.positions) > 0
        assert all(pos.alpha_score >= 60 for pos in p.positions)

    def test_construct_defensive(self):
        p = self.engine.construct(PortfolioObjective.DEFENSIVE, self.profiles, "recession")
        assert p.objective == PortfolioObjective.DEFENSIVE

    def test_construct_all_returns_six(self):
        result = self.engine.construct_all(self.profiles, "expansion")
        assert len(result) == 6
        styles = {p.objective for p in result}
        assert styles == set(PortfolioObjective)

    def test_weights_sum_to_one(self):
        p = self.engine.construct(PortfolioObjective.GROWTH, self.profiles)
        if p.positions:
            total = sum(pos.weight for pos in p.positions)
            assert abs(total - 1.0) < 0.02

    def test_empty_profiles_returns_empty_positions(self):
        p = self.engine.construct(PortfolioObjective.GROWTH, [])
        assert len(p.positions) == 0

    def test_opportunity_boost(self):
        opps = [{"ticker": "NVDA"}]
        p1 = self.engine.construct(PortfolioObjective.GROWTH, self.profiles)
        p2 = self.engine.construct(PortfolioObjective.GROWTH, self.profiles, opportunities=opps)
        # NVDA should have same or higher weight with opportunity boost
        w1 = next((pos.weight for pos in p1.positions if pos.ticker == "NVDA"), 0)
        w2 = next((pos.weight for pos in p2.positions if pos.ticker == "NVDA"), 0)
        assert w2 >= w1

    def test_max_position_cap(self):
        p = self.engine.construct(PortfolioObjective.GROWTH, self.profiles)
        for pos in p.positions:
            assert pos.weight <= 0.30  # 25% cap + normalization headroom


# ── Allocation Engine ────────────────────────────────────────────────────────

from src.engines.autonomous_pm.allocation_engine import AllocationEngine


class TestAllocationEngine:
    def setup_method(self):
        self.engine = AllocationEngine()
        self.portfolio = APMPortfolio(
            objective=PortfolioObjective.GROWTH,
            positions=[
                APMPosition(ticker="NVDA", weight=0.3, alpha_score=88, sector="Technology"),
                APMPosition(ticker="AAPL", weight=0.25, alpha_score=82, sector="Technology"),
                APMPosition(ticker="JPM", weight=0.25, alpha_score=76, sector="Financials"),
                APMPosition(ticker="JNJ", weight=0.2, alpha_score=68, sector="Healthcare"),
            ],
        )
        self.vols = {"NVDA": 0.35, "AAPL": 0.22, "JPM": 0.18, "JNJ": 0.14}

    def test_risk_parity(self):
        result = self.engine.optimise(self.portfolio, self.vols, method=AllocationMethodAPM.RISK_PARITY)
        assert result.allocation_method == AllocationMethodAPM.RISK_PARITY
        # JNJ (lowest vol) should have highest weight in risk parity
        jnj_w = next(p.weight for p in result.positions if p.ticker == "JNJ")
        nvda_w = next(p.weight for p in result.positions if p.ticker == "NVDA")
        assert jnj_w > nvda_w

    def test_volatility_targeting(self):
        result = self.engine.optimise(self.portfolio, self.vols, method=AllocationMethodAPM.VOLATILITY_TARGETING)
        assert result.allocation_method == AllocationMethodAPM.VOLATILITY_TARGETING

    def test_max_sharpe(self):
        result = self.engine.optimise(self.portfolio, self.vols, method=AllocationMethodAPM.MAX_SHARPE)
        total = sum(p.weight for p in result.positions)
        assert abs(total - 1.0) < 0.02

    def test_min_variance(self):
        result = self.engine.optimise(self.portfolio, self.vols, method=AllocationMethodAPM.MIN_VARIANCE)
        assert result.allocation_method == AllocationMethodAPM.MIN_VARIANCE

    def test_defensive_tilt_in_recession(self):
        result = self.engine.optimise(self.portfolio, self.vols, regime="recession")
        jnj_w = next(p.weight for p in result.positions if p.ticker == "JNJ")
        assert jnj_w > 0.15  # Healthcare should get defensive tilt

    def test_empty_portfolio_returns_unchanged(self):
        empty = APMPortfolio(objective=PortfolioObjective.GROWTH)
        result = self.engine.optimise(empty, {})
        assert len(result.positions) == 0

    def test_portfolio_vol_estimated(self):
        result = self.engine.optimise(self.portfolio, self.vols)
        assert result.expected_volatility > 0


# ── Rebalancing Engine ───────────────────────────────────────────────────────

from src.engines.autonomous_pm.rebalancing_engine import RebalancingEngine


class TestRebalancingEngine:
    def setup_method(self):
        self.engine = RebalancingEngine()
        self.portfolio = APMPortfolio(
            objective=PortfolioObjective.GROWTH,
            positions=[
                APMPosition(ticker="NVDA", weight=0.30, alpha_score=75),
                APMPosition(ticker="AAPL", weight=0.25, alpha_score=80),
                APMPosition(ticker="JPM", weight=0.25, alpha_score=70),
                APMPosition(ticker="JNJ", weight=0.20, alpha_score=65),
            ],
        )

    def test_regime_change_triggers(self):
        rec = self.engine.evaluate(current_regime="recession", previous_regime="expansion")
        assert RebalanceTrigger.REGIME_CHANGE in rec.triggers_fired
        assert rec.should_rebalance

    def test_alpha_shift_triggers(self):
        new_profiles = [{"ticker": "NVDA", "composite_alpha_score": 95}]
        rec = self.engine.evaluate(
            current_portfolio=self.portfolio,
            new_alpha_profiles=new_profiles,
        )
        assert RebalanceTrigger.ALPHA_SHIFT in rec.triggers_fired

    def test_risk_escalation_triggers(self):
        risk_report = PortfolioRiskReport(risk_score=85, violations=[
            RiskViolation(violation_type=RiskViolationType.VOLATILITY_EXCESS, title="High Vol", description="test", affected_tickers=["NVDA"]),
        ])
        rec = self.engine.evaluate(risk_report=risk_report)
        assert RebalanceTrigger.RISK_ESCALATION in rec.triggers_fired
        assert rec.urgency in (RebalanceUrgency.HIGH, RebalanceUrgency.IMMEDIATE)

    def test_no_triggers_when_stable(self):
        rec = self.engine.evaluate(current_regime="expansion", previous_regime="expansion")
        assert rec.should_rebalance is False
        assert len(rec.triggers_fired) == 0

    def test_market_event_triggers(self):
        events = [{"ticker": "AAPL", "impact": "bearish", "headline": "Earnings miss"}]
        rec = self.engine.evaluate(market_events=events)
        assert RebalanceTrigger.MARKET_EVENT in rec.triggers_fired

    def test_new_candidate_detection(self):
        profiles = [{"ticker": "TSLA", "composite_alpha_score": 75}]
        rec = self.engine.evaluate(current_portfolio=self.portfolio, new_alpha_profiles=profiles)
        new_tickers = [a.ticker for a in rec.actions if a.ticker == "TSLA"]
        assert len(new_tickers) > 0


# ── Risk Management Engine ──────────────────────────────────────────────────

from src.engines.autonomous_pm.risk_management_engine import RiskManagementEngine


class TestRiskManagementEngine:
    def setup_method(self):
        self.engine = RiskManagementEngine()

    def test_concentrated_portfolio(self):
        p = APMPortfolio(objective=PortfolioObjective.GROWTH, positions=[
            APMPosition(ticker="NVDA", weight=0.60, sector="Technology"),
            APMPosition(ticker="AAPL", weight=0.40, sector="Technology"),
        ])
        report = self.engine.assess(p)
        types = [v.violation_type for v in report.violations]
        assert RiskViolationType.CONCENTRATION_BREACH in types
        assert RiskViolationType.SECTOR_OVERWEIGHT in types

    def test_within_limits(self):
        p = APMPortfolio(objective=PortfolioObjective.BALANCED, positions=[
            APMPosition(ticker="AAPL", weight=0.15, sector="Technology"),
            APMPosition(ticker="JPM", weight=0.15, sector="Financials"),
            APMPosition(ticker="JNJ", weight=0.15, sector="Healthcare"),
            APMPosition(ticker="XOM", weight=0.15, sector="Energy"),
            APMPosition(ticker="KO", weight=0.15, sector="Consumer Staples"),
            APMPosition(ticker="WMT", weight=0.13, sector="Retail"),
            APMPosition(ticker="PG", weight=0.12, sector="Consumer Goods"),
        ])
        report = self.engine.assess(p)
        assert report.within_limits

    def test_risk_score_computed(self):
        p = APMPortfolio(objective=PortfolioObjective.GROWTH, positions=[
            APMPosition(ticker="NVDA", weight=0.5, sector="Technology"),
            APMPosition(ticker="AAPL", weight=0.5, sector="Technology"),
        ])
        report = self.engine.assess(p, asset_volatilities={"NVDA": 0.35, "AAPL": 0.22})
        assert 0 <= report.risk_score <= 100

    def test_max_drawdown_detection(self):
        p = APMPortfolio(objective=PortfolioObjective.GROWTH, positions=[
            APMPosition(ticker="X", weight=1.0, sector="Materials"),
        ])
        # Simulate returns with a drawdown
        returns = [0.01] * 10 + [-0.05] * 5 + [0.01] * 5
        report = self.engine.assess(p, returns_history=returns)
        assert report.max_drawdown < 0

    def test_var_computed(self):
        p = APMPortfolio(objective=PortfolioObjective.GROWTH, positions=[
            APMPosition(ticker="X", weight=1.0, sector="Technology"),
        ])
        returns = [0.01, -0.02, 0.005, -0.01, 0.008] * 10
        report = self.engine.assess(p, returns_history=returns)
        assert report.var_95 != 0

    def test_empty_portfolio(self):
        report = self.engine.assess()
        assert report.risk_score == 0


# ── Performance Engine ───────────────────────────────────────────────────────

from src.engines.autonomous_pm.performance_engine import PerformanceEngine


class TestPerformanceEngine:
    def setup_method(self):
        self.engine = PerformanceEngine()

    def test_basic_performance(self):
        returns = [0.01, -0.005, 0.008, 0.012, -0.003]
        snap = self.engine.evaluate(portfolio_returns=returns)
        assert snap.total_return != 0
        assert snap.period_days == 5

    def test_sharpe_ratio(self):
        # Varied positive returns so variance > 0
        returns = [0.01, 0.012, 0.008, 0.011, 0.009] * 10
        snap = self.engine.evaluate(portfolio_returns=returns)
        assert snap.sharpe_ratio > 0

    def test_benchmark_comparison(self):
        p_returns = [0.01, 0.02, 0.015, -0.005, 0.008]
        b_returns = [0.005, 0.01, 0.008, -0.003, 0.005]
        snap = self.engine.evaluate(p_returns, b_returns)
        assert snap.alpha_vs_benchmark > 0
        assert snap.beta != 0
        assert snap.tracking_error > 0

    def test_max_drawdown(self):
        returns = [0.05, 0.03, -0.10, -0.08, 0.02]
        snap = self.engine.evaluate(portfolio_returns=returns)
        assert snap.max_drawdown < 0

    def test_empty_returns(self):
        snap = self.engine.evaluate()
        assert snap.period_days == 0
        assert snap.total_return == 0


# ── APM Facade ───────────────────────────────────────────────────────────────

from src.engines.autonomous_pm.engine import AutonomousPortfolioManager


class TestAPMFacade:
    def test_full_pipeline(self):
        apm = AutonomousPortfolioManager()
        profiles = [
            {"ticker": "NVDA", "composite_alpha_score": 88, "sector": "Technology", "factor_scores": {"momentum": 91}, "tier": "elite"},
            {"ticker": "JPM", "composite_alpha_score": 76, "sector": "Financials", "factor_scores": {"value": 82}, "tier": "alpha"},
        ]
        dashboard = apm.manage(alpha_profiles=profiles, regime="expansion")
        assert isinstance(dashboard, APMDashboard)
        assert len(dashboard.portfolios) == 6
        assert dashboard.active_regime == "expansion"
        assert len(dashboard.explanations) > 0

    def test_with_performance_data(self):
        apm = AutonomousPortfolioManager()
        dashboard = apm.manage(
            alpha_profiles=[{"ticker": "AAPL", "composite_alpha_score": 80, "sector": "Technology", "factor_scores": {}, "tier": "alpha"}],
            portfolio_returns=[0.01, -0.005, 0.008, 0.012, -0.003] * 20,
            benchmark_returns=[0.005, -0.003, 0.006, 0.008, -0.002] * 20,
        )
        assert dashboard.performance is not None
        assert dashboard.performance.sharpe_ratio != 0

    def test_with_rebalance_triggers(self):
        apm = AutonomousPortfolioManager()
        dashboard = apm.manage(
            alpha_profiles=[{"ticker": "NVDA", "composite_alpha_score": 90, "sector": "Technology", "factor_scores": {}, "tier": "elite"}],
            regime="recession",
            previous_regime="expansion",
        )
        assert dashboard.rebalance is not None
        assert dashboard.rebalance.should_rebalance

    def test_empty_input(self):
        apm = AutonomousPortfolioManager()
        dashboard = apm.manage()
        assert isinstance(dashboard, APMDashboard)
        assert len(dashboard.portfolios) == 6
