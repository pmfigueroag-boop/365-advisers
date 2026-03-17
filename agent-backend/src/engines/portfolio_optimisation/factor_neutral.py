"""
src/engines/portfolio_optimisation/factor_neutral.py
--------------------------------------------------------------------------
Factor-Neutral Portfolio Construction — constrains the optimizer to
produce portfolios with zero (or controlled) factor exposures.

Key capabilities:
  - Beta-neutral: portfolio beta ≈ 0 (market-neutral)
  - Factor exposure limits: cap exposure to value, momentum, size, etc.
  - Dynamic beta estimation from historical returns
  - Integration with PortfolioOptimisationEngine via constraint injection

Usage::

    fn = FactorNeutralConstraints(target_beta=0.0, tolerance=0.05)
    adjusted_weights = fn.neutralize(
        weights={"AAPL": 0.3, "MSFT": 0.3, "GOOGL": 0.4},
        betas={"AAPL": 1.2, "MSFT": 1.1, "GOOGL": 0.9},
    )
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.portfolio.factor_neutral")


# ── Contracts ────────────────────────────────────────────────────────────────

class FactorExposure(BaseModel):
    """Factor exposure for a single ticker."""
    ticker: str
    beta: float = 1.0
    size: float = 0.0        # SMB exposure (-1 = large, +1 = small)
    value: float = 0.0       # HML exposure (-1 = growth, +1 = value)
    momentum: float = 0.0    # WML exposure
    quality: float = 0.0     # QMJ exposure


class PortfolioExposure(BaseModel):
    """Aggregate factor exposures for the portfolio."""
    portfolio_beta: float = 0.0
    size_exposure: float = 0.0
    value_exposure: float = 0.0
    momentum_exposure: float = 0.0
    quality_exposure: float = 0.0
    is_neutral: bool = False
    violations: list[str] = Field(default_factory=list)


class NeutralizationResult(BaseModel):
    """Result of neutralization."""
    original_weights: dict[str, float] = Field(default_factory=dict)
    adjusted_weights: dict[str, float] = Field(default_factory=dict)
    exposure_before: PortfolioExposure = Field(
        default_factory=PortfolioExposure,
    )
    exposure_after: PortfolioExposure = Field(
        default_factory=PortfolioExposure,
    )
    adjustment_magnitude: float = 0.0
    iterations: int = 0


# ── Engine ───────────────────────────────────────────────────────────────────

class FactorNeutralConstraints:
    """
    Constrains portfolio to achieve factor neutrality.

    Method: iterative weight adjustment that tilts the portfolio toward
    target factor exposures while minimizing tracking error vs original
    weights.

    Parameters
    ----------
    target_beta : float
        Target portfolio beta (0.0 = market-neutral, 1.0 = benchmark).
    beta_tolerance : float
        Acceptable deviation from target beta.
    factor_limits : dict[str, tuple[float, float]] | None
        {factor_name: (min_exposure, max_exposure)}.
    max_iterations : int
        Maximum iterations for convergence.
    """

    def __init__(
        self,
        target_beta: float = 0.0,
        beta_tolerance: float = 0.05,
        factor_limits: dict[str, tuple[float, float]] | None = None,
        max_iterations: int = 50,
    ) -> None:
        self.target_beta = target_beta
        self.beta_tolerance = beta_tolerance
        self.factor_limits = factor_limits or {}
        self.max_iterations = max_iterations

    def compute_exposure(
        self,
        weights: dict[str, float],
        factor_exposures: dict[str, FactorExposure],
    ) -> PortfolioExposure:
        """Compute portfolio-level factor exposures."""
        beta = 0.0
        size = 0.0
        value = 0.0
        momentum = 0.0
        quality = 0.0

        for ticker, w in weights.items():
            if w < 0.001:
                continue
            fe = factor_exposures.get(ticker, FactorExposure(ticker=ticker))
            beta += w * fe.beta
            size += w * fe.size
            value += w * fe.value
            momentum += w * fe.momentum
            quality += w * fe.quality

        violations = []
        if abs(beta - self.target_beta) > self.beta_tolerance:
            violations.append(
                f"Beta={beta:.3f}, target={self.target_beta:.3f} "
                f"(tolerance={self.beta_tolerance})"
            )

        for factor_name, (lo, hi) in self.factor_limits.items():
            exp = {"size": size, "value": value, "momentum": momentum,
                   "quality": quality}.get(factor_name, 0.0)
            if exp < lo or exp > hi:
                violations.append(
                    f"{factor_name}={exp:.3f}, limits=[{lo:.2f}, {hi:.2f}]"
                )

        return PortfolioExposure(
            portfolio_beta=round(beta, 4),
            size_exposure=round(size, 4),
            value_exposure=round(value, 4),
            momentum_exposure=round(momentum, 4),
            quality_exposure=round(quality, 4),
            is_neutral=len(violations) == 0,
            violations=violations,
        )

    def neutralize(
        self,
        weights: dict[str, float],
        betas: dict[str, float] | None = None,
        factor_exposures: dict[str, FactorExposure] | None = None,
    ) -> NeutralizationResult:
        """
        Adjust weights to achieve target beta / factor neutrality.

        Uses iterative proportional adjustment:
        1. Compute current portfolio beta
        2. If beta > target: reduce high-beta, increase low-beta
        3. Repeat until convergence or max iterations

        Parameters
        ----------
        weights : dict[str, float]
            Original portfolio weights.
        betas : dict[str, float] | None
            Per-ticker betas. If None, uses factor_exposures.
        factor_exposures : dict[str, FactorExposure] | None
            Full factor exposure data. If None, uses just betas.
        """
        # Build factor exposure map
        if factor_exposures is None:
            factor_exposures = {}
            for t in weights:
                b = (betas or {}).get(t, 1.0)
                factor_exposures[t] = FactorExposure(ticker=t, beta=b)

        # Before
        exp_before = self.compute_exposure(weights, factor_exposures)

        if exp_before.is_neutral:
            return NeutralizationResult(
                original_weights=weights,
                adjusted_weights=dict(weights),
                exposure_before=exp_before,
                exposure_after=exp_before,
                iterations=0,
            )

        # Iterative adjustment
        adj = dict(weights)
        iterations = 0

        for iteration in range(self.max_iterations):
            iterations = iteration + 1
            exp = self.compute_exposure(adj, factor_exposures)

            if exp.is_neutral:
                break

            # Beta adjustment: tilt weights away from beta direction
            beta_err = exp.portfolio_beta - self.target_beta
            if abs(beta_err) <= self.beta_tolerance:
                break

            # Compute adjustment per ticker
            tickers = [t for t in adj if adj[t] > 0.001]
            if not tickers:
                break

            # Adjustment proportional to (beta_i - target_beta) * error_sign
            adjustments: dict[str, float] = {}
            for t in tickers:
                fe = factor_exposures.get(t, FactorExposure(ticker=t))
                # Reduce weight on high-beta stocks when beta too high
                adj_factor = -(fe.beta - self.target_beta) * beta_err * 0.5
                adjustments[t] = adj_factor

            # Normalize adjustments to be weight-neutral
            total_adj = sum(adjustments.values())
            if abs(total_adj) > 1e-9:
                avg_adj = total_adj / len(tickers)
                for t in tickers:
                    adjustments[t] -= avg_adj

            # Apply
            for t in tickers:
                adj[t] = max(adj[t] + adj[t] * adjustments[t], 0.0)

            # Re-normalize to sum=1
            total = sum(adj.values())
            if total > 0:
                adj = {t: w / total for t, w in adj.items()}

        # Round
        adj = {t: round(w, 6) for t, w in adj.items() if w > 0.001}

        exp_after = self.compute_exposure(adj, factor_exposures)

        mag = sum(abs(adj.get(t, 0) - weights.get(t, 0)) for t in set(adj) | set(weights))

        logger.info(
            "FACTOR-NEUTRAL: beta %.3f → %.3f (target=%.2f), "
            "%d iterations, adjustment=%.4f",
            exp_before.portfolio_beta, exp_after.portfolio_beta,
            self.target_beta, iterations, mag,
        )

        return NeutralizationResult(
            original_weights=weights,
            adjusted_weights=adj,
            exposure_before=exp_before,
            exposure_after=exp_after,
            adjustment_magnitude=round(mag, 4),
            iterations=iterations,
        )

    @staticmethod
    def estimate_betas(
        asset_returns: dict[str, list[float]],
        market_returns: list[float],
    ) -> dict[str, float]:
        """
        Estimate betas from historical return series.

        β_i = Cov(r_i, r_m) / Var(r_m)
        """
        if not market_returns or len(market_returns) < 10:
            return {t: 1.0 for t in asset_returns}

        n = len(market_returns)
        mean_m = sum(market_returns) / n
        var_m = sum((r - mean_m) ** 2 for r in market_returns) / max(n - 1, 1)

        if var_m < 1e-12:
            return {t: 1.0 for t in asset_returns}

        betas = {}
        for ticker, returns in asset_returns.items():
            min_len = min(len(returns), n)
            if min_len < 10:
                betas[ticker] = 1.0
                continue

            mean_i = sum(returns[:min_len]) / min_len
            mean_m_adj = sum(market_returns[:min_len]) / min_len
            cov = sum(
                (returns[k] - mean_i) * (market_returns[k] - mean_m_adj)
                for k in range(min_len)
            ) / max(min_len - 1, 1)

            betas[ticker] = round(cov / var_m, 4)

        return betas
