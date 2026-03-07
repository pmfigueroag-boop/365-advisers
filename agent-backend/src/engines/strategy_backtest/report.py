"""
src/engines/strategy_backtest/report.py
─────────────────────────────────────────────────────────────────────────────
BacktestReport — structured report generation from strategy backtest results.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from .regime_analysis import RegimePerformance

logger = logging.getLogger("365advisers.strategy_backtest.report")


class BacktestReport:
    """Generate structured backtest reports."""

    @staticmethod
    def generate(backtest_result: dict) -> dict:
        """Generate a comprehensive report from a backtest result.

        Args:
            backtest_result: Output from StrategyBacktester.run()

        Returns:
            Formatted report with summary, metrics, and analysis.
        """
        metrics = backtest_result.get("metrics", {})
        equity_curve = backtest_result.get("equity_curve", [])
        trades = backtest_result.get("trades", [])

        # Regime analysis
        regime = RegimePerformance.analyze(equity_curve)

        # Trade analysis
        avg_turnover = 0.0
        if trades:
            avg_turnover = sum(t["turnover"] for t in trades) / len(trades)

        # Monthly returns approximation
        monthly_returns = _approximate_monthly_returns(equity_curve)

        return {
            "report_type": "strategy_backtest",
            "generated_at": datetime.now(timezone.utc).isoformat(),

            # Summary
            "summary": {
                "strategy_name": backtest_result.get("strategy_name", "unnamed"),
                "period": backtest_result.get("period", []),
                "initial_capital": backtest_result.get("initial_capital", 0),
                "final_value": backtest_result.get("final_value", 0),
                "total_return": backtest_result.get("total_return", 0),
                "total_cost": backtest_result.get("total_cost_usd", 0),
            },

            # Risk-adjusted metrics
            "metrics": metrics,

            # Trade analysis
            "trade_analysis": {
                "total_trades": len(trades),
                "avg_turnover": round(avg_turnover, 4),
                "total_cost_usd": backtest_result.get("total_cost_usd", 0),
            },

            # Regime breakdown
            "regime_analysis": regime,

            # Monthly returns
            "monthly_returns": monthly_returns,
        }

    @staticmethod
    def generate_comparison_report(results: list[dict]) -> dict:
        """Compare multiple strategy backtest results side by side.

        Args:
            results: List of backtest results from StrategyBacktester.run()

        Returns:
            Comparison table with key metrics per strategy.
        """
        strategies = []
        for r in results:
            m = r.get("metrics", {})
            strategies.append({
                "name": r.get("strategy_name", "unnamed"),
                "total_return": r.get("total_return", 0),
                "sharpe": m.get("sharpe_ratio", 0),
                "sortino": m.get("sortino_ratio", 0),
                "max_drawdown": m.get("max_drawdown", 0),
                "calmar": m.get("calmar_ratio", 0),
                "alpha": m.get("alpha"),
                "win_rate": m.get("win_rate", 0),
                "total_cost": r.get("total_cost_usd", 0),
            })

        # Rank by Sharpe
        strategies.sort(key=lambda s: s["sharpe"], reverse=True)

        return {
            "report_type": "strategy_comparison",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "strategies": strategies,
            "best_sharpe": strategies[0]["name"] if strategies else None,
            "best_return": max(strategies, key=lambda s: s["total_return"])["name"] if strategies else None,
        }


def _approximate_monthly_returns(equity_curve: list[dict]) -> list[dict]:
    """Approximate monthly returns from equity curve."""
    if not equity_curve:
        return []

    monthly: dict[str, list] = {}
    for entry in equity_curve:
        month = entry["date"][:7]  # YYYY-MM
        monthly.setdefault(month, []).append(entry["portfolio_value"])

    returns = []
    months = sorted(monthly.keys())
    for i in range(1, len(months)):
        prev_vals = monthly[months[i - 1]]
        curr_vals = monthly[months[i]]
        if prev_vals and curr_vals and prev_vals[-1] > 0:
            ret = (curr_vals[-1] - prev_vals[-1]) / prev_vals[-1]
            returns.append({"month": months[i], "return": round(ret, 4)})

    return returns
