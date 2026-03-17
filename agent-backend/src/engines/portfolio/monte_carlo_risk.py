"""
src/engines/portfolio/monte_carlo_risk.py
--------------------------------------------------------------------------
Monte Carlo VaR / CVaR — probabilistic risk measurement.

Generates N simulated portfolio return paths, then measures:
  - VaR (Value at Risk): max loss at X% confidence
  - CVaR (Conditional VaR): average loss beyond VaR (tail risk)
  - Max drawdown distribution
  - Probability of ruin (loss > threshold)

Methods:
  1. Parametric: assume normal/t-distribution
  2. Historical bootstrap: resample from actual returns
  3. Correlated simulation: use Cholesky of covariance

Usage::

    mc = MonteCarloRisk(n_simulations=10000, horizon_days=21)
    report = mc.run(weights, expected_returns, covariance)
"""

from __future__ import annotations

import logging
import math
import random

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.portfolio.mc_risk")


# ── Contracts ────────────────────────────────────────────────────────────────

class VaRResult(BaseModel):
    """Value at Risk results."""
    var_95: float = 0.0       # 95% VaR (loss amount)
    var_99: float = 0.0       # 99% VaR
    cvar_95: float = 0.0      # Expected shortfall at 95%
    cvar_99: float = 0.0      # Expected shortfall at 99%
    expected_return: float = 0.0
    expected_vol: float = 0.0
    max_drawdown_median: float = 0.0
    probability_of_loss: float = 0.0
    probability_of_ruin: float = Field(
        0.0, description="P(loss > 20%)",
    )
    n_simulations: int = 0
    horizon_days: int = 0
    method: str = "parametric"


class SimulationPath(BaseModel):
    """A single simulation path."""
    path_id: int = 0
    cumulative_return: float = 0.0
    max_drawdown: float = 0.0
    daily_returns: list[float] = Field(default_factory=list)


# ── Engine ───────────────────────────────────────────────────────────────────

class MonteCarloRisk:
    """
    Monte Carlo risk simulator.

    Parameters
    ----------
    n_simulations : int
        Number of simulation paths.
    horizon_days : int
        Simulation horizon in trading days.
    ruin_threshold : float
        Loss threshold for probability of ruin.
    seed : int | None
        Random seed for reproducibility.
    """

    def __init__(
        self,
        n_simulations: int = 10_000,
        horizon_days: int = 21,
        ruin_threshold: float = -0.20,
        seed: int | None = None,
    ) -> None:
        self.n_simulations = n_simulations
        self.horizon_days = horizon_days
        self.ruin_threshold = ruin_threshold
        self.rng = random.Random(seed)

    def run_parametric(
        self,
        portfolio_return: float,
        portfolio_vol: float,
    ) -> VaRResult:
        """
        Parametric Monte Carlo: assume normal distribution.

        Parameters
        ----------
        portfolio_return : float
            Expected daily return.
        portfolio_vol : float
            Daily volatility (std dev of returns).
        """
        daily_mu = portfolio_return
        daily_sigma = max(portfolio_vol, 1e-8)

        terminal_returns: list[float] = []
        max_drawdowns: list[float] = []

        for _ in range(self.n_simulations):
            # Simulate daily returns
            cum = 0.0
            peak = 0.0
            max_dd = 0.0

            for _ in range(self.horizon_days):
                daily_r = self.rng.gauss(daily_mu, daily_sigma)
                cum += daily_r
                if cum > peak:
                    peak = cum
                dd = cum - peak
                if dd < max_dd:
                    max_dd = dd

            terminal_returns.append(cum)
            max_drawdowns.append(max_dd)

        return self._compute_metrics(
            terminal_returns, max_drawdowns, "parametric",
        )

    def run_historical(
        self,
        historical_returns: list[float],
    ) -> VaRResult:
        """
        Historical bootstrap: resample from actual daily returns.

        Parameters
        ----------
        historical_returns : list[float]
            Historical daily portfolio returns.
        """
        if len(historical_returns) < 10:
            return VaRResult(method="historical")

        terminal_returns: list[float] = []
        max_drawdowns: list[float] = []

        for _ in range(self.n_simulations):
            # Sample with replacement
            cum = 0.0
            peak = 0.0
            max_dd = 0.0

            for _ in range(self.horizon_days):
                daily_r = self.rng.choice(historical_returns)
                cum += daily_r
                if cum > peak:
                    peak = cum
                dd = cum - peak
                if dd < max_dd:
                    max_dd = dd

            terminal_returns.append(cum)
            max_drawdowns.append(max_dd)

        return self._compute_metrics(
            terminal_returns, max_drawdowns, "historical",
        )

    def run_correlated(
        self,
        weights: dict[str, float],
        expected_returns: dict[str, float],
        covariance: list[list[float]],
        tickers: list[str],
    ) -> VaRResult:
        """
        Correlated simulation using Cholesky decomposition.

        Parameters
        ----------
        weights : dict[str, float]
            Portfolio weights.
        expected_returns : dict[str, float]
            Expected daily returns per asset.
        covariance : list[list[float]]
            Asset covariance matrix.
        tickers : list[str]
            Ticker order matching covariance rows.
        """
        n = len(tickers)
        if n < 1:
            return VaRResult(method="correlated")

        # Cholesky decomposition
        L = self._cholesky(covariance, n)
        w = [weights.get(t, 0) for t in tickers]
        mu = [expected_returns.get(t, 0) for t in tickers]

        terminal_returns: list[float] = []
        max_drawdowns: list[float] = []

        for _ in range(self.n_simulations):
            cum = 0.0
            peak = 0.0
            max_dd = 0.0

            for _ in range(self.horizon_days):
                # Generate correlated normals
                z = [self.rng.gauss(0, 1) for _ in range(n)]
                corr_z = [sum(L[i][j] * z[j] for j in range(i + 1)) for i in range(n)]

                # Asset returns
                port_r = sum(w[i] * (mu[i] + corr_z[i]) for i in range(n))
                cum += port_r
                if cum > peak:
                    peak = cum
                dd = cum - peak
                if dd < max_dd:
                    max_dd = dd

            terminal_returns.append(cum)
            max_drawdowns.append(max_dd)

        return self._compute_metrics(
            terminal_returns, max_drawdowns, "correlated",
        )

    def _compute_metrics(
        self,
        terminal_returns: list[float],
        max_drawdowns: list[float],
        method: str,
    ) -> VaRResult:
        """Compute VaR/CVaR from simulation results."""
        n = len(terminal_returns)
        if n == 0:
            return VaRResult(method=method)

        sorted_returns = sorted(terminal_returns)
        sorted_dd = sorted(max_drawdowns)

        # VaR: loss at percentile (negative = loss)
        idx_5 = max(int(n * 0.05), 0)
        idx_1 = max(int(n * 0.01), 0)

        var_95 = -sorted_returns[idx_5]   # Positive = loss amount
        var_99 = -sorted_returns[idx_1]

        # CVaR: average of returns below VaR
        cvar_95 = -sum(sorted_returns[:idx_5 + 1]) / max(idx_5 + 1, 1)
        cvar_99 = -sum(sorted_returns[:idx_1 + 1]) / max(idx_1 + 1, 1)

        # Summary stats
        mean_r = sum(terminal_returns) / n
        var_r = sum((r - mean_r) ** 2 for r in terminal_returns) / max(n - 1, 1)
        vol = math.sqrt(var_r)

        # Drawdown median
        dd_median = sorted_dd[n // 2]

        # Probabilities
        p_loss = sum(1 for r in terminal_returns if r < 0) / n
        p_ruin = sum(1 for r in terminal_returns if r < self.ruin_threshold) / n

        logger.info(
            "MC-RISK (%s): %d sims, VaR95=%.2f%%, CVaR95=%.2f%%, "
            "P(loss)=%.1f%%, P(ruin)=%.1f%%",
            method, n, var_95 * 100, cvar_95 * 100,
            p_loss * 100, p_ruin * 100,
        )

        return VaRResult(
            var_95=round(var_95, 6),
            var_99=round(var_99, 6),
            cvar_95=round(cvar_95, 6),
            cvar_99=round(cvar_99, 6),
            expected_return=round(mean_r, 6),
            expected_vol=round(vol, 6),
            max_drawdown_median=round(dd_median, 6),
            probability_of_loss=round(p_loss, 4),
            probability_of_ruin=round(p_ruin, 4),
            n_simulations=n,
            horizon_days=self.horizon_days,
            method=method,
        )

    @staticmethod
    def _cholesky(matrix: list[list[float]], n: int) -> list[list[float]]:
        """Cholesky decomposition: A = L × L^T."""
        L = [[0.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(i + 1):
                s = sum(L[i][k] * L[j][k] for k in range(j))

                if i == j:
                    val = matrix[i][i] - s
                    L[i][j] = math.sqrt(max(val, 1e-12))
                else:
                    if L[j][j] > 0:
                        L[i][j] = (matrix[i][j] - s) / L[j][j]

        return L
