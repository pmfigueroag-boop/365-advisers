"""src/engines/capital_allocation/engine.py — Capital allocation orchestrator."""
from __future__ import annotations
from src.engines.capital_allocation.models import AllocationMethod, StrategyBudget, AllocationResult, DriftReport
from src.engines.capital_allocation.allocator import CapitalAllocator
from src.engines.capital_allocation.rebalancer import DriftDetector


class CapitalAllocationEngine:
    """Orchestrate allocation + drift detection + rebalancing."""

    @classmethod
    def allocate(cls, strategies: list[StrategyBudget], method: AllocationMethod = AllocationMethod.EQUAL,
                 total_capital: float = 1_000_000.0) -> AllocationResult:
        result = CapitalAllocator.allocate(strategies, method, total_capital)
        # Update target allocations on strategies
        for s in strategies:
            s.target_allocation = result.allocations.get(s.strategy_id, 0)
        return result

    @classmethod
    def check_drift(cls, strategies: list[StrategyBudget], threshold: float = 0.05) -> DriftReport:
        return DriftDetector.detect_drift(strategies, threshold)

    @classmethod
    def rebalance(cls, strategies: list[StrategyBudget]) -> dict:
        trades = DriftDetector.compute_rebalance_trades(strategies)
        return {"trades": [t.model_dump() for t in trades], "count": len(trades)}
