"""
src/engines/portfolio/multi_strategy.py
--------------------------------------------------------------------------
Multi-Strategy Capital Allocation — meta-optimizer distributing capital
across competing strategies.

Methods:
  1. Equal weight (1/N)
  2. Risk parity (weight inversely proportional to volatility)
  3. Momentum-based (overweight recent top performers)
  4. Kelly-criterion (optimal growth based on edge + odds)

Usage::

    allocator = MultiStrategyAllocator()
    allocator.add_strategy("momentum", sharpe=1.2, vol=0.15, returns=[...])
    allocator.add_strategy("value", sharpe=0.8, vol=0.10, returns=[...])
    allocation = allocator.allocate(method="risk_parity", total_capital=1_000_000)
"""

from __future__ import annotations

import logging
import math

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.portfolio.multi_strategy")


# ── Contracts ────────────────────────────────────────────────────────────────

class StrategyProfile(BaseModel):
    """Profile of a single strategy."""
    name: str
    sharpe: float = 0.0
    annualized_return: float = 0.0
    annualized_vol: float = 0.0
    max_drawdown: float = 0.0
    recent_returns: list[float] = Field(default_factory=list)
    capacity: float = Field(
        float("inf"), description="Max capital (USD) this strategy can absorb",
    )
    is_active: bool = True


class StrategyAllocation(BaseModel):
    """Allocation result for one strategy."""
    name: str
    weight: float = 0.0
    capital: float = 0.0
    rationale: str = ""


class AllocationResult(BaseModel):
    """Complete allocation output."""
    method: str = ""
    total_capital: float = 0.0
    allocations: list[StrategyAllocation] = Field(default_factory=list)
    expected_portfolio_sharpe: float = 0.0
    expected_portfolio_vol: float = 0.0
    diversification_ratio: float = 0.0


# ── Engine ───────────────────────────────────────────────────────────────────

class MultiStrategyAllocator:
    """
    Allocates capital across multiple strategies.

    Methods:
      - equal_weight: 1/N
      - risk_parity: weight ∝ 1/σ
      - momentum: overweight recent winners
      - kelly: f* = μ/σ² (capped)
    """

    def __init__(self) -> None:
        self._strategies: dict[str, StrategyProfile] = {}

    def add_strategy(
        self,
        name: str,
        sharpe: float = 0.0,
        annualized_return: float = 0.0,
        annualized_vol: float = 0.01,
        max_drawdown: float = 0.0,
        recent_returns: list[float] | None = None,
        capacity: float = float("inf"),
    ) -> StrategyProfile:
        """Register a strategy."""
        profile = StrategyProfile(
            name=name,
            sharpe=sharpe,
            annualized_return=annualized_return,
            annualized_vol=max(annualized_vol, 0.001),
            max_drawdown=max_drawdown,
            recent_returns=recent_returns or [],
            capacity=capacity,
        )
        self._strategies[name] = profile
        return profile

    def allocate(
        self,
        method: str = "risk_parity",
        total_capital: float = 1_000_000.0,
    ) -> AllocationResult:
        """
        Compute capital allocation across strategies.

        Parameters
        ----------
        method : str
            "equal_weight", "risk_parity", "momentum", "kelly".
        total_capital : float
            Total capital to allocate.
        """
        active = [s for s in self._strategies.values() if s.is_active]

        if not active:
            return AllocationResult(method=method, total_capital=total_capital)

        if method == "equal_weight":
            weights = self._equal_weight(active)
        elif method == "risk_parity":
            weights = self._risk_parity(active)
        elif method == "momentum":
            weights = self._momentum(active)
        elif method == "kelly":
            weights = self._kelly(active)
        else:
            weights = self._equal_weight(active)

        # Apply capacity constraints
        weights = self._apply_capacity(weights, active, total_capital)

        # Build result
        allocations = []
        for s in active:
            w = weights.get(s.name, 0.0)
            allocations.append(StrategyAllocation(
                name=s.name,
                weight=round(w, 4),
                capital=round(w * total_capital, 2),
                rationale=f"{method}: Sharpe={s.sharpe:.2f}, Vol={s.annualized_vol:.2%}",
            ))

        # Portfolio-level metrics
        port_vol = self._portfolio_vol(active, weights)
        port_ret = sum(s.annualized_return * weights.get(s.name, 0) for s in active)
        port_sharpe = port_ret / port_vol if port_vol > 0 else 0.0

        # Diversification ratio
        weighted_vol = sum(s.annualized_vol * weights.get(s.name, 0) for s in active)
        div_ratio = weighted_vol / port_vol if port_vol > 0 else 1.0

        logger.info(
            "MULTI-STRATEGY: %s allocation across %d strategies, "
            "expected Sharpe=%.2f, vol=%.2f%%",
            method, len(active), port_sharpe, port_vol * 100,
        )

        return AllocationResult(
            method=method,
            total_capital=total_capital,
            allocations=allocations,
            expected_portfolio_sharpe=round(port_sharpe, 4),
            expected_portfolio_vol=round(port_vol, 4),
            diversification_ratio=round(div_ratio, 4),
        )

    def _equal_weight(self, strategies: list[StrategyProfile]) -> dict[str, float]:
        n = len(strategies)
        return {s.name: 1.0 / n for s in strategies}

    def _risk_parity(self, strategies: list[StrategyProfile]) -> dict[str, float]:
        """Weight inversely proportional to volatility."""
        inv_vols = {s.name: 1.0 / s.annualized_vol for s in strategies}
        total = sum(inv_vols.values())
        return {name: v / total for name, v in inv_vols.items()}

    def _momentum(self, strategies: list[StrategyProfile]) -> dict[str, float]:
        """Overweight recent top performers (last 60 days)."""
        scores: dict[str, float] = {}
        for s in strategies:
            if s.recent_returns:
                # Use recent cumulative return as score
                cum = sum(s.recent_returns[-60:])
                scores[s.name] = max(cum, 0.01)  # Floor at 0.01
            else:
                scores[s.name] = max(s.sharpe, 0.01)

        total = sum(scores.values())
        return {name: v / total for name, v in scores.items()}

    def _kelly(self, strategies: list[StrategyProfile]) -> dict[str, float]:
        """Kelly criterion: f* = μ/σ² (capped at 25% per strategy)."""
        raw: dict[str, float] = {}
        for s in strategies:
            var = s.annualized_vol ** 2
            if var > 0:
                f_star = s.annualized_return / var
                f_star = max(0.0, min(f_star, 0.25))  # Cap at 25%
            else:
                f_star = 0.0
            raw[s.name] = f_star

        total = sum(raw.values()) or 1.0
        return {name: v / total for name, v in raw.items()}

    def _apply_capacity(
        self,
        weights: dict[str, float],
        strategies: list[StrategyProfile],
        total_capital: float,
    ) -> dict[str, float]:
        """Redistribute weight from capacity-constrained strategies."""
        adjusted = dict(weights)
        overflow = 0.0

        for s in strategies:
            if s.capacity < float("inf"):
                max_weight = s.capacity / total_capital
                if adjusted[s.name] > max_weight:
                    overflow += adjusted[s.name] - max_weight
                    adjusted[s.name] = max_weight

        if overflow > 0:
            # Redistribute overflow to unconstrained strategies
            unconstrained = [
                s for s in strategies
                if s.capacity >= adjusted[s.name] * total_capital * 1.5
            ]
            if unconstrained:
                share = overflow / len(unconstrained)
                for s in unconstrained:
                    adjusted[s.name] += share

        # Re-normalize
        total = sum(adjusted.values()) or 1.0
        return {name: w / total for name, w in adjusted.items()}

    def _portfolio_vol(
        self,
        strategies: list[StrategyProfile],
        weights: dict[str, float],
    ) -> float:
        """Estimate portfolio vol (assumes zero correlation for simplicity)."""
        var = sum(
            (weights.get(s.name, 0) * s.annualized_vol) ** 2
            for s in strategies
        )
        return math.sqrt(var)

    @property
    def strategy_count(self) -> int:
        return len(self._strategies)
