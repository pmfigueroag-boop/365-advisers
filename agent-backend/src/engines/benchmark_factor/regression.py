"""
src/engines/benchmark_factor/regression.py
──────────────────────────────────────────────────────────────────────────────
OLS factor regression for signal returns.

Implements the 4-factor model:
  R_signal = α + β_MKT × MKT + β_SMB × SMB + β_HML × HML + β_UMD × UMD + ε

Uses numpy normal equations (no statsmodels dependency).
"""

from __future__ import annotations

import logging
import math

import numpy as np

from src.engines.benchmark_factor.models import FactorExposure

logger = logging.getLogger("365advisers.benchmark_factor.regression")


class FactorRegressor:
    """
    OLS regression of signal returns against factor returns.

    Usage::

        regressor = FactorRegressor()
        exposure = regressor.regress(signal_returns, factor_matrix, window=20)
    """

    def regress(
        self,
        signal_returns: np.ndarray,
        factor_matrix: np.ndarray,
        forward_window: int = 20,
    ) -> FactorExposure:
        """
        Run OLS regression: signal_returns ~ α + β × factors.

        Parameters
        ----------
        signal_returns : np.ndarray
            Shape (n,) — signal excess returns.
        factor_matrix : np.ndarray
            Shape (n, 4) — columns [MKT, SMB, HML, UMD].
        forward_window : int
            Which forward window these returns represent.

        Returns
        -------
        FactorExposure
            Alpha, betas, t-stat, R², neutrality.
        """
        n = len(signal_returns)
        if n < 3 or factor_matrix.shape[0] != n:
            return FactorExposure(
                n_observations=n,
                forward_window=forward_window,
            )

        # Ensure correct shapes
        y = signal_returns.astype(float)
        X = factor_matrix.astype(float)

        # Number of factors
        k = X.shape[1] if X.ndim > 1 else 1
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        # Add intercept column
        ones = np.ones((n, 1))
        X_full = np.hstack([ones, X])  # Shape: (n, k+1)

        # Normal equations: β = (X'X)⁻¹ X'y
        try:
            XtX = X_full.T @ X_full
            XtX_inv = np.linalg.pinv(XtX)
            beta = XtX_inv @ (X_full.T @ y)
        except np.linalg.LinAlgError:
            logger.warning("REGRESSOR: Singular matrix, returning empty exposure")
            return FactorExposure(n_observations=n, forward_window=forward_window)

        # Decompose coefficients
        alpha = float(beta[0])
        betas = beta[1:]

        # Residuals and R²
        y_hat = X_full @ beta
        residuals = y - y_hat
        ss_res = float(np.sum(residuals ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r_sq = 1.0 - ss_res / ss_tot if ss_tot > 1e-15 else 0.0
        r_sq = max(0.0, min(1.0, r_sq))

        # Standard errors
        dof = n - (k + 1)
        if dof > 0:
            mse = ss_res / dof
            se_beta = np.sqrt(np.diag(XtX_inv) * mse)
            se_alpha = float(se_beta[0]) if se_beta[0] > 0 else 1e-10
        else:
            se_alpha = 1e-10

        t_stat = alpha / se_alpha
        significant = abs(t_stat) > 2.0

        # Extract factor betas (pad if fewer than 4)
        b_mkt = float(betas[0]) if len(betas) > 0 else 0.0
        b_smb = float(betas[1]) if len(betas) > 1 else 0.0
        b_hml = float(betas[2]) if len(betas) > 2 else 0.0
        b_umd = float(betas[3]) if len(betas) > 3 else 0.0

        return FactorExposure(
            factor_alpha=round(alpha, 6),
            alpha_t_stat=round(t_stat, 4),
            alpha_significant=significant,
            beta_market=round(b_mkt, 4),
            beta_size=round(b_smb, 4),
            beta_value=round(b_hml, 4),
            beta_momentum=round(b_umd, 4),
            r_squared=round(r_sq, 4),
            factor_neutrality=round(1.0 - r_sq, 4),
            n_observations=n,
            forward_window=forward_window,
        )
