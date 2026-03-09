"""
src/engines/portfolio_optimisation/engine.py — Portfolio Optimisation orchestrator.
"""
from __future__ import annotations
import numpy as np
import logging
from src.engines.portfolio_optimisation.models import (
    OptimisationObjective, PortfolioConstraints, OptimisationResult,
    EfficientFrontierResult, BlackLittermanInputs,
)
from src.engines.portfolio_optimisation.markowitz import MarkowitzSolver
from src.engines.portfolio_optimisation.efficient_frontier import EfficientFrontierGenerator
from src.engines.portfolio_optimisation.black_litterman import BlackLittermanModel

logger = logging.getLogger("365advisers.optimisation.engine")


class PortfolioOptimisationEngine:
    """Unified portfolio optimisation: MVO + Frontier + Black-Litterman."""

    @classmethod
    def optimise(
        cls,
        expected_returns: dict[str, float],
        covariance: list[list[float]],
        objective: OptimisationObjective = OptimisationObjective.MAX_SHARPE,
        constraints: PortfolioConstraints | None = None,
        risk_free_rate: float = 0.0,
        target_return: float | None = None,
        target_risk: float | None = None,
    ) -> OptimisationResult:
        tickers = sorted(expected_returns.keys())
        cov = np.array(covariance, dtype=np.float64)
        return MarkowitzSolver.optimise(
            expected_returns, cov, tickers,
            objective, constraints, risk_free_rate,
            target_return, target_risk,
        )

    @classmethod
    def efficient_frontier(
        cls,
        expected_returns: dict[str, float],
        covariance: list[list[float]],
        constraints: PortfolioConstraints | None = None,
        risk_free_rate: float = 0.0,
        num_points: int = 50,
    ) -> EfficientFrontierResult:
        tickers = sorted(expected_returns.keys())
        cov = np.array(covariance, dtype=np.float64)
        return EfficientFrontierGenerator.generate(
            expected_returns, cov, tickers,
            constraints, risk_free_rate, num_points,
        )

    @classmethod
    def black_litterman_optimise(
        cls,
        covariance: list[list[float]],
        market_caps: dict[str, float],
        views: list[dict],
        objective: OptimisationObjective = OptimisationObjective.MAX_SHARPE,
        constraints: PortfolioConstraints | None = None,
        risk_aversion: float = 2.5,
        tau: float = 0.05,
        risk_free_rate: float = 0.0,
    ) -> OptimisationResult:
        """Black-Litterman → posterior returns → MVO."""
        tickers = sorted(market_caps.keys())
        cov = np.array(covariance, dtype=np.float64)

        posterior = BlackLittermanModel.full_model(
            tickers, cov, market_caps, views, risk_aversion, tau,
        )

        return MarkowitzSolver.optimise(
            posterior, cov, tickers,
            objective, constraints, risk_free_rate,
        )

    @classmethod
    def from_returns_data(
        cls,
        returns_dict: dict[str, list[float]],
        objective: OptimisationObjective = OptimisationObjective.MAX_SHARPE,
        constraints: PortfolioConstraints | None = None,
        risk_free_rate: float = 0.0,
        annualise: bool = True,
    ) -> OptimisationResult:
        """Convenience: compute expected returns & covariance from raw returns."""
        tickers = sorted(returns_dict.keys())
        n = len(tickers)
        min_len = min(len(returns_dict[t]) for t in tickers)
        data = np.array([returns_dict[t][:min_len] for t in tickers])

        if annualise:
            mu = {t: float(np.mean(data[i]) * 252) for i, t in enumerate(tickers)}
            cov = np.cov(data) * 252
        else:
            mu = {t: float(np.mean(data[i])) for i, t in enumerate(tickers)}
            cov = np.cov(data)

        return MarkowitzSolver.optimise(
            mu, cov, tickers,
            objective, constraints, risk_free_rate,
        )
