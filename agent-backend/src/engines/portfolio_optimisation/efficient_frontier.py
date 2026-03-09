"""
src/engines/portfolio_optimisation/efficient_frontier.py — Efficient Frontier generator.
"""
from __future__ import annotations
import numpy as np
import logging
from src.engines.portfolio_optimisation.models import (
    OptimisationObjective, PortfolioConstraints, PortfolioPoint, EfficientFrontierResult,
)
from src.engines.portfolio_optimisation.markowitz import MarkowitzSolver

logger = logging.getLogger("365advisers.optimisation.frontier")


class EfficientFrontierGenerator:
    """Generate the efficient frontier by sweeping target returns."""

    @classmethod
    def generate(
        cls,
        expected_returns: dict[str, float],
        cov_matrix: np.ndarray,
        tickers: list[str],
        constraints: PortfolioConstraints | None = None,
        risk_free_rate: float = 0.0,
        num_points: int = 50,
    ) -> EfficientFrontierResult:
        # 1. Find min-variance portfolio
        min_var = MarkowitzSolver.optimise(
            expected_returns, cov_matrix, tickers,
            OptimisationObjective.MIN_VARIANCE, constraints, risk_free_rate,
        )
        min_var_point = PortfolioPoint(
            expected_return=min_var.expected_return,
            volatility=min_var.volatility,
            sharpe_ratio=min_var.sharpe_ratio,
            weights=min_var.optimal_weights,
        )

        # 2. Find max-Sharpe portfolio
        max_sharpe = MarkowitzSolver.optimise(
            expected_returns, cov_matrix, tickers,
            OptimisationObjective.MAX_SHARPE, constraints, risk_free_rate,
        )
        max_sharpe_point = PortfolioPoint(
            expected_return=max_sharpe.expected_return,
            volatility=max_sharpe.volatility,
            sharpe_ratio=max_sharpe.sharpe_ratio,
            weights=max_sharpe.optimal_weights,
        )

        # 3. Sweep target returns
        mu_arr = np.array([expected_returns.get(t, 0) for t in tickers])
        min_ret = min_var.expected_return
        max_ret = float(np.max(mu_arr))
        if max_ret <= min_ret:
            max_ret = min_ret + 0.05

        target_returns = np.linspace(min_ret, max_ret, num_points)
        points = []

        for tr in target_returns:
            try:
                result = MarkowitzSolver.optimise(
                    expected_returns, cov_matrix, tickers,
                    OptimisationObjective.TARGET_RETURN, constraints,
                    risk_free_rate, target_return=float(tr),
                )
                points.append(PortfolioPoint(
                    expected_return=result.expected_return,
                    volatility=result.volatility,
                    sharpe_ratio=result.sharpe_ratio,
                    weights=result.optimal_weights,
                ))
            except Exception:
                continue

        return EfficientFrontierResult(
            points=points,
            min_variance_portfolio=min_var_point,
            max_sharpe_portfolio=max_sharpe_point,
            tickers=tickers,
            risk_free_rate=risk_free_rate,
            num_points=len(points),
        )
