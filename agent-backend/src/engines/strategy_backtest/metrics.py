"""
src/engines/strategy_backtest/metrics.py
─────────────────────────────────────────────────────────────────────────────
StrategyMetrics — risk-adjusted performance metrics for strategy evaluation.
"""

from __future__ import annotations

import math
from typing import Optional


class StrategyMetrics:
    """Compute risk-adjusted performance metrics from portfolio value series."""

    @staticmethod
    def compute(
        portfolio_values: list[float],
        benchmark_values: list[float] | None = None,
        periods_per_year: float = 252.0,
    ) -> dict:
        """Compute full metrics suite.

        Args:
            portfolio_values: Daily portfolio NAV series
            benchmark_values: Optional daily benchmark NAV series
            periods_per_year: Annualization factor

        Returns:
            Dict with Sharpe, Sortino, max drawdown, Calmar, etc.
        """
        if len(portfolio_values) < 2:
            return _empty_metrics()

        returns = _compute_returns(portfolio_values)
        n = len(returns)

        # Basic stats
        total_return = (portfolio_values[-1] - portfolio_values[0]) / portfolio_values[0]
        mean_return = sum(returns) / n
        ann_return = mean_return * periods_per_year

        # Volatility
        variance = sum((r - mean_return) ** 2 for r in returns) / max(n - 1, 1)
        std = math.sqrt(variance)
        ann_vol = std * math.sqrt(periods_per_year)

        # Sharpe
        sharpe = ann_return / ann_vol if ann_vol > 0 else 0.0

        # Sortino (downside deviation)
        downside_returns = [r for r in returns if r < 0]
        if downside_returns:
            down_var = sum(r ** 2 for r in downside_returns) / len(downside_returns)
            downside_dev = math.sqrt(down_var) * math.sqrt(periods_per_year)
            sortino = ann_return / downside_dev if downside_dev > 0 else 0.0
        else:
            sortino = float("inf") if ann_return > 0 else 0.0

        # Max drawdown
        max_dd, dd_start, dd_end = _max_drawdown(portfolio_values)

        # Calmar
        calmar = ann_return / abs(max_dd) if max_dd < 0 else float("inf")

        # Win rate
        win_count = sum(1 for r in returns if r > 0)
        win_rate = win_count / n if n > 0 else 0.0

        result = {
            "total_return": round(total_return, 4),
            "annualized_return": round(ann_return, 4),
            "annualized_volatility": round(ann_vol, 4),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(min(sortino, 99.0), 4),
            "max_drawdown": round(max_dd, 4),
            "max_drawdown_period": [dd_start, dd_end],
            "calmar_ratio": round(min(calmar, 99.0), 4),
            "win_rate": round(win_rate, 4),
            "total_periods": n,
        }

        # Benchmark comparison
        if benchmark_values and len(benchmark_values) >= 2:
            bm_returns = _compute_returns(benchmark_values)
            bm_total = (benchmark_values[-1] - benchmark_values[0]) / benchmark_values[0]

            # Active return
            alpha = total_return - bm_total

            # Tracking error
            min_len = min(len(returns), len(bm_returns))
            active_returns = [returns[i] - bm_returns[i] for i in range(min_len)]
            if active_returns:
                te_var = sum((r - sum(active_returns) / len(active_returns)) ** 2
                             for r in active_returns) / max(len(active_returns) - 1, 1)
                tracking_error = math.sqrt(te_var) * math.sqrt(periods_per_year)
                ir = alpha / tracking_error if tracking_error > 0 else 0.0
            else:
                tracking_error = 0.0
                ir = 0.0

            result["benchmark_return"] = round(bm_total, 4)
            result["alpha"] = round(alpha, 4)
            result["tracking_error"] = round(tracking_error, 4)
            result["information_ratio"] = round(ir, 4)

        return result


def _compute_returns(values: list[float]) -> list[float]:
    """Compute period-over-period returns."""
    return [(values[i] - values[i - 1]) / values[i - 1]
            for i in range(1, len(values)) if values[i - 1] > 0]


def _max_drawdown(values: list[float]) -> tuple[float, int, int]:
    """Compute max drawdown with start/end indices."""
    peak = values[0]
    max_dd = 0.0
    peak_idx = 0
    dd_start = 0
    dd_end = 0

    for i, v in enumerate(values):
        if v > peak:
            peak = v
            peak_idx = i
        dd = (v - peak) / peak if peak > 0 else 0.0
        if dd < max_dd:
            max_dd = dd
            dd_start = peak_idx
            dd_end = i

    return max_dd, dd_start, dd_end


def _empty_metrics() -> dict:
    return {
        "total_return": 0.0, "annualized_return": 0.0,
        "annualized_volatility": 0.0, "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0, "max_drawdown": 0.0,
        "max_drawdown_period": [0, 0], "calmar_ratio": 0.0,
        "win_rate": 0.0, "total_periods": 0,
    }
