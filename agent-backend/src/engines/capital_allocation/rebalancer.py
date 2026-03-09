"""src/engines/capital_allocation/rebalancer.py — Drift detection."""
from __future__ import annotations
from src.engines.capital_allocation.models import (
    StrategyBudget, DriftReport, DriftEntry, RebalanceTrade,
)


class DriftDetector:
    """Detect allocation drift and compute rebalance trades."""

    @classmethod
    def detect_drift(
        cls, strategies: list[StrategyBudget], threshold: float = 0.05,
    ) -> DriftReport:
        entries = []
        max_drift = 0.0
        for s in strategies:
            drift = abs(s.current_allocation - s.target_allocation)
            entries.append(DriftEntry(
                strategy_id=s.strategy_id,
                current_weight=s.current_allocation,
                target_weight=s.target_allocation,
                drift_pct=round(drift, 4),
                needs_rebalance=drift > threshold,
            ))
            max_drift = max(max_drift, drift)

        return DriftReport(
            entries=entries,
            max_drift=round(max_drift, 4),
            rebalance_needed=max_drift > threshold,
            threshold=threshold,
        )

    @classmethod
    def compute_rebalance_trades(
        cls, strategies: list[StrategyBudget],
    ) -> list[RebalanceTrade]:
        trades = []
        for s in strategies:
            diff = s.target_allocation - s.current_allocation
            if abs(diff) > 0.001:
                trades.append(RebalanceTrade(
                    strategy_id=s.strategy_id,
                    direction="increase" if diff > 0 else "decrease",
                    amount_pct=round(abs(diff), 4),
                ))
        return trades
