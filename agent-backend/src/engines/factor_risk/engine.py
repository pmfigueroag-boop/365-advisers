"""
src/engines/factor_risk/engine.py — Factor Risk Engine orchestrator.
"""
from __future__ import annotations
import numpy as np
import logging
from src.engines.factor_risk.models import (
    FactorExposure, FactorRiskDecomposition, FactorModelResult,
)
from src.engines.factor_risk.factor_model import FactorModel
from src.engines.factor_risk.risk_decomposer import RiskDecomposer

logger = logging.getLogger("365advisers.factor_risk.engine")


class FactorRiskEngine:
    """
    Unified Barra-style factor risk analysis.

    Pipeline: factor returns → exposure estimation → covariance → risk decomposition.
    """

    @classmethod
    def build_model(
        cls,
        asset_returns: dict[str, list[float]],
        factor_returns: dict[str, list[float]],
    ) -> FactorModelResult:
        """Build complete factor model."""
        exposures = FactorModel.estimate_exposures(asset_returns, factor_returns)
        factors, cov = FactorModel.compute_factor_covariance(factor_returns)

        # Factor mean returns (annualised)
        factor_rets = {}
        for f in factors:
            factor_rets[f] = round(float(np.mean(factor_returns[f]) * 252), 6)

        return FactorModelResult(
            tickers=sorted(asset_returns.keys()),
            factors=factors,
            exposures=exposures,
            factor_returns=factor_rets,
            factor_covariance=cov.tolist(),
        )

    @classmethod
    def decompose_risk(
        cls,
        weights: dict[str, float],
        asset_returns: dict[str, list[float]],
        factor_returns: dict[str, list[float]],
    ) -> FactorRiskDecomposition:
        """Full pipeline: estimate exposures → compute covariance → decompose risk."""
        exposures = FactorModel.estimate_exposures(asset_returns, factor_returns)
        factors, cov = FactorModel.compute_factor_covariance(factor_returns)
        residual_vars = FactorModel.compute_residual_variance(
            asset_returns, factor_returns, exposures,
        )
        return RiskDecomposer.decompose(weights, exposures, cov, factors, residual_vars)

    @classmethod
    def decompose_with_model(
        cls,
        weights: dict[str, float],
        model: FactorModelResult,
        residual_variances: dict[str, float],
    ) -> FactorRiskDecomposition:
        """Decompose risk using pre-built model."""
        cov = np.array(model.factor_covariance)
        return RiskDecomposer.decompose(
            weights, model.exposures, cov, model.factors, residual_variances,
        )

    @classmethod
    def generate_synthetic_factors(
        cls,
        n_obs: int = 252,
        seed: int | None = None,
    ) -> dict[str, list[float]]:
        """Generate synthetic factor returns for testing/demo."""
        if seed is not None:
            np.random.seed(seed)

        params = {
            "market":   (0.0004, 0.010),
            "size":     (0.0001, 0.005),
            "value":    (0.0001, 0.004),
            "momentum": (0.0002, 0.006),
            "quality":  (0.0001, 0.003),
            "volatility": (-0.0001, 0.008),
        }

        factors = {}
        for name, (mu, sigma) in params.items():
            factors[name] = (np.random.randn(n_obs) * sigma + mu).tolist()

        return factors
