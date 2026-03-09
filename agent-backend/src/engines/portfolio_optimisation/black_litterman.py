"""
src/engines/portfolio_optimisation/black_litterman.py — Black-Litterman model.

Combines market equilibrium returns with investor views
to produce posterior expected returns for MVO.
"""
from __future__ import annotations
import numpy as np
import logging

logger = logging.getLogger("365advisers.optimisation.black_litterman")


class BlackLittermanModel:
    """
    Black-Litterman model.

    Steps:
    1. Compute implied equilibrium returns (Π = δΣw_mkt)
    2. Incorporate investor views via Bayesian update
    3. Output posterior returns for Markowitz
    """

    @classmethod
    def implied_returns(
        cls,
        cov_matrix: np.ndarray,
        market_weights: np.ndarray,
        risk_aversion: float = 2.5,
    ) -> np.ndarray:
        """Compute implied equilibrium returns: Π = δΣw"""
        return risk_aversion * cov_matrix @ market_weights

    @classmethod
    def posterior_returns(
        cls,
        cov_matrix: np.ndarray,
        market_weights: np.ndarray,
        P: np.ndarray,
        Q: np.ndarray,
        omega: np.ndarray | None = None,
        risk_aversion: float = 2.5,
        tau: float = 0.05,
    ) -> np.ndarray:
        """
        Compute Black-Litterman posterior returns.

        Args:
            cov_matrix: N×N covariance matrix
            market_weights: N-vector of market cap weights
            P: K×N pick matrix (K views on N assets)
            Q: K-vector of view returns
            omega: K×K uncertainty of views (diagonal). If None, auto-compute.
            risk_aversion: δ (market risk aversion)
            tau: τ (uncertainty scalar on Σ)

        Returns:
            N-vector of posterior expected returns
        """
        sigma = np.array(cov_matrix, dtype=np.float64)
        w_mkt = np.array(market_weights, dtype=np.float64)
        P = np.array(P, dtype=np.float64)
        Q = np.array(Q, dtype=np.float64)

        # Implied equilibrium returns
        pi = cls.implied_returns(sigma, w_mkt, risk_aversion)

        # Uncertainty of views
        if omega is None:
            omega = np.diag(np.diag(tau * P @ sigma @ P.T))

        tau_sigma = tau * sigma

        # Posterior: μ_BL = [(τΣ)⁻¹ + P'Ω⁻¹P]⁻¹ [(τΣ)⁻¹π + P'Ω⁻¹Q]
        tau_sigma_inv = np.linalg.inv(tau_sigma)
        omega_inv = np.linalg.inv(omega)

        M = np.linalg.inv(tau_sigma_inv + P.T @ omega_inv @ P)
        posterior = M @ (tau_sigma_inv @ pi + P.T @ omega_inv @ Q)

        return posterior

    @classmethod
    def full_model(
        cls,
        tickers: list[str],
        cov_matrix: np.ndarray,
        market_caps: dict[str, float],
        views: list[dict],
        risk_aversion: float = 2.5,
        tau: float = 0.05,
    ) -> dict[str, float]:
        """
        Full Black-Litterman: market caps + views → posterior returns.

        views format: [
            {"asset": "AAPL", "return": 0.10, "confidence": 0.8},
            {"asset": "MSFT", "return": 0.08, "confidence": 0.6},
        ]
        """
        n = len(tickers)

        # Market weights from caps
        caps = np.array([market_caps.get(t, 1.0) for t in tickers])
        w_mkt = caps / caps.sum()

        # Build P (pick matrix) and Q (views) from simple absolute views
        if not views:
            pi = cls.implied_returns(cov_matrix, w_mkt, risk_aversion)
            return {t: round(float(r), 6) for t, r in zip(tickers, pi)}

        k = len(views)
        P = np.zeros((k, n))
        Q = np.zeros(k)
        confidences = []

        for i, v in enumerate(views):
            asset = v.get("asset", "")
            if asset in tickers:
                idx = tickers.index(asset)
                P[i, idx] = 1.0
                Q[i] = v.get("return", 0.0)
                confidences.append(v.get("confidence", 0.5))

        # Omega: lower confidence → higher uncertainty
        omega_diag = []
        for i, conf in enumerate(confidences):
            view_var = tau * (P[i:i+1] @ cov_matrix @ P[i:i+1].T)[0, 0]
            omega_diag.append(view_var / max(conf, 0.01))
        omega = np.diag(omega_diag)

        posterior = cls.posterior_returns(cov_matrix, w_mkt, P, Q, omega, risk_aversion, tau)
        return {t: round(float(r), 6) for t, r in zip(tickers, posterior)}
