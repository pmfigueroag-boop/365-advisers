"""
src/engines/stat_arb/cointegration.py
──────────────────────────────────────────────────────────────────────────────
Engle-Granger cointegration test and Ornstein-Uhlenbeck half-life estimator.

Uses numpy for OLS regression and ADF-equivalent computation to avoid
hard dependency on statsmodels in production.
"""

from __future__ import annotations

import logging
import math

import numpy as np

from src.engines.stat_arb.models import CointegrationResult

logger = logging.getLogger("365advisers.stat_arb.cointegration")


def engle_granger_test(
    prices_a: list[float] | np.ndarray,
    prices_b: list[float] | np.ndarray,
    significance: float = 0.05,
    max_lag: int = 1,
) -> CointegrationResult:
    """
    Perform an Engle-Granger two-step cointegration test.

    Step 1: OLS regression  prices_a = α + β × prices_b + ε
    Step 2: ADF test on residuals ε to check for stationarity.

    Args:
        prices_a: Price series for asset A.
        prices_b: Price series for asset B.
        significance: p-value threshold (default 0.05).
        max_lag: Maximum lag for ADF test.

    Returns:
        CointegrationResult with test statistics, p-value, hedge ratio, etc.
    """
    a = np.asarray(prices_a, dtype=np.float64)
    b = np.asarray(prices_b, dtype=np.float64)

    n = min(len(a), len(b))
    if n < 30:
        return CointegrationResult(
            ticker_a="A", ticker_b="B",
            test_statistic=0.0, p_value=1.0,
            is_cointegrated=False, observations=n,
        )

    a = a[:n]
    b = b[:n]

    # Step 1: OLS  a = alpha + beta * b
    X = np.column_stack([np.ones(n), b])
    beta_hat = np.linalg.lstsq(X, a, rcond=None)[0]
    alpha, hedge_ratio = beta_hat[0], beta_hat[1]
    residuals = a - (alpha + hedge_ratio * b)

    # Step 2: ADF on residuals (simplified Dickey-Fuller with lag-1)
    adf_stat, p_value_approx, critical_values = _adf_test(residuals, max_lag)

    is_coint = p_value_approx < significance
    resid_std = float(np.std(residuals))

    # Half-life
    hl = estimate_half_life(residuals)

    return CointegrationResult(
        ticker_a="A",
        ticker_b="B",
        test_statistic=round(float(adf_stat), 4),
        p_value=round(float(p_value_approx), 4),
        critical_values=critical_values,
        is_cointegrated=is_coint,
        hedge_ratio=round(float(hedge_ratio), 6),
        half_life=round(hl, 2) if hl and hl > 0 else None,
        residual_std=round(resid_std, 6),
        observations=n,
    )


def estimate_half_life(spread: list[float] | np.ndarray) -> float:
    """
    Estimate the mean-reversion half-life using an AR(1) model.

    Fits:  Δspread_t = φ × spread_{t-1} + ε
    Half-life = -ln(2) / ln(1 + φ)

    Returns half-life in periods (trading days). Returns 0.0 if not
    mean-reverting (φ ≥ 0).
    """
    s = np.asarray(spread, dtype=np.float64)
    if len(s) < 10:
        return 0.0

    delta = np.diff(s)
    lagged = s[:-1]

    # OLS: delta = phi * lagged
    X = lagged.reshape(-1, 1)
    phi = float(np.linalg.lstsq(X, delta, rcond=None)[0][0])

    if phi >= 0:
        return 0.0  # Not mean-reverting

    ratio = 1.0 + phi
    if ratio <= 0 or ratio >= 1:
        return 0.0

    half_life = -math.log(2) / math.log(ratio)
    return max(half_life, 0.0)


# ── Internal: simplified ADF test ────────────────────────────────────────────

def _adf_test(
    residuals: np.ndarray,
    max_lag: int = 1,
) -> tuple[float, float, dict[str, float]]:
    """
    Simplified Augmented Dickey-Fuller test.

    Returns:
        (test_statistic, approximate_p_value, critical_values_dict)
    """
    n = len(residuals)
    if n < 20:
        return 0.0, 1.0, {}

    y = np.diff(residuals)
    y_lag = residuals[:-1]

    # Regression: Δy_t = γ × y_{t-1} + ε  (no constant, no trend for residuals)
    X = y_lag.reshape(-1, 1)
    gamma = float(np.linalg.lstsq(X, y, rcond=None)[0][0])

    # Standard error of gamma
    predicted = gamma * y_lag
    residual_errors = y - predicted
    se_resid = np.sqrt(np.sum(residual_errors ** 2) / (n - 2))
    se_gamma = se_resid / np.sqrt(np.sum(y_lag ** 2))

    if se_gamma == 0:
        return 0.0, 1.0, {}

    t_stat = gamma / se_gamma

    # Approximate p-value using MacKinnon critical values (simplified)
    # These are approximate critical values for n ~ 250 (Engle-Granger, no constant)
    critical_values = {
        "1%": -3.43,
        "5%": -2.86,
        "10%": -2.57,
    }

    # Crude p-value approximation
    if t_stat < -3.43:
        p_approx = 0.005
    elif t_stat < -2.86:
        p_approx = 0.03
    elif t_stat < -2.57:
        p_approx = 0.07
    elif t_stat < -1.94:
        p_approx = 0.15
    else:
        p_approx = 0.50 + 0.3 * min(t_stat + 1.0, 1.0)

    p_approx = max(0.001, min(p_approx, 0.999))

    return float(t_stat), p_approx, {k: round(v, 4) for k, v in critical_values.items()}
