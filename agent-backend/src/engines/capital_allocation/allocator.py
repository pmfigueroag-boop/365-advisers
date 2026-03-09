"""src/engines/capital_allocation/allocator.py — Allocation methods."""
from __future__ import annotations
import numpy as np
import logging
from src.engines.capital_allocation.models import (
    AllocationMethod, AllocationResult, StrategyBudget,
)

logger = logging.getLogger("365advisers.capital_allocation.allocator")


class CapitalAllocator:
    """Cross-strategy capital allocation using various methods."""

    @classmethod
    def allocate(
        cls, strategies: list[StrategyBudget], method: AllocationMethod = AllocationMethod.EQUAL,
        total_capital: float = 1_000_000.0,
    ) -> AllocationResult:
        if not strategies:
            return AllocationResult(method=method, total_capital=total_capital)

        dispatch = {
            AllocationMethod.EQUAL: cls._equal,
            AllocationMethod.RISK_PARITY: cls._risk_parity,
            AllocationMethod.INVERSE_VOL: cls._inverse_vol,
            AllocationMethod.RISK_BUDGET: cls._risk_budget,
            AllocationMethod.MOMENTUM_TILT: cls._momentum_tilt,
        }
        allocations = dispatch.get(method, cls._equal)(strategies)

        # Enforce max bounds and renormalise
        allocations = cls._enforce_bounds(strategies, allocations)

        return AllocationResult(
            method=method,
            allocations=allocations,
            total_capital=total_capital,
            analytics={"strategy_count": len(strategies), "hhi": cls._hhi(allocations)},
        )

    @staticmethod
    def _equal(strategies: list[StrategyBudget]) -> dict[str, float]:
        w = round(1.0 / len(strategies), 6)
        return {s.strategy_id: w for s in strategies}

    @staticmethod
    def _risk_parity(strategies: list[StrategyBudget]) -> dict[str, float]:
        """Inverse-volatility weighting (simple risk parity)."""
        vols = np.array([max(s.volatility, 0.001) for s in strategies])
        inv = 1.0 / vols
        weights = inv / inv.sum()
        return {s.strategy_id: round(float(w), 6) for s, w in zip(strategies, weights)}

    @staticmethod
    def _inverse_vol(strategies: list[StrategyBudget]) -> dict[str, float]:
        """Same as risk parity (inverse vol)."""
        vols = np.array([max(s.volatility, 0.001) for s in strategies])
        inv = 1.0 / vols
        weights = inv / inv.sum()
        return {s.strategy_id: round(float(w), 6) for s, w in zip(strategies, weights)}

    @staticmethod
    def _risk_budget(strategies: list[StrategyBudget]) -> dict[str, float]:
        """Allocate proportional to target risk budget (max_allocation as proxy)."""
        budgets = np.array([s.max_allocation for s in strategies])
        total = budgets.sum()
        if total == 0:
            return {s.strategy_id: 1.0 / len(strategies) for s in strategies}
        weights = budgets / total
        return {s.strategy_id: round(float(w), 6) for s, w in zip(strategies, weights)}

    @staticmethod
    def _momentum_tilt(strategies: list[StrategyBudget]) -> dict[str, float]:
        """Overweight strategies with positive recent returns."""
        returns = np.array([s.recent_return for s in strategies])
        # Shift all positive: exp(r) gives higher weight to winners
        exp_r = np.exp(returns)
        weights = exp_r / exp_r.sum()
        return {s.strategy_id: round(float(w), 6) for s, w in zip(strategies, weights)}

    @staticmethod
    def _enforce_bounds(strategies: list[StrategyBudget], alloc: dict[str, float]) -> dict[str, float]:
        for s in strategies:
            if alloc.get(s.strategy_id, 0) > s.max_allocation:
                alloc[s.strategy_id] = s.max_allocation
        total = sum(alloc.values())
        if total > 0:
            alloc = {k: round(v / total, 6) for k, v in alloc.items()}
        return alloc

    @staticmethod
    def _hhi(alloc: dict[str, float]) -> float:
        """Herfindahl-Hirschman Index (concentration measure)."""
        return round(sum(w ** 2 for w in alloc.values()), 4)
