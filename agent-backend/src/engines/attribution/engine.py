"""
src/engines/attribution/engine.py — Attribution Engine orchestrator.
"""
from __future__ import annotations
import logging
from src.engines.attribution.models import BrinsonResult, AttributionPeriod
from src.engines.attribution.brinson import BrinsonFachler

logger = logging.getLogger("365advisers.attribution.engine")


class AttributionEngine:
    """Unified attribution: single-period and multi-period."""

    @classmethod
    def single_period(
        cls,
        portfolio_weights: dict[str, float],
        benchmark_weights: dict[str, float],
        portfolio_returns: dict[str, float],
        benchmark_returns: dict[str, float],
    ) -> BrinsonResult:
        return BrinsonFachler.attribute(
            portfolio_weights, benchmark_weights,
            portfolio_returns, benchmark_returns,
        )

    @classmethod
    def multi_period(
        cls,
        periods: list[dict],
    ) -> list[AttributionPeriod]:
        """
        Multi-period attribution.

        periods: list of {
            "period": "2024-Q1",
            "portfolio_weights": {...},
            "benchmark_weights": {...},
            "portfolio_returns": {...},
            "benchmark_returns": {...},
        }
        """
        results = []
        for p in periods:
            result = BrinsonFachler.attribute(
                p["portfolio_weights"], p["benchmark_weights"],
                p["portfolio_returns"], p["benchmark_returns"],
            )
            results.append(AttributionPeriod(period=p.get("period", ""), result=result))
        return results

    @classmethod
    def cumulative_attribution(cls, periods: list[AttributionPeriod]) -> dict:
        """Aggregate multi-period attribution."""
        total_alloc = sum(p.result.total_allocation for p in periods)
        total_select = sum(p.result.total_selection for p in periods)
        total_inter = sum(p.result.total_interaction for p in periods)
        cum_active = sum(p.result.active_return for p in periods)

        return {
            "cumulative_active_return": round(cum_active, 6),
            "cumulative_allocation": round(total_alloc, 6),
            "cumulative_selection": round(total_select, 6),
            "cumulative_interaction": round(total_inter, 6),
            "num_periods": len(periods),
        }
