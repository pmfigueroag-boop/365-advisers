"""
src/engines/factor_risk/barra_factor_model.py
--------------------------------------------------------------------------
Barra-Style Cross-Sectional Factor Model.

Estimates factor exposures and covariance from fundamental characteristics
and price returns, suitable for feeding into RiskDecomposer.

Methodology:
  1. Compute standardised characteristics (z-scores) as factor proxies
  2. Cross-sectional regression: r_i = Σ β_ij × f_j + ε_i
  3. Estimate factor covariance from time series of factor returns
  4. Estimate residual variances from regression residuals

Supported factors:
  - Market (beta to benchmark)
  - Size (log market cap)
  - Value (book-to-price or earnings yield)
  - Momentum (12m-1m return)
  - Volatility (realised vol)

Usage::

    model = BarraFactorModel()
    result = model.estimate(
        tickers=["AAPL", "MSFT", ...],
        characteristics={"AAPL": {"market_cap": 3e12, ...}, ...},
        returns={"AAPL": [0.01, -0.02, ...], ...},
    )
"""

from __future__ import annotations

import logging
import math

from pydantic import BaseModel, Field

from src.engines.factor_risk.models import FactorExposure

logger = logging.getLogger("365advisers.factor_risk.barra")


# ── Contracts ────────────────────────────────────────────────────────────────

BARRA_FACTORS = ["market", "size", "value", "momentum", "volatility"]


class BarraEstimation(BaseModel):
    """Result of Barra factor model estimation."""
    tickers: list[str] = Field(default_factory=list)
    factors: list[str] = Field(default_factory=list)
    exposures: list[FactorExposure] = Field(default_factory=list)
    factor_covariance: list[list[float]] = Field(default_factory=list)
    factor_returns: dict[str, float] = Field(default_factory=dict)
    residual_variances: dict[str, float] = Field(default_factory=dict)
    r_squared_avg: float = 0.0
    n_periods: int = 0


# ── Engine ───────────────────────────────────────────────────────────────────

class BarraFactorModel:
    """
    Estimate factor exposures from fundamental characteristics.

    Process:
    1. Standardise characteristics to z-scores
    2. Assign factor exposures from z-scores
    3. Estimate factor returns via cross-sectional regression
    4. Compute factor covariance and residual variances
    """

    def __init__(self, factors: list[str] | None = None) -> None:
        self.factors = factors or BARRA_FACTORS

    def estimate(
        self,
        tickers: list[str],
        characteristics: dict[str, dict[str, float]],
        returns: dict[str, list[float]] | None = None,
    ) -> BarraEstimation:
        """
        Estimate factor model from characteristics and optional returns.

        Parameters
        ----------
        tickers : list[str]
            Universe of tickers.
        characteristics : dict[str, dict]
            Per-ticker characteristics: market_cap, book_to_price,
            momentum_12m, realised_vol, beta.
        returns : dict[str, list[float]] | None
            Historical daily returns per ticker (for factor covariance).
        """
        if len(tickers) < 2:
            return BarraEstimation(factors=self.factors)

        # Step 1: Compute z-scores for each characteristic
        exposures = self._compute_exposures(tickers, characteristics)

        # Step 2: Estimate factor returns (cross-sectional averages)
        factor_returns = self._estimate_factor_returns(
            tickers, exposures, returns,
        )

        # Step 3: Factor covariance matrix
        factor_cov = self._estimate_factor_covariance(
            tickers, exposures, returns,
        )

        # Step 4: Residual variances
        residual_vars = self._estimate_residuals(
            tickers, exposures, returns, factor_returns,
        )

        exposure_list = [
            FactorExposure(
                ticker=t,
                exposures=exposures[t],
                r_squared=0.0,
            )
            for t in tickers if t in exposures
        ]

        logger.info(
            "BARRA: Estimated %d factors for %d tickers",
            len(self.factors), len(tickers),
        )

        return BarraEstimation(
            tickers=tickers,
            factors=self.factors,
            exposures=exposure_list,
            factor_covariance=factor_cov,
            factor_returns=factor_returns,
            residual_variances=residual_vars,
            n_periods=len(next(iter(returns.values()), [])) if returns else 0,
        )

    def _compute_exposures(
        self,
        tickers: list[str],
        characteristics: dict[str, dict[str, float]],
    ) -> dict[str, dict[str, float]]:
        """Compute standardised factor exposures from characteristics."""
        # Collect raw values per factor
        raw: dict[str, list[tuple[str, float]]] = {f: [] for f in self.factors}

        for t in tickers:
            chars = characteristics.get(t, {})

            # Map characteristics to factors
            if "beta" in chars:
                raw["market"].append((t, chars["beta"]))
            else:
                raw["market"].append((t, 1.0))

            if "market_cap" in chars:
                raw["size"].append((t, math.log(max(chars["market_cap"], 1e6))))
            else:
                raw["size"].append((t, 0.0))

            if "book_to_price" in chars:
                raw["value"].append((t, chars["book_to_price"]))
            elif "earnings_yield" in chars:
                raw["value"].append((t, chars["earnings_yield"]))
            else:
                raw["value"].append((t, 0.0))

            if "momentum_12m" in chars:
                raw["momentum"].append((t, chars["momentum_12m"]))
            else:
                raw["momentum"].append((t, 0.0))

            if "realised_vol" in chars:
                raw["volatility"].append((t, chars["realised_vol"]))
            else:
                raw["volatility"].append((t, 0.0))

        # Z-score standardisation
        exposures: dict[str, dict[str, float]] = {t: {} for t in tickers}

        for factor in self.factors:
            vals = raw.get(factor, [])
            if not vals:
                continue

            values = [v for _, v in vals]
            n = len(values)
            mean = sum(values) / n
            var = sum((v - mean) ** 2 for v in values) / max(n - 1, 1)
            std = math.sqrt(var) if var > 0 else 1.0

            for ticker, v in vals:
                z = (v - mean) / std if std > 1e-8 else 0.0
                # Clip to [-3, 3] to limit outlier impact
                z = max(-3.0, min(3.0, z))
                exposures[ticker][factor] = round(z, 4)

        return exposures

    def _estimate_factor_returns(
        self,
        tickers: list[str],
        exposures: dict[str, dict[str, float]],
        returns: dict[str, list[float]] | None,
    ) -> dict[str, float]:
        """Estimate factor returns as exposure-weighted average returns."""
        if not returns:
            return {f: 0.0 for f in self.factors}

        factor_returns: dict[str, float] = {}

        for factor in self.factors:
            weighted_sum = 0.0
            total_abs_exposure = 0.0

            for t in tickers:
                r_list = returns.get(t, [])
                if not r_list:
                    continue
                avg_r = sum(r_list) / len(r_list)
                exp = exposures.get(t, {}).get(factor, 0.0)

                weighted_sum += exp * avg_r
                total_abs_exposure += abs(exp)

            if total_abs_exposure > 0:
                factor_returns[factor] = round(
                    weighted_sum / total_abs_exposure, 6,
                )
            else:
                factor_returns[factor] = 0.0

        return factor_returns

    def _estimate_factor_covariance(
        self,
        tickers: list[str],
        exposures: dict[str, dict[str, float]],
        returns: dict[str, list[float]] | None,
    ) -> list[list[float]]:
        """Estimate factor covariance matrix."""
        k = len(self.factors)

        if not returns:
            # Identity × small variance
            return [[0.0001 if i == j else 0.0 for j in range(k)] for i in range(k)]

        # Simple approach: compute factor return time series, then covariance
        # For each period, cross-sectional regression gives factor returns
        # Simplified: use exposure-weighted returns as proxy
        n_periods = min(len(r) for r in returns.values()) if returns else 0
        if n_periods < 5:
            return [[0.0001 if i == j else 0.0 for j in range(k)] for i in range(k)]

        # Factor return time series
        factor_ts: dict[str, list[float]] = {f: [] for f in self.factors}

        for t_idx in range(n_periods):
            for factor in self.factors:
                weighted = 0.0
                total_w = 0.0
                for ticker in tickers:
                    r_list = returns.get(ticker, [])
                    if t_idx >= len(r_list):
                        continue
                    exp = exposures.get(ticker, {}).get(factor, 0.0)
                    weighted += exp * r_list[t_idx]
                    total_w += abs(exp)
                factor_ts[factor].append(
                    weighted / total_w if total_w > 0 else 0.0,
                )

        # Covariance matrix
        cov = [[0.0] * k for _ in range(k)]
        means = {f: sum(factor_ts[f]) / n_periods for f in self.factors}

        for i, fi in enumerate(self.factors):
            for j, fj in enumerate(self.factors):
                covar = sum(
                    (factor_ts[fi][t] - means[fi]) * (factor_ts[fj][t] - means[fj])
                    for t in range(n_periods)
                ) / max(n_periods - 1, 1)
                cov[i][j] = round(covar, 8)

        return cov

    def _estimate_residuals(
        self,
        tickers: list[str],
        exposures: dict[str, dict[str, float]],
        returns: dict[str, list[float]] | None,
        factor_returns: dict[str, float],
    ) -> dict[str, float]:
        """Estimate per-stock residual variance."""
        residuals: dict[str, float] = {}

        for t in tickers:
            r_list = returns.get(t, []) if returns else []
            if not r_list:
                residuals[t] = 0.01  # Default
                continue

            avg_r = sum(r_list) / len(r_list)
            # Predicted return from factor model
            predicted = sum(
                exposures.get(t, {}).get(f, 0.0) * factor_returns.get(f, 0.0)
                for f in self.factors
            )
            # Residual variance
            residual_r = [r - predicted for r in r_list]
            mean_res = sum(residual_r) / len(residual_r)
            var = sum((r - mean_res) ** 2 for r in residual_r) / max(len(residual_r) - 1, 1)
            residuals[t] = round(var, 8)

        return residuals
