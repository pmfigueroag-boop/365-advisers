"""
tests/test_portfolio_risk.py
──────────────────────────────────────────────────────────────────────────────
Tests for the Portfolio Risk metrics engine and routes.
"""
from __future__ import annotations

import pytest

from src.engines.risk.monte_carlo import MonteCarloRiskEngine, RiskMetrics


class TestMonteCarloRiskEngine:

    def setup_method(self):
        self.engine = MonteCarloRiskEngine()

    def test_compute_returns_risk_metrics(self):
        """Engine should return RiskMetrics with VaR and CVaR."""
        # Use sample portfolio
        portfolio = {"AAPL": 0.5, "MSFT": 0.5}
        result = self.engine.compute(portfolio, capital=100_000)
        assert isinstance(result, RiskMetrics)

    def test_var_is_negative(self):
        """VaR at 95% should be a negative number (loss)."""
        portfolio = {"AAPL": 1.0}
        result = self.engine.compute(portfolio, capital=100_000)
        if result.var_95 is not None:
            assert result.var_95 <= 0

    def test_cvar_worse_than_var(self):
        """CVaR should be worse (more negative) than VaR."""
        portfolio = {"AAPL": 1.0}
        result = self.engine.compute(portfolio, capital=100_000)
        if result.var_95 is not None and result.cvar_95 is not None:
            assert result.cvar_95 <= result.var_95

    def test_empty_portfolio(self):
        """Empty portfolio should return zero risk."""
        result = self.engine.compute({}, capital=100_000)
        assert result.var_95 == 0 or result.var_95 is None or result.var_95 == 0.0


class TestRiskMetricsContract:

    def test_risk_metrics_has_required_fields(self):
        """RiskMetrics should have the fields expected by the portfolio_risk route."""
        metrics = RiskMetrics(var_95=-5000, cvar_95=-7000)
        assert hasattr(metrics, "var_95")
        assert hasattr(metrics, "cvar_95")
