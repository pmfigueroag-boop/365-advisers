"""
tests/test_portfolio_optimisation.py — MVO + Efficient Frontier + Black-Litterman tests.
"""
import numpy as np
import pytest
from src.engines.portfolio_optimisation.models import (
    OptimisationObjective, PortfolioConstraints, PortfolioPoint,
)
from src.engines.portfolio_optimisation.markowitz import MarkowitzSolver
from src.engines.portfolio_optimisation.efficient_frontier import EfficientFrontierGenerator
from src.engines.portfolio_optimisation.black_litterman import BlackLittermanModel
from src.engines.portfolio_optimisation.engine import PortfolioOptimisationEngine


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _three_asset():
    """3-asset universe with known returns and covariance."""
    tickers = ["A", "B", "C"]
    mu = {"A": 0.10, "B": 0.06, "C": 0.14}
    # Covariance matrix (annualised)
    cov = np.array([
        [0.04, 0.006, 0.010],
        [0.006, 0.01, 0.004],
        [0.010, 0.004, 0.09],
    ])
    return tickers, mu, cov


# ── Markowitz Tests ──────────────────────────────────────────────────────────

class TestMarkowitz:
    def test_min_variance(self):
        tickers, mu, cov = _three_asset()
        r = MarkowitzSolver.optimise(mu, cov, tickers, OptimisationObjective.MIN_VARIANCE)
        assert sum(r.optimal_weights.values()) == pytest.approx(1.0, abs=0.01)
        assert r.volatility > 0

    def test_max_sharpe(self):
        tickers, mu, cov = _three_asset()
        r = MarkowitzSolver.optimise(mu, cov, tickers, OptimisationObjective.MAX_SHARPE)
        assert sum(r.optimal_weights.values()) == pytest.approx(1.0, abs=0.01)
        assert r.sharpe_ratio > 0

    def test_min_var_lower_vol_than_sharpe(self):
        tickers, mu, cov = _three_asset()
        mv = MarkowitzSolver.optimise(mu, cov, tickers, OptimisationObjective.MIN_VARIANCE)
        ms = MarkowitzSolver.optimise(mu, cov, tickers, OptimisationObjective.MAX_SHARPE)
        assert mv.volatility <= ms.volatility + 0.01

    def test_target_return(self):
        tickers, mu, cov = _three_asset()
        r = MarkowitzSolver.optimise(mu, cov, tickers, OptimisationObjective.TARGET_RETURN, target_return=0.08)
        assert r.expected_return == pytest.approx(0.08, abs=0.02)

    def test_risk_parity(self):
        tickers, mu, cov = _three_asset()
        r = MarkowitzSolver.optimise(mu, cov, tickers, OptimisationObjective.RISK_PARITY)
        assert sum(r.optimal_weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_long_only(self):
        tickers, mu, cov = _three_asset()
        cons = PortfolioConstraints(long_only=True)
        r = MarkowitzSolver.optimise(mu, cov, tickers, OptimisationObjective.MAX_SHARPE, cons)
        for w in r.optimal_weights.values():
            assert w >= -0.001

    def test_max_weight_constraint(self):
        tickers, mu, cov = _three_asset()
        cons = PortfolioConstraints(max_weight=0.5)
        r = MarkowitzSolver.optimise(mu, cov, tickers, OptimisationObjective.MAX_SHARPE, cons)
        for w in r.optimal_weights.values():
            assert w <= 0.51  # Allow small tolerance

    def test_constraints_logged(self):
        tickers, mu, cov = _three_asset()
        cons = PortfolioConstraints(max_weight=0.4, long_only=True)
        r = MarkowitzSolver.optimise(mu, cov, tickers, OptimisationObjective.MAX_SHARPE, cons)
        assert "long_only" in r.constraints_applied
        assert "max_weight=0.4" in r.constraints_applied

    def test_two_asset(self):
        tickers = ["X", "Y"]
        mu = {"X": 0.08, "Y": 0.12}
        cov = np.array([[0.04, 0.01], [0.01, 0.09]])
        r = MarkowitzSolver.optimise(mu, cov, tickers, OptimisationObjective.MAX_SHARPE)
        assert sum(r.optimal_weights.values()) == pytest.approx(1.0, abs=0.01)


# ── Efficient Frontier Tests ────────────────────────────────────────────────

class TestEfficientFrontier:
    def test_frontier_has_points(self):
        tickers, mu, cov = _three_asset()
        ef = EfficientFrontierGenerator.generate(mu, cov, tickers, num_points=20)
        assert ef.num_points >= 10
        assert ef.min_variance_portfolio is not None
        assert ef.max_sharpe_portfolio is not None

    def test_frontier_monotonic_return(self):
        tickers, mu, cov = _three_asset()
        ef = EfficientFrontierGenerator.generate(mu, cov, tickers, num_points=20)
        returns = [p.expected_return for p in ef.points]
        # Returns should be roughly non-decreasing
        for i in range(1, len(returns)):
            assert returns[i] >= returns[i - 1] - 0.01

    def test_min_var_lowest_vol(self):
        tickers, mu, cov = _three_asset()
        ef = EfficientFrontierGenerator.generate(mu, cov, tickers, num_points=20)
        min_vol = min(p.volatility for p in ef.points)
        assert ef.min_variance_portfolio.volatility <= min_vol + 0.01

    def test_max_sharpe_highest_sharpe(self):
        tickers, mu, cov = _three_asset()
        ef = EfficientFrontierGenerator.generate(mu, cov, tickers, num_points=20)
        max_sr = max(p.sharpe_ratio for p in ef.points)
        assert ef.max_sharpe_portfolio.sharpe_ratio >= max_sr - 0.2

    def test_constrained_frontier(self):
        tickers, mu, cov = _three_asset()
        cons = PortfolioConstraints(max_weight=0.5)
        ef = EfficientFrontierGenerator.generate(mu, cov, tickers, cons, num_points=15)
        assert ef.num_points >= 5


# ── Black-Litterman Tests ───────────────────────────────────────────────────

class TestBlackLitterman:
    def test_implied_returns(self):
        _, _, cov = _three_asset()
        w = np.array([0.5, 0.3, 0.2])
        pi = BlackLittermanModel.implied_returns(cov, w)
        assert len(pi) == 3
        assert all(not np.isnan(r) for r in pi)

    def test_posterior_with_views(self):
        _, _, cov = _three_asset()
        w = np.array([0.5, 0.3, 0.2])
        P = np.array([[1, 0, 0]])  # view on asset A
        Q = np.array([0.15])
        posterior = BlackLittermanModel.posterior_returns(cov, w, P, Q)
        assert len(posterior) == 3
        # View says A returns 15%, so posterior for A should be tilted up
        pi = BlackLittermanModel.implied_returns(cov, w)
        assert posterior[0] > pi[0]

    def test_full_model(self):
        tickers = ["A", "B", "C"]
        _, _, cov = _three_asset()
        caps = {"A": 1000, "B": 500, "C": 300}
        views = [{"asset": "A", "return": 0.15, "confidence": 0.8}]
        posterior = BlackLittermanModel.full_model(tickers, cov, caps, views)
        assert len(posterior) == 3
        assert all(isinstance(v, float) for v in posterior.values())

    def test_no_views_returns_equilibrium(self):
        tickers = ["A", "B", "C"]
        _, _, cov = _three_asset()
        caps = {"A": 1000, "B": 500, "C": 300}
        posterior = BlackLittermanModel.full_model(tickers, cov, caps, views=[])
        assert len(posterior) == 3


# ── Engine Integration Tests ────────────────────────────────────────────────

class TestEngine:
    def test_optimise(self):
        _, mu, cov = _three_asset()
        r = PortfolioOptimisationEngine.optimise(mu, cov.tolist())
        assert sum(r.optimal_weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_frontier(self):
        _, mu, cov = _three_asset()
        ef = PortfolioOptimisationEngine.efficient_frontier(mu, cov.tolist(), num_points=15)
        assert ef.num_points >= 5

    def test_bl_optimise(self):
        _, _, cov = _three_asset()
        caps = {"A": 1000, "B": 500, "C": 300}
        views = [{"asset": "A", "return": 0.12, "confidence": 0.7}]
        r = PortfolioOptimisationEngine.black_litterman_optimise(cov.tolist(), caps, views)
        assert sum(r.optimal_weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_from_returns_data(self):
        np.random.seed(42)
        returns = {
            "A": (np.random.randn(252) * 0.01 + 0.0004).tolist(),
            "B": (np.random.randn(252) * 0.015 + 0.0003).tolist(),
            "C": (np.random.randn(252) * 0.02 + 0.0005).tolist(),
        }
        r = PortfolioOptimisationEngine.from_returns_data(returns)
        assert sum(r.optimal_weights.values()) == pytest.approx(1.0, abs=0.01)
