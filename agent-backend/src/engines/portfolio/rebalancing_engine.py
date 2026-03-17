"""
src/engines/portfolio/rebalancing_engine.py
--------------------------------------------------------------------------
Rebalancing Engine — turnover-aware portfolio transitions.

Takes current holdings → target weights and produces a transition plan
that respects:
  - Turnover constraints (max % changed per rebalance)
  - Minimum trade thresholds (don't trade if Δweight < threshold)
  - Partial transitions (gradual move to target over N rebalances)
  - Transaction cost awareness (skip trade if cost > expected benefit)

This is the missing link between "optimizer says 8% AAPL" and actually
changing the portfolio.

Usage::

    engine = RebalancingEngine()
    plan = engine.compute_transition(
        current={"AAPL": 0.10, "MSFT": 0.15, "GOOGL": 0.05},
        target={"AAPL": 0.08, "MSFT": 0.20, "GOOGL": 0.00, "AMZN": 0.12},
    )
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from src.engines.portfolio.transaction_costs import (
    TransactionCostModel,
    CostModelConfig,
)

logger = logging.getLogger("365advisers.portfolio.rebalancing")


# ── Contracts ────────────────────────────────────────────────────────────────

class RebalanceConfig(BaseModel):
    """Configuration for rebalancing."""
    max_turnover: float = Field(
        0.30, ge=0.0, le=1.0,
        description="Max one-way turnover per rebalance (0.30 = 30%)",
    )
    min_trade_weight: float = Field(
        0.005, ge=0.0,
        description="Minimum weight change to execute a trade (skip dust)",
    )
    transition_periods: int = Field(
        1, ge=1,
        description="Number of periods to transition (1 = immediate, 3 = gradual over 3 rebalances)",
    )
    cost_threshold_bps: float = Field(
        500.0, ge=0.0,
        description="Skip trade if cost > this many bps of trade value",
    )
    portfolio_value: float = Field(
        1_000_000.0, gt=0.0,
        description="Total portfolio value in USD",
    )


class TradeOrder(BaseModel):
    """A single trade order to execute."""
    ticker: str
    direction: str = ""  # "BUY" or "SELL"
    current_weight: float = 0.0
    target_weight: float = 0.0
    trade_weight: float = 0.0
    trade_value: float = 0.0
    estimated_cost: float = 0.0
    estimated_cost_bps: float = 0.0
    is_new_position: bool = False
    is_exit: bool = False
    is_dust: bool = False
    is_skipped: bool = False
    skip_reason: str = ""


class TransitionPlan(BaseModel):
    """Full rebalance transition plan."""
    orders: list[TradeOrder] = Field(default_factory=list)
    executable_orders: list[TradeOrder] = Field(default_factory=list)
    skipped_orders: list[TradeOrder] = Field(default_factory=list)

    # Portfolio state
    current_weights: dict[str, float] = Field(default_factory=dict)
    target_weights: dict[str, float] = Field(default_factory=dict)
    post_rebalance_weights: dict[str, float] = Field(default_factory=dict)

    # Metrics
    total_turnover: float = 0.0
    total_trades: int = 0
    total_cost: float = 0.0
    total_cost_bps: float = 0.0
    positions_added: int = 0
    positions_removed: int = 0
    transition_completion: float = Field(
        0.0, description="1.0 = fully transitioned, 0.5 = halfway",
    )

    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Engine ───────────────────────────────────────────────────────────────────

class RebalancingEngine:
    """
    Computes turnover-aware portfolio transitions.

    Handles:
    - Turnover caps
    - Minimum trade thresholds (skip dust trades)
    - Gradual transitions (multi-period)
    - Cost-aware trade filtering
    """

    def __init__(
        self,
        config: RebalanceConfig | None = None,
        cost_model: TransactionCostModel | None = None,
    ) -> None:
        self.config = config or RebalanceConfig()
        self.cost_model = cost_model or TransactionCostModel()

    def compute_transition(
        self,
        current: dict[str, float],
        target: dict[str, float],
    ) -> TransitionPlan:
        """
        Compute a transition plan from current to target weights.

        Parameters
        ----------
        current : dict[str, float]
            Current portfolio weights {ticker: weight}.
        target : dict[str, float]
            Target portfolio weights {ticker: weight}.

        Returns
        -------
        TransitionPlan
            Detailed plan with orders, costs, and post-rebalance state.
        """
        all_tickers = sorted(set(current) | set(target))

        # Step 1: compute raw deltas
        raw_orders: list[TradeOrder] = []
        for ticker in all_tickers:
            cur_w = current.get(ticker, 0.0)
            tgt_w = target.get(ticker, 0.0)
            delta = tgt_w - cur_w

            if abs(delta) < 1e-6:
                continue

            trade_value = abs(delta) * self.config.portfolio_value
            cost_est = self.cost_model.estimate_trade(ticker, trade_value)

            order = TradeOrder(
                ticker=ticker,
                direction="BUY" if delta > 0 else "SELL",
                current_weight=round(cur_w, 6),
                target_weight=round(tgt_w, 6),
                trade_weight=round(abs(delta), 6),
                trade_value=round(trade_value, 2),
                estimated_cost=round(cost_est.total_cost, 4),
                estimated_cost_bps=round(cost_est.cost_bps, 2),
                is_new_position=cur_w < 0.001 and tgt_w >= 0.001,
                is_exit=tgt_w < 0.001 and cur_w >= 0.001,
                is_dust=abs(delta) < self.config.min_trade_weight,
            )

            # Check if cost exceeds threshold
            if cost_est.cost_bps > self.config.cost_threshold_bps:
                order.is_skipped = True
                order.skip_reason = (
                    f"Cost {cost_est.cost_bps:.0f}bps > threshold "
                    f"{self.config.cost_threshold_bps:.0f}bps"
                )
            elif order.is_dust and not order.is_exit:
                order.is_skipped = True
                order.skip_reason = (
                    f"Dust trade: Δ={abs(delta):.4f} < min {self.config.min_trade_weight}"
                )

            raw_orders.append(order)

        # Step 2: apply transition periods (gradual transition)
        if self.config.transition_periods > 1:
            fraction = 1.0 / self.config.transition_periods
            for order in raw_orders:
                if not order.is_skipped:
                    order.trade_weight = round(order.trade_weight * fraction, 6)
                    order.trade_value = round(order.trade_value * fraction, 2)

        # Step 3: apply turnover cap
        executable, skipped = self._apply_turnover_cap(raw_orders)

        # Step 4: compute post-rebalance weights
        post = dict(current)
        for order in executable:
            sign = 1.0 if order.direction == "BUY" else -1.0
            post[order.ticker] = post.get(order.ticker, 0.0) + sign * order.trade_weight

        # Clean tiny weights
        post = {t: round(max(w, 0.0), 6) for t, w in post.items() if w > 0.0001}

        # Metrics
        total_turnover = sum(o.trade_weight for o in executable) / 2
        total_cost = sum(o.estimated_cost for o in executable)
        total_cost_bps = (
            (total_cost / self.config.portfolio_value) * 10_000
            if self.config.portfolio_value > 0 else 0.0
        )

        # Transition completion
        all_skipped = executable + skipped
        total_delta = sum(o.trade_weight for o in raw_orders if not o.is_dust)
        executed_delta = sum(o.trade_weight for o in executable)
        completion = executed_delta / total_delta if total_delta > 0 else 1.0

        plan = TransitionPlan(
            orders=raw_orders,
            executable_orders=executable,
            skipped_orders=skipped,
            current_weights=current,
            target_weights=target,
            post_rebalance_weights=post,
            total_turnover=round(total_turnover, 4),
            total_trades=len(executable),
            total_cost=round(total_cost, 4),
            total_cost_bps=round(total_cost_bps, 2),
            positions_added=sum(1 for o in executable if o.is_new_position),
            positions_removed=sum(1 for o in executable if o.is_exit),
            transition_completion=round(min(completion, 1.0), 4),
        )

        logger.info(
            "REBALANCE: %d orders → %d executable, turnover=%.1f%%, "
            "cost=%.2fbps, completion=%.0f%%",
            len(raw_orders), len(executable),
            total_turnover * 100, total_cost_bps,
            completion * 100,
        )

        return plan

    def _apply_turnover_cap(
        self,
        orders: list[TradeOrder],
    ) -> tuple[list[TradeOrder], list[TradeOrder]]:
        """Enforce max turnover by prioritizing larger trades."""
        # Separate executable from already-skipped
        candidates = [o for o in orders if not o.is_skipped]
        already_skipped = [o for o in orders if o.is_skipped]

        # Sort by trade size (largest first — most impactful)
        candidates.sort(key=lambda o: o.trade_weight, reverse=True)

        executable: list[TradeOrder] = []
        cumulative_turnover = 0.0
        overflow: list[TradeOrder] = []

        for order in candidates:
            if cumulative_turnover + order.trade_weight / 2 <= self.config.max_turnover:
                executable.append(order)
                cumulative_turnover += order.trade_weight / 2
            else:
                order.is_skipped = True
                order.skip_reason = (
                    f"Turnover cap: would exceed {self.config.max_turnover:.0%}"
                )
                overflow.append(order)

        return executable, already_skipped + overflow
