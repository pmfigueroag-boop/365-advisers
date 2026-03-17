"""
tests/test_score_push.py
--------------------------------------------------------------------------
Tests for MonteCarloRisk, ComplianceRuleEngine, RegimePositionSizer.
"""

from __future__ import annotations

import math
import random
import pytest

from src.engines.portfolio.monte_carlo_risk import MonteCarloRisk, VaRResult
from src.engines.compliance.compliance_rules import (
    ComplianceRuleEngine,
    ComplianceConfig,
    ComplianceReport,
)
from src.engines.portfolio.regime_position_sizing import (
    RegimePositionSizer,
    RegimeSizingConfig,
    RegimeContext,
    SizingResult,
)


# ─── Monte Carlo VaR Tests ──────────────────────────────────────────────────

class TestMonteCarloRisk:

    def test_parametric_var_positive(self):
        """VaR95 should be positive (a loss amount)."""
        mc = MonteCarloRisk(n_simulations=5000, horizon_days=21, seed=42)
        result = mc.run_parametric(
            portfolio_return=0.0003,
            portfolio_vol=0.012,
        )

        assert result.var_95 > 0
        assert result.var_99 > result.var_95  # 99% worse than 95%

    def test_cvar_exceeds_var(self):
        """CVaR >= VaR (tail average >= threshold)."""
        mc = MonteCarloRisk(n_simulations=5000, seed=42)
        result = mc.run_parametric(0.0002, 0.015)

        assert result.cvar_95 >= result.var_95
        assert result.cvar_99 >= result.var_99

    def test_historical_bootstrap(self):
        """Historical VaR from actual returns."""
        rng = random.Random(42)
        returns = [rng.gauss(0.0002, 0.012) for _ in range(500)]

        mc = MonteCarloRisk(n_simulations=5000, seed=42)
        result = mc.run_historical(returns)

        assert result.method == "historical"
        assert result.var_95 > 0

    def test_correlated_simulation(self):
        """Correlated MC with 2 assets."""
        mc = MonteCarloRisk(n_simulations=3000, seed=42)
        cov = [
            [0.0001, 0.00005],
            [0.00005, 0.00015],
        ]
        result = mc.run_correlated(
            weights={"AAPL": 0.6, "MSFT": 0.4},
            expected_returns={"AAPL": 0.0003, "MSFT": 0.0002},
            covariance=cov,
            tickers=["AAPL", "MSFT"],
        )

        assert result.method == "correlated"
        assert result.var_95 > 0
        assert result.n_simulations == 3000

    def test_high_vol_higher_var(self):
        """Higher vol → higher VaR."""
        mc = MonteCarloRisk(n_simulations=5000, seed=42)
        low_vol = mc.run_parametric(0.0003, 0.005)
        high_vol = mc.run_parametric(0.0003, 0.025)

        assert high_vol.var_95 > low_vol.var_95

    def test_probability_of_loss(self):
        """P(loss) is between 0 and 1."""
        mc = MonteCarloRisk(n_simulations=5000, seed=42)
        result = mc.run_parametric(0.0, 0.012)

        assert 0 <= result.probability_of_loss <= 1
        # With zero drift, should be ~50%
        assert 0.4 <= result.probability_of_loss <= 0.6

    def test_max_drawdown_negative(self):
        """Median max drawdown should be negative."""
        mc = MonteCarloRisk(n_simulations=3000, seed=42)
        result = mc.run_parametric(0.0002, 0.015)

        assert result.max_drawdown_median <= 0

    def test_short_history_returns_empty(self):
        """Too short history → empty result."""
        mc = MonteCarloRisk()
        result = mc.run_historical([0.01] * 5)

        assert result.n_simulations == 0


# ─── Compliance Rule Engine Tests ────────────────────────────────────────────

class TestComplianceRuleEngine:

    def test_compliant_portfolio(self):
        """Well-diversified portfolio passes all rules."""
        engine = ComplianceRuleEngine()
        weights = {f"STOCK{i}": 0.10 for i in range(10)}
        report = engine.check_portfolio(weights)

        assert report.is_compliant
        assert report.violations == 0

    def test_concentrated_position_violation(self):
        """15% in one name → violation."""
        engine = ComplianceRuleEngine(ComplianceConfig(max_single_position=0.10))
        weights = {"AAPL": 0.15, "MSFT": 0.10, "GOOGL": 0.10,
                    "AMZN": 0.10, "META": 0.10, "NVDA": 0.45}
        report = engine.check_portfolio(weights)

        assert not report.is_compliant
        assert report.violations > 0

    def test_sector_concentration(self):
        """40% in one sector → violation."""
        engine = ComplianceRuleEngine(ComplianceConfig(max_sector_exposure=0.30))
        weights = {"AAPL": 0.09, "MSFT": 0.09, "GOOGL": 0.09,
                    "AMZN": 0.09, "META": 0.09, "JPM": 0.09,
                    "BAC": 0.09, "GS": 0.09, "XOM": 0.09,
                    "CVX": 0.09, "NVDA": 0.10}
        sector_map = {
            "AAPL": "Tech", "MSFT": "Tech", "GOOGL": "Tech", "NVDA": "Tech",
            "AMZN": "Consumer", "META": "Tech",
            "JPM": "Finance", "BAC": "Finance", "GS": "Finance",
            "XOM": "Energy", "CVX": "Energy",
        }
        report = engine.check_portfolio(weights, sector_map=sector_map)

        # Tech = 0.09*4 + 0.10 = 0.46 > 0.30
        assert not report.is_compliant

    def test_restricted_ticker_critical(self):
        """Restricted ticker → critical violation."""
        config = ComplianceConfig(restricted_tickers=["SANC_CORP"])
        engine = ComplianceRuleEngine(config)
        weights = {"AAPL": 0.20, "MSFT": 0.20, "GOOGL": 0.20,
                    "AMZN": 0.20, "SANC_CORP": 0.20}
        report = engine.check_portfolio(weights)

        assert not report.is_compliant
        assert report.critical > 0

    def test_too_few_positions(self):
        """Only 3 positions → min diversification fail."""
        config = ComplianceConfig(min_positions=5)
        engine = ComplianceRuleEngine(config)
        weights = {"AAPL": 0.40, "MSFT": 0.30, "GOOGL": 0.30}
        report = engine.check_portfolio(weights)

        assert not report.is_compliant

    def test_beta_out_of_range(self):
        """Portfolio beta 2.0 → violation."""
        engine = ComplianceRuleEngine()
        weights = {"AAPL": 0.20, "TSLA": 0.20, "NVDA": 0.20,
                    "AMD": 0.20, "SHOP": 0.20}
        betas = {"AAPL": 1.2, "TSLA": 2.0, "NVDA": 1.8,
                 "AMD": 1.9, "SHOP": 2.1}
        report = engine.check_portfolio(weights, betas=betas)

        assert not report.is_compliant

    def test_turnover_warning(self):
        """60% turnover → warning."""
        engine = ComplianceRuleEngine()
        weights = {f"S{i}": 0.10 for i in range(10)}
        report = engine.check_portfolio(weights, turnover=0.60)

        assert report.warnings > 0

    def test_remedy_provided(self):
        """Violations include a remedy."""
        config = ComplianceConfig(restricted_tickers=["BAD"])
        engine = ComplianceRuleEngine(config)
        weights = {"BAD": 0.20, "A": 0.20, "B": 0.20, "C": 0.20, "D": 0.20}
        report = engine.check_portfolio(weights)

        violations = [r for r in report.results if not r.passed]
        assert any(r.remedy for r in violations)


# ─── Regime Position Sizing Tests ────────────────────────────────────────────

class TestRegimePositionSizer:

    def test_normal_regime_unchanged(self):
        """Normal vol + neutral trend → multiplier is 1.0 with small cash floor."""
        sizer = RegimePositionSizer()
        weights = {"AAPL": 0.30, "MSFT": 0.30, "GOOGL": 0.40}
        result = sizer.adjust(weights, volatility_regime="normal", trend_regime="neutral")

        assert result.vol_multiplier == 1.0
        assert result.trend_adjustment == 0.0
        # Weights slightly reduced by 5% cash floor
        assert result.total_exposure == pytest.approx(0.95, abs=0.01)

    def test_crisis_scales_down(self):
        """Crisis regime → weights ×0.3."""
        sizer = RegimePositionSizer()
        weights = {"AAPL": 0.50, "MSFT": 0.50}
        result = sizer.adjust(weights, volatility_regime="crisis")

        assert result.vol_multiplier == 0.3
        assert result.total_exposure < 0.50

    def test_high_vol_reduces(self):
        """High vol → exposure reduced."""
        sizer = RegimePositionSizer()
        weights = {"AAPL": 0.50, "MSFT": 0.50}
        result = sizer.adjust(weights, volatility_regime="high")

        assert result.total_exposure < 1.0
        assert result.cash_allocation > 0

    def test_low_vol_trending_increases(self):
        """Low vol + trending → slight increase."""
        sizer = RegimePositionSizer()
        weights = {"AAPL": 0.40, "MSFT": 0.40}
        result = sizer.adjust(
            weights, volatility_regime="low", trend_regime="trending",
        )

        # 1.15 + 0.10 = 1.25 but capped
        assert result.vol_multiplier == 1.15
        assert result.trend_adjustment == 0.10

    def test_cash_floor_enforced(self):
        """Even in low vol, cash floor maintained."""
        config = RegimeSizingConfig(cash_floor=0.10)
        sizer = RegimePositionSizer(config)
        weights = {"AAPL": 0.50, "MSFT": 0.50}
        result = sizer.adjust(weights, volatility_regime="low")

        assert result.cash_allocation >= 0.09  # ~10% cash floor

    def test_max_exposure_capped(self):
        """Total exposure never exceeds max."""
        sizer = RegimePositionSizer()
        weights = {"AAPL": 0.50, "MSFT": 0.50}
        result = sizer.adjust(
            weights, volatility_regime="low", trend_regime="trending",
        )

        assert result.total_exposure <= 1.0

    def test_classify_regime(self):
        """Regime classification from metrics."""
        sizer = RegimePositionSizer()

        # Crisis: very high percentile
        regime = sizer.classify_regime(0.40, vol_percentile=97)
        assert regime.volatility_regime == "crisis"

        # Low vol
        regime = sizer.classify_regime(0.08, vol_percentile=15)
        assert regime.volatility_regime == "low"

    def test_regime_context_object(self):
        """Can pass RegimeContext directly."""
        sizer = RegimePositionSizer()
        ctx = RegimeContext(volatility_regime="high", trend_regime="choppy")
        weights = {"A": 0.50, "B": 0.50}
        result = sizer.adjust(weights, regime=ctx)

        assert result.regime.volatility_regime == "high"
        assert result.vol_multiplier == 0.60
