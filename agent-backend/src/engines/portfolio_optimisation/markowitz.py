"""
src/engines/portfolio_optimisation/markowitz.py — Markowitz Mean-Variance Solver.

Uses scipy.optimize for constrained quadratic optimisation.
"""
from __future__ import annotations
import numpy as np
import logging
from scipy.optimize import minimize
from src.engines.portfolio_optimisation.models import (
    OptimisationObjective, PortfolioConstraints, OptimisationResult,
)

logger = logging.getLogger("365advisers.optimisation.markowitz")


class MarkowitzSolver:
    """
    Classic Markowitz mean-variance optimisation.

    Solves:
        min  w'Σw           (min variance)
        max  (w'μ - rf) / √(w'Σw)  (max Sharpe)
        s.t. Σwᵢ = 1, bounds
    """

    @classmethod
    def optimise(
        cls,
        expected_returns: dict[str, float],
        cov_matrix: np.ndarray,
        tickers: list[str],
        objective: OptimisationObjective = OptimisationObjective.MAX_SHARPE,
        constraints: PortfolioConstraints | None = None,
        risk_free_rate: float = 0.0,
        target_return: float | None = None,
        target_risk: float | None = None,
    ) -> OptimisationResult:
        cons = constraints or PortfolioConstraints()
        n = len(tickers)
        mu = np.array([expected_returns.get(t, 0) for t in tickers])
        sigma = np.array(cov_matrix, dtype=np.float64)

        # Bounds
        if cons.long_only:
            bounds = [(max(cons.min_weight, 0), cons.max_weight)] * n
        else:
            bounds = [(cons.min_weight, cons.max_weight)] * n

        # Constraints: weights sum to 1
        eq_constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        # Target return constraint
        if objective == OptimisationObjective.TARGET_RETURN and target_return is not None:
            eq_constraints.append({
                "type": "eq",
                "fun": lambda w, tr=target_return: w @ mu - tr,
            })

        # Target risk constraint
        if objective == OptimisationObjective.TARGET_RISK and target_risk is not None:
            eq_constraints.append({
                "type": "eq",
                "fun": lambda w, tr=target_risk: np.sqrt(w @ sigma @ w) - tr,
            })

        # Turnover constraint
        ineq_constraints = []
        if cons.turnover_limit and cons.current_weights:
            w0 = np.array([cons.current_weights.get(t, 0) for t in tickers])
            ineq_constraints.append({
                "type": "ineq",
                "fun": lambda w, w0=w0, lim=cons.turnover_limit: lim - np.sum(np.abs(w - w0)),
            })

        all_constraints = eq_constraints + ineq_constraints

        # Objective function
        x0 = np.ones(n) / n

        if objective == OptimisationObjective.MIN_VARIANCE:
            def obj(w):
                return w @ sigma @ w
        elif objective == OptimisationObjective.MAX_SHARPE:
            def obj(w):
                ret = w @ mu - risk_free_rate
                vol = np.sqrt(w @ sigma @ w)
                return -(ret / vol) if vol > 1e-10 else 1e10
        elif objective in (OptimisationObjective.TARGET_RETURN, OptimisationObjective.TARGET_RISK):
            def obj(w):
                return w @ sigma @ w
        elif objective == OptimisationObjective.RISK_PARITY:
            def obj(w):
                port_var = w @ sigma @ w
                marginal = sigma @ w
                risk_contrib = w * marginal
                target_rc = port_var / n
                return np.sum((risk_contrib - target_rc) ** 2)
        else:
            def obj(w):
                return w @ sigma @ w

        result = minimize(
            obj, x0, method="SLSQP",
            bounds=bounds, constraints=all_constraints,
            options={"maxiter": 1000, "ftol": 1e-12},
        )

        if not result.success:
            logger.warning("Optimisation did not converge: %s", result.message)

        weights = result.x
        # Clean tiny weights
        weights = np.where(np.abs(weights) < 1e-6, 0, weights)
        weights = weights / np.sum(weights)  # renormalise

        port_return = float(weights @ mu)
        port_vol = float(np.sqrt(weights @ sigma @ weights))
        sharpe = (port_return - risk_free_rate) / port_vol if port_vol > 0 else 0

        constraints_applied = []
        if cons.long_only:
            constraints_applied.append("long_only")
        if cons.turnover_limit:
            constraints_applied.append(f"turnover≤{cons.turnover_limit}")
        if cons.max_weight < 1.0:
            constraints_applied.append(f"max_weight={cons.max_weight}")

        return OptimisationResult(
            objective=objective,
            optimal_weights={t: round(float(w), 6) for t, w in zip(tickers, weights)},
            expected_return=round(port_return, 6),
            volatility=round(port_vol, 6),
            sharpe_ratio=round(sharpe, 4),
            risk_free_rate=risk_free_rate,
            constraints_applied=constraints_applied,
        )
