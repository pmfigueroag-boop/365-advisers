"""src/engines/risk/cvar.py — Conditional VaR (Expected Shortfall)."""
from __future__ import annotations
import numpy as np
from src.engines.risk.models import VaRMethod, CVaRResult


class CVaRCalculator:
    """Conditional VaR = expected loss beyond the VaR threshold."""

    @classmethod
    def historical(
        cls, returns: list[float], confidence: float = 0.95,
        portfolio_value: float = 1_000_000.0,
    ) -> CVaRResult:
        arr = np.array(returns, dtype=np.float64)
        cutoff = np.percentile(arr, (1 - confidence) * 100)
        tail = arr[arr <= cutoff]
        cvar_pct = float(np.mean(tail)) if len(tail) > 0 else float(cutoff)
        return CVaRResult(
            method=VaRMethod.HISTORICAL,
            confidence_level=confidence,
            cvar_pct=round(abs(cvar_pct), 6),
            cvar_amount=round(abs(cvar_pct) * portfolio_value, 2),
            var_amount=round(abs(cutoff) * portfolio_value, 2),
        )

    @classmethod
    def parametric(
        cls, mean: float, std: float, confidence: float = 0.95,
        portfolio_value: float = 1_000_000.0,
    ) -> CVaRResult:
        from scipy.stats import norm
        alpha = 1 - confidence
        z = norm.ppf(alpha)
        var_pct = -(mean + z * std)
        # CVaR for normal: mean + std * phi(z) / alpha
        cvar_pct = -(mean - std * norm.pdf(z) / alpha)
        return CVaRResult(
            method=VaRMethod.PARAMETRIC,
            confidence_level=confidence,
            cvar_pct=round(abs(cvar_pct), 6),
            cvar_amount=round(abs(cvar_pct) * portfolio_value, 2),
            var_amount=round(abs(var_pct) * portfolio_value, 2),
        )
