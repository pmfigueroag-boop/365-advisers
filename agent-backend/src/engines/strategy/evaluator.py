"""
src/engines/strategy/evaluator.py
─────────────────────────────────────────────────────────────────────────────
StrategyEvaluator — Evaluates how a strategy would have performed
given historical data from the scorecards and shadow portfolios.
"""

from __future__ import annotations

import logging

from .definition import StrategyDefinition
from .filter import StrategyFilter

logger = logging.getLogger("365advisers.strategy.evaluator")


class StrategyEvaluator:
    """Evaluates strategy performance using historical scorecard data."""

    def __init__(self) -> None:
        self._definitions = StrategyDefinition()
        self._filter = StrategyFilter()

    def evaluate_strategy(
        self,
        strategy_id: str,
        opportunities: list[dict],
    ) -> dict:
        """Evaluate a strategy against a set of opportunities.

        Returns the filtered opportunity set along with stats.
        """
        strategy = self._definitions.get(strategy_id)
        if not strategy:
            return {"error": "Strategy not found"}

        filtered = self._filter.apply(opportunities, strategy.config)

        # Compute basic stats
        n = len(filtered)
        avg_case = (
            sum(o.get("case_score", 0) for o in filtered) / n if n > 0 else 0
        )
        avg_uos = (
            sum(o.get("uos", 0) for o in filtered) / n if n > 0 else 0
        )

        return {
            "strategy_id": strategy_id,
            "strategy_name": strategy.name,
            "total_opportunities": len(opportunities),
            "filtered_count": n,
            "pass_rate": round(n / max(len(opportunities), 1), 4),
            "avg_case_score": round(avg_case, 2),
            "avg_uos": round(avg_uos, 4),
            "filtered_tickers": [o.get("ticker", "") for o in filtered],
        }
