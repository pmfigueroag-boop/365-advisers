"""
tests/test_monte_carlo_risk.py
--------------------------------------------------------------------------
Tests for MonteCarloRisk engine — parametric, historical, correlated.
"""

from __future__ import annotations

import math
import pytest

from src.engines.portfolio.monte_carlo_risk import (
    MonteCarloRisk,
    VaRResult,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

SEED = 42
N_SIMS = 5_000
HORIZON = 21


def _engine(**kw) -> MonteCarloRisk:
    return MonteCarloRisk(
        n_simulations=kw.get("n", N_SIMS),
        horizon_days=kw.get("horizon", HORIZON),
        seed=kw.get("seed", SEED),
    )


# ─── Parametric Tests ────────────────────────────────────────────────────────

class TestParametric:

    def test_basic_var_cvar(self):
        """Parametric VaR/CVaR should be positive for a portfolio with vol."""
        mc = _engine()
        result = mc.run_parametric(portfolio_return=0.0005, portfolio_vol=0.015)

        assert isinstance(result, VaRResult)
        assert result.var_95 > 0
        assert result.var_99 > 0
        assert result.method == "parametric"

    def test_cvar_gte_var(self):
        """CVaR (expected shortfall) must always be ≥ VaR."""
        mc = _engine()
        result = mc.run_parametric(portfolio_return=0.0003, portfolio_vol=0.02)

        assert result.cvar_95 >= result.var_95
        assert result.cvar_99 >= result.var_99

    def test_var99_gte_var95(self):
        """99% VaR should be ≥ 95% VaR (more extreme quantile)."""
        mc = _engine()
        result = mc.run_parametric(portfolio_return=0.0, portfolio_vol=0.02)

        assert result.var_99 >= result.var_95

    def test_zero_vol_no_risk(self):
        """Zero volatility → negligible VaR."""
        mc = _engine()
        result = mc.run_parametric(portfolio_return=0.001, portfolio_vol=0.0)

        # With zero vol all returns are identical
        assert result.expected_vol < 0.001

    def test_high_vol_high_var(self):
        """Higher vol → higher VaR."""
        mc = _engine()
        lo = mc.run_parametric(portfolio_return=0.0, portfolio_vol=0.01)
        hi = mc.run_parametric(portfolio_return=0.0, portfolio_vol=0.04)

        assert hi.var_95 > lo.var_95

    def test_seed_reproducibility(self):
        """Same seed → identical results."""
        a = _engine(seed=99).run_parametric(0.0005, 0.015)
        b = _engine(seed=99).run_parametric(0.0005, 0.015)

        assert a.var_95 == b.var_95
        assert a.cvar_99 == b.cvar_99

    def test_probability_of_loss(self):
        """With zero expected return and vol, ~50% chance of loss."""
        mc = _engine(n=10_000)
        result = mc.run_parametric(portfolio_return=0.0, portfolio_vol=0.02)

        # Should be roughly 50% ± 5%
        assert 0.35 < result.probability_of_loss < 0.65


# ─── Historical Bootstrap Tests ─────────────────────────────────────────────

class TestHistorical:

    def test_basic_historical(self):
        """Historical bootstrap with real-ish returns."""
        import random
        rng = random.Random(42)
        returns = [rng.gauss(0.0005, 0.015) for _ in range(252)]

        mc = _engine()
        result = mc.run_historical(returns)

        assert result.method == "historical"
        assert result.var_95 > 0
        assert result.n_simulations == N_SIMS

    def test_insufficient_data(self):
        """< 10 historical returns → empty result."""
        mc = _engine()
        result = mc.run_historical([0.01, 0.02, -0.01])

        assert result.method == "historical"
        assert result.n_simulations == 0


# ─── Correlated Simulation Tests ────────────────────────────────────────────

class TestCorrelated:

    def test_single_asset(self):
        """Correlated sim with 1 asset → matches parametric roughly."""
        mc = _engine()
        result = mc.run_correlated(
            weights={"AAPL": 1.0},
            expected_returns={"AAPL": 0.0005},
            covariance=[[0.0002]],
            tickers=["AAPL"],
        )

        assert result.method == "correlated"
        assert result.var_95 > 0

    def test_two_correlated_assets(self):
        """2 assets with positive correlation."""
        mc = _engine()
        # Positive correlation → higher portfolio vol
        cov = [
            [0.0004, 0.0003],
            [0.0003, 0.0004],
        ]
        result = mc.run_correlated(
            weights={"AAPL": 0.5, "MSFT": 0.5},
            expected_returns={"AAPL": 0.0005, "MSFT": 0.0003},
            covariance=cov,
            tickers=["AAPL", "MSFT"],
        )

        assert result.var_95 > 0
        assert result.cvar_95 >= result.var_95

    def test_empty_tickers(self):
        """Empty tickers → empty result."""
        mc = _engine()
        result = mc.run_correlated(
            weights={}, expected_returns={},
            covariance=[], tickers=[],
        )
        assert result.n_simulations == 0


# ─── Cholesky Tests ─────────────────────────────────────────────────────────

class TestCholesky:

    def test_identity_cholesky(self):
        """Cholesky of identity matrix → identity."""
        L = MonteCarloRisk._cholesky([[1, 0], [0, 1]], 2)
        assert abs(L[0][0] - 1.0) < 1e-6
        assert abs(L[1][1] - 1.0) < 1e-6
        assert abs(L[0][1]) < 1e-6
        assert abs(L[1][0]) < 1e-6

    def test_cholesky_reconstruction(self):
        """L × L^T should reconstruct the original matrix."""
        cov = [[0.04, 0.01], [0.01, 0.03]]
        L = MonteCarloRisk._cholesky(cov, 2)

        # Reconstruct
        for i in range(2):
            for j in range(2):
                val = sum(L[i][k] * L[j][k] for k in range(2))
                assert abs(val - cov[i][j]) < 1e-6
