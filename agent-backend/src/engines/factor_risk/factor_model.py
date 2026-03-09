"""
src/engines/factor_risk/factor_model.py — Multi-factor regression model.

Estimates factor exposures (betas) via OLS regression of asset returns on factor returns.
Similar to Barra's cross-sectional factor model.
"""
from __future__ import annotations
import numpy as np
import logging
from src.engines.factor_risk.models import RiskFactor, FactorExposure

logger = logging.getLogger("365advisers.factor_risk.model")


class FactorModel:
    """
    Estimate factor exposures via time-series regression.

    For each asset: r_i = α + Σ β_ij * F_j + ε
    """

    @classmethod
    def estimate_exposures(
        cls,
        asset_returns: dict[str, list[float]],
        factor_returns: dict[str, list[float]],
    ) -> list[FactorExposure]:
        """
        Estimate factor loadings for each asset via OLS.

        Args:
            asset_returns: ticker → daily return series
            factor_returns: factor_name → daily return series

        Returns:
            List of FactorExposure (one per asset)
        """
        factors = sorted(factor_returns.keys())
        n_obs = min(len(factor_returns[f]) for f in factors)
        n_obs = min(n_obs, min(len(asset_returns[t]) for t in asset_returns))

        # Build factor matrix [n_obs × k+1] (with intercept)
        X = np.ones((n_obs, len(factors) + 1))
        for j, f in enumerate(factors):
            X[:, j + 1] = np.array(factor_returns[f][:n_obs])

        results = []
        for ticker in sorted(asset_returns.keys()):
            y = np.array(asset_returns[ticker][:n_obs])

            # OLS: β = (X'X)^-1 X'y
            try:
                XtX = X.T @ X
                Xty = X.T @ y
                betas = np.linalg.solve(XtX, Xty)

                # R-squared
                y_hat = X @ betas
                ss_res = np.sum((y - y_hat) ** 2)
                ss_tot = np.sum((y - np.mean(y)) ** 2)
                r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

                exposures = {f: round(float(betas[j + 1]), 6) for j, f in enumerate(factors)}
                results.append(FactorExposure(ticker=ticker, exposures=exposures, r_squared=round(r2, 4)))

            except np.linalg.LinAlgError:
                logger.warning("Singular matrix for %s, using zero exposures", ticker)
                results.append(FactorExposure(ticker=ticker, exposures={f: 0.0 for f in factors}))

        return results

    @classmethod
    def compute_factor_covariance(
        cls,
        factor_returns: dict[str, list[float]],
        annualise: bool = True,
    ) -> tuple[list[str], np.ndarray]:
        """Compute factor-factor covariance matrix."""
        factors = sorted(factor_returns.keys())
        n_obs = min(len(factor_returns[f]) for f in factors)
        data = np.array([factor_returns[f][:n_obs] for f in factors])
        cov = np.cov(data)
        if annualise:
            cov = cov * 252
        return factors, cov

    @classmethod
    def compute_residual_variance(
        cls,
        asset_returns: dict[str, list[float]],
        factor_returns: dict[str, list[float]],
        exposures: list[FactorExposure],
    ) -> dict[str, float]:
        """Compute per-asset idiosyncratic (residual) variance."""
        factors = sorted(factor_returns.keys())
        n_obs = min(len(factor_returns[f]) for f in factors)
        n_obs = min(n_obs, min(len(asset_returns[t]) for t in asset_returns))

        F = np.array([factor_returns[f][:n_obs] for f in factors]).T  # [n_obs × k]

        residual_vars = {}
        exposure_map = {e.ticker: e for e in exposures}

        for ticker in sorted(asset_returns.keys()):
            y = np.array(asset_returns[ticker][:n_obs])
            exp = exposure_map.get(ticker)
            if not exp:
                residual_vars[ticker] = float(np.var(y)) * 252
                continue

            betas = np.array([exp.exposures.get(f, 0) for f in factors])
            y_hat = F @ betas
            residuals = y - y_hat
            residual_vars[ticker] = float(np.var(residuals)) * 252

        return residual_vars
