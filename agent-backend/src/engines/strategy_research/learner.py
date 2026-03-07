"""
src/engines/strategy_research/learner.py
─────────────────────────────────────────────────────────────────────────────
StrategyLearner — learn which strategies perform best per context.

Uses historical backtest results and regime labels to build a
strategy-regime performance mapping for adaptive allocation.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger("365advisers.strategy_research.learner")


class StrategyLearner:
    """Learn strategy-regime performance mappings."""

    def __init__(self):
        self._regime_performance: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )  # {regime: {strategy_id: [sharpe_values]}}
        self._global_performance: dict[str, list[float]] = defaultdict(list)

    def fit(
        self,
        backtest_results: list[dict],
        regime_analyses: dict[str, dict] | None = None,
    ) -> dict:
        """Fit learner from backtest results + regime breakdowns.

        Args:
            backtest_results: List of backtest result dicts
            regime_analyses: Optional {strategy_name: regime_analysis_result}

        Returns:
            Learned mapping summary.
        """
        for result in backtest_results:
            strategy_name = result.get("strategy_name", "unnamed")
            metrics = result.get("metrics", {})
            sharpe = metrics.get("sharpe_ratio", 0)
            self._global_performance[strategy_name].append(sharpe)

        # If regime analysis available, build per-regime map
        if regime_analyses:
            for strategy_name, ra in regime_analyses.items():
                regimes = ra.get("regimes", {})
                for regime, stats in regimes.items():
                    sharpe = stats.get("sharpe_ratio", 0)
                    self._regime_performance[regime][strategy_name].append(sharpe)

        return self._build_summary()

    def recommend(
        self,
        current_regime: str,
        top_n: int = 3,
    ) -> list[dict]:
        """Recommend best strategies for current regime.

        Args:
            current_regime: Current market regime label
            top_n: Number of recommendations

        Returns:
            Ranked list of {strategy, avg_sharpe, confidence, regime_edge}
        """
        regime_data = self._regime_performance.get(current_regime, {})

        if not regime_data:
            # Fall back to global performance
            return self._recommend_from_global(top_n)

        # Compute average Sharpe per strategy in this regime
        scores = []
        for strategy, sharpes in regime_data.items():
            avg_sharpe = sum(sharpes) / len(sharpes) if sharpes else 0
            std_sharpe = _std(sharpes) if len(sharpes) > 1 else float("inf")
            confidence = 1.0 - min(1.0, std_sharpe / max(abs(avg_sharpe), 0.01))

            # Regime edge: how much better vs global
            global_sharpes = self._global_performance.get(strategy, [])
            global_avg = sum(global_sharpes) / len(global_sharpes) if global_sharpes else 0
            regime_edge = avg_sharpe - global_avg

            scores.append({
                "strategy": strategy,
                "avg_sharpe": round(avg_sharpe, 4),
                "observations": len(sharpes),
                "confidence": round(max(0, confidence), 4),
                "regime_edge": round(regime_edge, 4),
            })

        scores.sort(key=lambda s: s["avg_sharpe"], reverse=True)
        return scores[:top_n]

    def update(
        self,
        strategy_id: str,
        regime: str,
        sharpe_observation: float,
    ) -> None:
        """Update learner with a new observation (online learning)."""
        self._regime_performance[regime][strategy_id].append(sharpe_observation)
        self._global_performance[strategy_id].append(sharpe_observation)
        logger.info(
            "Updated learner: %s in %s → Sharpe %.4f",
            strategy_id, regime, sharpe_observation,
        )

    def get_regime_map(self) -> dict:
        """Get the full regime → best strategy mapping."""
        mapping = {}
        for regime, strategies in self._regime_performance.items():
            best = None
            best_sharpe = -float("inf")
            for strategy, sharpes in strategies.items():
                avg = sum(sharpes) / len(sharpes) if sharpes else 0
                if avg > best_sharpe:
                    best_sharpe = avg
                    best = strategy
            mapping[regime] = {
                "best_strategy": best,
                "avg_sharpe": round(best_sharpe, 4),
                "candidates": len(strategies),
            }
        return mapping

    def _recommend_from_global(self, top_n: int) -> list[dict]:
        """Fallback recommendation from global performance."""
        scores = []
        for strategy, sharpes in self._global_performance.items():
            avg = sum(sharpes) / len(sharpes) if sharpes else 0
            scores.append({
                "strategy": strategy,
                "avg_sharpe": round(avg, 4),
                "observations": len(sharpes),
                "confidence": 0.5,
                "regime_edge": 0.0,
                "note": "global fallback",
            })
        scores.sort(key=lambda s: s["avg_sharpe"], reverse=True)
        return scores[:top_n]

    def _build_summary(self) -> dict:
        """Build a summary of learned mappings."""
        return {
            "regimes_learned": len(self._regime_performance),
            "strategies_tracked": len(self._global_performance),
            "regime_map": self.get_regime_map(),
            "total_observations": sum(
                len(v) for v in self._global_performance.values()
            ),
            "fitted_at": datetime.now(timezone.utc).isoformat(),
        }


def _std(values: list[float]) -> float:
    """Standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
