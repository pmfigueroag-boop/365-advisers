"""
src/engines/validation/metrics.py
──────────────────────────────────────────────────────────────────────────────
Annualized performance metrics for the Alpha Validation System.

All metrics follow institutional conventions:
  - Sharpe: annualized, risk-free-rate adjusted
  - Sortino: only downside deviation
  - CAGR: geometric compound
  - Drawdown: peak-to-trough
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class PerformanceMetrics:
    """Container for a complete suite of performance metrics."""
    # Returns
    total_return: float = 0.0        # Cumulative %
    cagr: float = 0.0                # Annualized %

    # Risk-adjusted
    sharpe: float = 0.0              # Annualized, rf-adjusted
    sortino: float = 0.0             # Downside deviation only
    calmar: float = 0.0              # CAGR / max_drawdown

    # Drawdown
    max_drawdown: float = 0.0        # Max peak-to-trough %
    max_drawdown_days: int = 0       # Duration of worst drawdown

    # Win/Loss
    total_trades: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0            # win_count / total_trades
    profit_factor: float = 0.0       # sum(wins) / |sum(losses)|

    # Hit rates at horizons
    hit_rate_5d: float = 0.0
    hit_rate_20d: float = 0.0

    # Period info
    n_days: int = 0
    n_years: float = 0.0


def compute_metrics(
    returns: list[float],
    risk_free_rate: float = 0.045,
    trading_days: int = 252,
) -> PerformanceMetrics:
    """
    Compute all performance metrics from a series of daily % returns.

    Parameters
    ----------
    returns : list[float]
        Daily returns as decimals (e.g. 0.01 = +1%).
    risk_free_rate : float
        Annual risk-free rate (default 4.5% for 2024-era).
    trading_days : int
        Trading days per year.
    """
    if not returns or len(returns) < 2:
        return PerformanceMetrics()

    n = len(returns)
    n_years = n / trading_days if trading_days > 0 else 1.0

    # ── Cumulative return ────────────────────────────────────────────────
    cum = 1.0
    for r in returns:
        cum *= (1 + r)
    total_return = cum - 1.0

    # ── CAGR ─────────────────────────────────────────────────────────────
    if n_years > 0 and cum > 0:
        cagr = cum ** (1 / n_years) - 1
    else:
        cagr = 0.0

    # ── Sharpe (annualized) ──────────────────────────────────────────────
    daily_rf = (1 + risk_free_rate) ** (1 / trading_days) - 1
    excess = [r - daily_rf for r in returns]
    mean_excess = sum(excess) / n
    std_excess = _std(excess)
    sharpe = (mean_excess / std_excess * math.sqrt(trading_days)) if std_excess > 0 else 0.0

    # ── Sortino (downside deviation only) ────────────────────────────────
    downside = [min(r - daily_rf, 0) ** 2 for r in returns]
    dd_std = math.sqrt(sum(downside) / n) if n > 0 else 0.0
    sortino = (mean_excess / dd_std * math.sqrt(trading_days)) if dd_std > 0 else 0.0

    # ── Max Drawdown ─────────────────────────────────────────────────────
    peak = 1.0
    equity = 1.0
    max_dd = 0.0
    dd_start = 0
    max_dd_days = 0
    current_dd_start = 0
    for i, r in enumerate(returns):
        equity *= (1 + r)
        if equity > peak:
            peak = equity
            current_dd_start = i
        dd = (peak - equity) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
            dd_start = current_dd_start
            max_dd_days = i - dd_start

    # ── Calmar ───────────────────────────────────────────────────────────
    calmar = abs(cagr / max_dd) if max_dd > 0 else 0.0

    # ── Win rate / profit factor ─────────────────────────────────────────
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    total_trades = len(wins) + len(losses)
    win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
    sum_losses = abs(sum(losses))
    profit_factor = sum(wins) / sum_losses if sum_losses > 0 else float("inf")

    return PerformanceMetrics(
        total_return=round(total_return, 6),
        cagr=round(cagr, 6),
        sharpe=round(sharpe, 4),
        sortino=round(sortino, 4),
        calmar=round(calmar, 4),
        max_drawdown=round(max_dd, 6),
        max_drawdown_days=max_dd_days,
        total_trades=total_trades,
        win_count=len(wins),
        loss_count=len(losses),
        win_rate=round(win_rate, 4),
        profit_factor=round(profit_factor, 4),
        n_days=n,
        n_years=round(n_years, 2),
    )


def compute_hit_rates(
    signal_values: list[float],
    forward_returns: list[float],
    is_bullish: list[bool],
) -> tuple[float, int]:
    """
    Compute hit rate: fraction of signals where direction matched return.

    Returns (hit_rate, sample_size).
    """
    if not signal_values:
        return 0.0, 0

    hits = 0
    total = 0
    for val, ret, bullish in zip(signal_values, forward_returns, is_bullish):
        if val is None or ret is None:
            continue
        total += 1
        if bullish and ret > 0:
            hits += 1
        elif not bullish and ret < 0:
            hits += 1

    return (hits / total if total > 0 else 0.0, total)


def _std(values: list[float]) -> float:
    """Population standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
