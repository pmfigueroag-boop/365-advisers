"""
src/engines/strategy_backtest/walk_forward_strategy.py
─────────────────────────────────────────────────────────────────────────────
WalkForwardStrategyValidator — walk-forward validation at STRATEGY level.

Splits history into train/test folds and measures whether the strategy's
edge persists out-of-sample.
"""

from __future__ import annotations

import logging
from typing import Any

from .engine import StrategyBacktester
from .metrics import StrategyMetrics

logger = logging.getLogger("365advisers.strategy_backtest.walk_forward")


class WalkForwardStrategyValidator:
    """Walk-forward validation for complete strategies."""

    @staticmethod
    def validate(
        strategy_config: dict,
        positions_by_date: dict[str, list[dict]],
        prices: dict[str, dict[str, float]],
        n_folds: int = 5,
        train_pct: float = 0.70,
        cost_per_trade_bps: float = 5.0,
        initial_capital: float = 1_000_000.0,
    ) -> dict:
        """Run walk-forward validation.

        Splits dates into overlapping train/test folds.
        Runs backtest on each test fold and measures consistency.

        Args:
            strategy_config: Strategy definition
            positions_by_date: Full historical position targets
            prices: Full price matrix
            n_folds: Number of walk-forward folds
            train_pct: Fraction of data for training in each fold
            cost_per_trade_bps: Transaction cost assumption
            initial_capital: Starting capital per fold

        Returns:
            Walk-forward results with per-fold metrics and consistency score.
        """
        dates = sorted(positions_by_date.keys())
        if len(dates) < 20:
            return {"error": "Insufficient dates for walk-forward", "date_count": len(dates)}

        n_total = len(dates)
        fold_results = []

        for fold_idx in range(n_folds):
            # Expanding window: each fold uses progressively more training data
            train_end_idx = int(n_total * (train_pct + (1 - train_pct) * fold_idx / max(n_folds - 1, 1)))
            test_start_idx = train_end_idx
            test_end_idx = min(n_total, test_start_idx + int(n_total * (1 - train_pct) / n_folds))

            if test_start_idx >= n_total or test_end_idx <= test_start_idx:
                continue

            # Extract test dates
            test_dates = dates[test_start_idx:test_end_idx]
            test_positions = {d: positions_by_date[d] for d in test_dates if d in positions_by_date}

            if len(test_positions) < 3:
                continue

            # Run backtest on test fold
            result = StrategyBacktester.run(
                strategy_config=strategy_config,
                positions_by_date=test_positions,
                prices=prices,
                cost_per_trade_bps=cost_per_trade_bps,
                initial_capital=initial_capital,
            )

            metrics = result.get("metrics", {})
            fold_results.append({
                "fold": fold_idx + 1,
                "period": [test_dates[0], test_dates[-1]],
                "test_days": len(test_dates),
                "total_return": metrics.get("total_return", 0),
                "sharpe_ratio": metrics.get("sharpe_ratio", 0),
                "max_drawdown": metrics.get("max_drawdown", 0),
                "win_rate": metrics.get("win_rate", 0),
            })

        if not fold_results:
            return {"error": "No valid folds generated", "n_folds": n_folds}

        # Aggregate metrics
        sharpes = [f["sharpe_ratio"] for f in fold_results]
        returns = [f["total_return"] for f in fold_results]
        drawdowns = [f["max_drawdown"] for f in fold_results]

        avg_sharpe = sum(sharpes) / len(sharpes)
        avg_return = sum(returns) / len(returns)

        # Consistency: fraction of folds with positive Sharpe
        profitable_folds = sum(1 for s in sharpes if s > 0)
        consistency = profitable_folds / len(fold_results)

        # IS/OOS stability: std of Sharpe across folds
        import math
        sharpe_std = math.sqrt(sum((s - avg_sharpe)**2 for s in sharpes) / max(len(sharpes) - 1, 1))
        stability = max(0, 1 - sharpe_std / max(abs(avg_sharpe), 0.01))

        return {
            "n_folds": len(fold_results),
            "folds": fold_results,
            "aggregate": {
                "avg_sharpe": round(avg_sharpe, 4),
                "avg_return": round(avg_return, 4),
                "avg_drawdown": round(sum(drawdowns) / len(drawdowns), 4),
                "sharpe_std": round(sharpe_std, 4),
                "consistency": round(consistency, 4),
                "stability_score": round(min(stability, 1.0), 4),
                "profitable_folds": profitable_folds,
            },
            "verdict": _classify_wf_result(consistency, avg_sharpe, stability),
        }


def _classify_wf_result(consistency: float, avg_sharpe: float, stability: float) -> str:
    """Classify walk-forward result."""
    if consistency >= 0.8 and avg_sharpe > 0.5 and stability > 0.6:
        return "robust"
    elif consistency >= 0.6 and avg_sharpe > 0:
        return "acceptable"
    elif consistency >= 0.4:
        return "marginal"
    else:
        return "overfit"
