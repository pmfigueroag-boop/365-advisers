"""
src/engines/strategy_backtest/comparator.py
─────────────────────────────────────────────────────────────────────────────
StrategyComparator — compare multiple strategy backtest results with
regime-segmented analysis, pairwise correlation, and multi-dimension ranking.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

logger = logging.getLogger("365advisers.strategy_backtest.comparator")


class StrategyComparator:
    """Compare multiple strategy backtest results."""

    @staticmethod
    def compare(results: list[dict]) -> dict:
        """Compare multiple backtest results.

        Args:
            results: List of BacktestResult dicts from StrategyBacktestEngine.run()

        Returns:
            Comparison with rankings, regime analysis, and correlation matrix.
        """
        if not results:
            return {"error": "No results to compare"}

        # ── Strategy summary table ──
        strategies = []
        for r in results:
            m = r.get("metrics", {})
            strategies.append({
                "name": r.get("strategy_name", "unnamed"),
                "run_id": r.get("run_id", ""),
                "total_return": r.get("total_return", 0),
                "cagr": m.get("cagr", 0),
                "sharpe": m.get("sharpe_ratio", 0),
                "sortino": m.get("sortino_ratio", 0),
                "max_drawdown": m.get("max_drawdown", 0),
                "calmar": m.get("calmar_ratio", 0),
                "alpha": m.get("alpha"),
                "beta": m.get("beta"),
                "information_ratio": m.get("information_ratio"),
                "win_rate": m.get("win_rate", 0),
                "profit_factor": m.get("profit_factor", 0),
                "turnover": m.get("annualized_turnover", 0),
                "cost_drag": m.get("cost_drag_bps", 0),
                "avg_positions": m.get("avg_positions", 0),
            })

        # ── Rankings ──
        rankings = {}
        rank_keys = [
            ("by_sharpe", "sharpe", True),
            ("by_cagr", "cagr", True),
            ("by_sortino", "sortino", True),
            ("by_drawdown", "max_drawdown", False),  # Lower (less negative) is better
            ("by_alpha", "alpha", True),
            ("by_win_rate", "win_rate", True),
            ("by_cost_efficiency", "cost_drag", False),  # Lower cost is better
        ]
        for rank_name, key, descending in rank_keys:
            valid = [s for s in strategies if s.get(key) is not None]
            if valid:
                sorted_s = sorted(valid, key=lambda x: x[key] or 0, reverse=descending)
                rankings[rank_name] = [s["name"] for s in sorted_s]

        # ── Regime comparison ──
        regime_comparison = _compare_regimes(results)

        # ── Pairwise correlation ──
        correlation_matrix = _compute_correlations(results)

        # ── Drawdown comparison ──
        drawdown_profiles = {}
        for r in results:
            name = r.get("strategy_name", "unnamed")
            ec = r.get("equity_curve", [])
            drawdown_profiles[name] = {
                "max_drawdown": r.get("metrics", {}).get("max_drawdown", 0),
                "max_dd_duration": r.get("metrics", {}).get("max_dd_duration_days", 0),
                "drawdown_series": [e.get("drawdown", 0) for e in ec],
            }

        # Sort strategies by Sharpe
        strategies.sort(key=lambda s: s.get("sharpe", 0), reverse=True)

        return {
            "report_type": "strategy_comparison",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "strategy_count": len(strategies),
            "strategies": strategies,
            "rankings": rankings,
            "regime_comparison": regime_comparison,
            "correlation_matrix": correlation_matrix,
            "drawdown_profiles": drawdown_profiles,
            "best_overall": strategies[0]["name"] if strategies else None,
        }


def _compare_regimes(results: list[dict]) -> dict:
    """Compare strategy performance across regimes."""
    # Collect all regimes
    all_regimes: set[str] = set()
    for r in results:
        ra = r.get("regime_analysis", {}).get("regimes", {})
        all_regimes.update(ra.keys())

    regime_table: dict[str, dict] = {}
    for regime in sorted(all_regimes):
        regime_table[regime] = {}
        best_sharpe = -float("inf")
        worst_sharpe = float("inf")
        best_name = ""
        worst_name = ""

        for r in results:
            name = r.get("strategy_name", "unnamed")
            ra = r.get("regime_analysis", {}).get("regimes", {})
            regime_data = ra.get(regime, {})

            sharpe = regime_data.get("sharpe_ratio", 0)
            regime_table[regime][name] = {
                "annualized_return": regime_data.get("annualized_return", 0),
                "sharpe_ratio": sharpe,
                "win_rate": regime_data.get("win_rate", 0),
                "periods": regime_data.get("periods", 0),
            }

            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_name = name
            if sharpe < worst_sharpe:
                worst_sharpe = sharpe
                worst_name = name

        regime_table[regime]["_best"] = best_name
        regime_table[regime]["_worst"] = worst_name

    return regime_table


def _compute_correlations(results: list[dict]) -> dict:
    """Compute pairwise return correlations between strategies."""
    # Extract return series from equity curves
    return_series: dict[str, list[float]] = {}
    for r in results:
        name = r.get("strategy_name", "unnamed")
        ec = r.get("equity_curve", [])
        values = [e["portfolio_value"] for e in ec]
        if len(values) > 1:
            returns = [(values[i] - values[i - 1]) / values[i - 1]
                       for i in range(1, len(values)) if values[i - 1] > 0]
            return_series[name] = returns

    names = list(return_series.keys())
    matrix: dict[str, dict[str, float]] = {}

    for i, name_a in enumerate(names):
        matrix[name_a] = {}
        for j, name_b in enumerate(names):
            if i == j:
                matrix[name_a][name_b] = 1.0
            elif j < i:
                matrix[name_a][name_b] = matrix[name_b][name_a]
            else:
                rets_a = return_series[name_a]
                rets_b = return_series[name_b]
                min_len = min(len(rets_a), len(rets_b))
                if min_len < 2:
                    matrix[name_a][name_b] = 0.0
                    continue

                a = rets_a[:min_len]
                b = rets_b[:min_len]
                mean_a = sum(a) / min_len
                mean_b = sum(b) / min_len

                cov = sum((a[k] - mean_a) * (b[k] - mean_b) for k in range(min_len)) / (min_len - 1)
                std_a = math.sqrt(sum((x - mean_a) ** 2 for x in a) / (min_len - 1))
                std_b = math.sqrt(sum((x - mean_b) ** 2 for x in b) / (min_len - 1))

                corr = cov / (std_a * std_b) if std_a > 0 and std_b > 0 else 0.0
                matrix[name_a][name_b] = round(corr, 4)

    return matrix
