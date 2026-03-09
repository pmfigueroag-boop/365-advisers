"""src/engines/risk/var.py — Value-at-Risk calculators."""
from __future__ import annotations
import numpy as np
import logging
from src.engines.risk.models import VaRMethod, VaRResult

logger = logging.getLogger("365advisers.risk.var")


class VaRCalculator:
    """Historical, Parametric, and Monte Carlo VaR."""

    @classmethod
    def historical(
        cls, returns: list[float], confidence: float = 0.95,
        portfolio_value: float = 1_000_000.0, horizon_days: int = 1,
    ) -> VaRResult:
        """Historical VaR: percentile of actual return distribution."""
        arr = np.array(returns, dtype=np.float64)
        var_pct = float(np.percentile(arr, (1 - confidence) * 100))
        var_pct_scaled = var_pct * np.sqrt(horizon_days)
        return VaRResult(
            method=VaRMethod.HISTORICAL,
            confidence_level=confidence,
            horizon_days=horizon_days,
            var_pct=round(abs(var_pct_scaled), 6),
            var_amount=round(abs(var_pct_scaled) * portfolio_value, 2),
            portfolio_value=portfolio_value,
        )

    @classmethod
    def parametric(
        cls, mean: float, std: float, confidence: float = 0.95,
        portfolio_value: float = 1_000_000.0, horizon_days: int = 1,
    ) -> VaRResult:
        """Parametric VaR (variance-covariance): assumes normal distribution."""
        from scipy.stats import norm
        z = norm.ppf(1 - confidence)  # negative
        var_pct = -(mean + z * std) * np.sqrt(horizon_days)
        return VaRResult(
            method=VaRMethod.PARAMETRIC,
            confidence_level=confidence,
            horizon_days=horizon_days,
            var_pct=round(abs(var_pct), 6),
            var_amount=round(abs(var_pct) * portfolio_value, 2),
            portfolio_value=portfolio_value,
        )

    @classmethod
    def monte_carlo(
        cls, returns: list[float], confidence: float = 0.95,
        portfolio_value: float = 1_000_000.0, horizon_days: int = 1,
        n_sims: int = 10_000, seed: int = 42,
    ) -> VaRResult:
        """Monte Carlo VaR: simulate return paths from fitted distribution."""
        np.random.seed(seed)
        arr = np.array(returns, dtype=np.float64)
        mu = float(np.mean(arr))
        sigma = float(np.std(arr))

        # Simulate
        sims = np.random.normal(mu, sigma, (n_sims, horizon_days))
        cumulative = sims.sum(axis=1)
        var_pct = float(np.percentile(cumulative, (1 - confidence) * 100))

        return VaRResult(
            method=VaRMethod.MONTE_CARLO,
            confidence_level=confidence,
            horizon_days=horizon_days,
            var_pct=round(abs(var_pct), 6),
            var_amount=round(abs(var_pct) * portfolio_value, 2),
            portfolio_value=portfolio_value,
        )
