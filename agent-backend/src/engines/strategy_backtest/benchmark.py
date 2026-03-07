"""
src/engines/strategy_backtest/benchmark.py
─────────────────────────────────────────────────────────────────────────────
BenchmarkComparison — compare strategy performance to benchmarks.
"""

from __future__ import annotations

import logging
from .metrics import StrategyMetrics

logger = logging.getLogger("365advisers.strategy_backtest.benchmark")


BENCHMARK_DEFINITIONS = {
    "spy": {"name": "S&P 500", "ticker": "SPY", "type": "equity_index"},
    "qqq": {"name": "Nasdaq 100", "ticker": "QQQ", "type": "equity_index"},
    "iwm": {"name": "Russell 2000", "ticker": "IWM", "type": "equity_index"},
    "agg": {"name": "US Aggregate Bond", "ticker": "AGG", "type": "fixed_income"},
    "6040": {"name": "60/40 Portfolio", "ticker": "VBINX", "type": "balanced"},
    "equal_weight": {"name": "Equal Weight Universe", "ticker": None, "type": "custom"},
}


class BenchmarkComparison:
    """Compare strategy results against standard benchmarks."""

    @staticmethod
    def compare(
        strategy_values: list[float],
        benchmark_values: dict[str, list[float]],
    ) -> dict:
        """Compare strategy against multiple benchmarks.

        Args:
            strategy_values: Strategy portfolio value series
            benchmark_values: {benchmark_name: [values]}

        Returns:
            Comparison dict with relative metrics for each benchmark.
        """
        strategy_metrics = StrategyMetrics.compute(strategy_values)

        comparisons = {}
        for bm_name, bm_values in benchmark_values.items():
            if len(bm_values) < 2:
                continue

            bm_metrics = StrategyMetrics.compute(bm_values)
            relative_metrics = StrategyMetrics.compute(strategy_values, bm_values)

            comparisons[bm_name] = {
                "benchmark": BENCHMARK_DEFINITIONS.get(bm_name, {"name": bm_name}),
                "strategy_return": strategy_metrics["total_return"],
                "benchmark_return": bm_metrics["total_return"],
                "alpha": relative_metrics.get("alpha", 0.0),
                "tracking_error": relative_metrics.get("tracking_error", 0.0),
                "information_ratio": relative_metrics.get("information_ratio", 0.0),
                "strategy_sharpe": strategy_metrics["sharpe_ratio"],
                "benchmark_sharpe": bm_metrics["sharpe_ratio"],
                "strategy_max_dd": strategy_metrics["max_drawdown"],
                "benchmark_max_dd": bm_metrics["max_drawdown"],
                "outperformed": strategy_metrics["total_return"] > bm_metrics["total_return"],
            }

        return {
            "strategy_metrics": strategy_metrics,
            "comparisons": comparisons,
            "best_benchmark": min(comparisons.items(), key=lambda x: x[1]["alpha"])[0] if comparisons else None,
        }

    @staticmethod
    def list_benchmarks() -> list[dict]:
        """List available benchmark definitions."""
        return list(BENCHMARK_DEFINITIONS.values())
