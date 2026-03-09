"""src/engines/risk/engine.py — Risk engine orchestrator."""
from __future__ import annotations
import numpy as np
from src.engines.risk.models import VaRMethod, RiskReport, StressScenario
from src.engines.risk.var import VaRCalculator
from src.engines.risk.cvar import CVaRCalculator
from src.engines.risk.stress import StressTester


class RiskEngine:
    """Unified risk assessment: VaR + CVaR + stress testing."""

    @classmethod
    def full_report(
        cls, returns: list[float], portfolio_value: float = 1_000_000.0,
        confidence: float = 0.95, horizon_days: int = 1,
        portfolio_weights: dict[str, float] | None = None,
        var_method: VaRMethod = VaRMethod.HISTORICAL,
    ) -> RiskReport:
        """Generate a comprehensive risk report."""
        # VaR
        if var_method == VaRMethod.HISTORICAL:
            var = VaRCalculator.historical(returns, confidence, portfolio_value, horizon_days)
        elif var_method == VaRMethod.MONTE_CARLO:
            var = VaRCalculator.monte_carlo(returns, confidence, portfolio_value, horizon_days)
        else:
            arr = np.array(returns)
            var = VaRCalculator.parametric(float(np.mean(arr)), float(np.std(arr)),
                                           confidence, portfolio_value, horizon_days)

        # CVaR
        cvar = CVaRCalculator.historical(returns, confidence, portfolio_value)

        # Stress
        stress_results = []
        if portfolio_weights:
            stress_results = StressTester.run_all_builtin(portfolio_weights, portfolio_value)

        # Summary
        arr = np.array(returns)
        summary = {
            "annualised_vol": round(float(np.std(arr) * np.sqrt(252)), 4),
            "max_drawdown_daily": round(float(np.min(arr)), 6),
            "skewness": round(float(cls._skewness(arr)), 4),
            "kurtosis": round(float(cls._kurtosis(arr)), 4),
        }

        return RiskReport(
            portfolio_value=portfolio_value,
            var=var, cvar=cvar,
            stress_results=stress_results,
            risk_summary=summary,
        )

    @staticmethod
    def _skewness(arr):
        n = len(arr)
        if n < 3:
            return 0
        m = np.mean(arr)
        s = np.std(arr)
        if s == 0:
            return 0
        return float(np.mean(((arr - m) / s) ** 3))

    @staticmethod
    def _kurtosis(arr):
        n = len(arr)
        if n < 4:
            return 0
        m = np.mean(arr)
        s = np.std(arr)
        if s == 0:
            return 0
        return float(np.mean(((arr - m) / s) ** 4) - 3)  # excess kurtosis
