"""
src/engines/factor_risk/risk_decomposer.py — Portfolio risk decomposition.

Decomposes portfolio risk into systematic (factor) and idiosyncratic components.
Computes per-factor risk contributions and marginal risk.

Risk model:
    σ²_p = w'BΣ_f B'w + w'Dw
    where:
        w = portfolio weights
        B = factor exposure matrix
        Σ_f = factor covariance
        D = diagonal residual covariance
"""
from __future__ import annotations
import numpy as np
import logging
from src.engines.factor_risk.models import (
    FactorExposure, FactorContribution, FactorRiskDecomposition,
)

logger = logging.getLogger("365advisers.factor_risk.decomposer")


class RiskDecomposer:
    """Decompose portfolio risk into factor contributions."""

    @classmethod
    def decompose(
        cls,
        weights: dict[str, float],
        exposures: list[FactorExposure],
        factor_covariance: np.ndarray,
        factor_names: list[str],
        residual_variances: dict[str, float],
    ) -> FactorRiskDecomposition:
        tickers = sorted(weights.keys())
        n = len(tickers)
        k = len(factor_names)

        w = np.array([weights.get(t, 0) for t in tickers])
        exposure_map = {e.ticker: e for e in exposures}

        # Build B: [n × k] factor exposure matrix
        B = np.zeros((n, k))
        for i, t in enumerate(tickers):
            exp = exposure_map.get(t)
            if exp:
                for j, f in enumerate(factor_names):
                    B[i, j] = exp.exposures.get(f, 0)

        # D: [n × n] diagonal residual covariance
        D = np.diag([residual_variances.get(t, 0.01) for t in tickers])

        # Portfolio factor exposures: b_p = B'w  [k × 1]
        b_p = B.T @ w

        # Systematic variance: w'BΣ_f B'w
        Sigma_f = np.array(factor_covariance, dtype=np.float64)
        systematic_var = float(w @ B @ Sigma_f @ B.T @ w)

        # Idiosyncratic variance: w'Dw
        idiosyncratic_var = float(w @ D @ w)

        # Total variance
        total_var = systematic_var + idiosyncratic_var
        total_risk = np.sqrt(total_var) if total_var > 0 else 0

        # Per-factor risk contributions
        # Marginal contribution of factor j: ∂σ/∂b_j
        # Risk contribution: b_j * (Σ_f b_p)_j / σ_p
        factor_risk_vec = Sigma_f @ b_p  # [k × 1]
        contributions = []

        for j, f in enumerate(factor_names):
            f_vol = np.sqrt(Sigma_f[j, j]) if Sigma_f[j, j] > 0 else 0
            rc = float(b_p[j] * factor_risk_vec[j])
            rc_pct = rc / total_var * 100 if total_var > 0 else 0
            marginal = float(factor_risk_vec[j] / total_risk) if total_risk > 0 else 0

            contributions.append(FactorContribution(
                factor=f,
                exposure=round(float(b_p[j]), 6),
                factor_volatility=round(f_vol, 6),
                risk_contribution=round(rc, 6),
                risk_pct=round(rc_pct, 2),
                marginal_risk=round(marginal, 6),
            ))

        # Add idiosyncratic
        idio_pct = idiosyncratic_var / total_var * 100 if total_var > 0 else 0
        contributions.append(FactorContribution(
            factor="idiosyncratic",
            risk_contribution=round(idiosyncratic_var, 6),
            risk_pct=round(idio_pct, 2),
        ))

        # Sort by absolute risk contribution
        contributions.sort(key=lambda c: abs(c.risk_contribution), reverse=True)
        top_factors = [c.factor for c in contributions[:5] if c.factor != "idiosyncratic"]

        sys_risk = np.sqrt(systematic_var) if systematic_var > 0 else 0
        idio_risk = np.sqrt(idiosyncratic_var) if idiosyncratic_var > 0 else 0
        sys_pct = systematic_var / total_var * 100 if total_var > 0 else 0

        return FactorRiskDecomposition(
            total_risk=round(total_risk, 6),
            systematic_risk=round(sys_risk, 6),
            idiosyncratic_risk=round(idio_risk, 6),
            systematic_pct=round(sys_pct, 2),
            factor_contributions=contributions,
            top_risk_factors=top_factors,
        )
