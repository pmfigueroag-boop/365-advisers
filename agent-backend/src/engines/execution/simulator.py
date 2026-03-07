"""
src/engines/execution/simulator.py
─────────────────────────────────────────────────────────────────────────────
ExecutionSimulator — Applies realistic execution costs to theoretical
returns, combining slippage, spread, volume participation, and latency.
"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger("365advisers.execution.simulator")


class ExecutionSimulator:
    """Simulates realistic execution for backtest return adjustment.

    Execution Cost = Slippage + Spread + Market Impact

    Slippage = base_bps + volume_factor × (order_size / ADV)
    Spread   = half_spread_bps  (one-way cost)
    Impact   = k × σ × √(Q/V)  (Almgren-Chriss)
    """

    def __init__(
        self,
        base_slippage_bps: float = 2.0,
        volume_slippage_factor: float = 10.0,
        impact_k: float = 0.314,
        default_spread_bps: float = 5.0,
        max_participation_rate: float = 0.05,
        latency_days: int = 0,
    ) -> None:
        self.base_slippage_bps = base_slippage_bps
        self.volume_slippage_factor = volume_slippage_factor
        self.impact_k = impact_k
        self.default_spread_bps = default_spread_bps
        self.max_participation_rate = max_participation_rate
        self.latency_days = latency_days

    def simulate_execution(
        self,
        order_value_usd: float,
        price: float,
        adv: float,
        daily_volatility: float = 0.02,
        spread_bps: float | None = None,
    ) -> dict:
        """Simulate execution costs for a single order.

        Args:
            order_value_usd: Dollar value of the order.
            price: Current stock price.
            adv: Average daily volume (shares).
            daily_volatility: Daily return volatility.
            spread_bps: Actual bid-ask spread; uses default if None.

        Returns:
            Dict with cost breakdown in bps and $ terms.
        """
        if price <= 0 or adv <= 0:
            return {"error": "Invalid price or ADV", "total_cost_bps": 0}

        order_shares = order_value_usd / price
        participation = order_shares / adv

        # Cap participation
        if participation > self.max_participation_rate:
            logger.warning(
                "Participation %.2f%% exceeds limit %.2f%%",
                participation * 100,
                self.max_participation_rate * 100,
            )

        # 1. Slippage
        slippage_bps = (
            self.base_slippage_bps
            + self.volume_slippage_factor * participation
        )

        # 2. Spread (one-way)
        spread = spread_bps if spread_bps is not None else self.default_spread_bps
        half_spread = spread / 2

        # 3. Market impact (Almgren-Chriss)
        impact_bps = (
            self.impact_k * daily_volatility * math.sqrt(participation) * 10000
        )

        total_bps = slippage_bps + half_spread + impact_bps
        total_usd = order_value_usd * total_bps / 10000

        return {
            "order_value_usd": round(order_value_usd, 2),
            "order_shares": round(order_shares),
            "participation_rate": round(participation, 6),
            "slippage_bps": round(slippage_bps, 2),
            "spread_bps": round(half_spread, 2),
            "market_impact_bps": round(impact_bps, 2),
            "total_cost_bps": round(total_bps, 2),
            "total_cost_usd": round(total_usd, 2),
            "exceeds_participation_limit": participation > self.max_participation_rate,
        }

    def adjust_returns(
        self,
        forward_returns: dict[str, float],
        execution_cost_bps: float,
    ) -> dict[str, float]:
        """Adjust forward returns by subtracting execution costs.

        Args:
            forward_returns: {"1d": 0.005, "5d": 0.02, ...}
            execution_cost_bps: Total one-way cost in bps.

        Returns:
            Adjusted returns dict.
        """
        cost_pct = execution_cost_bps / 10000  # One-way entry cost

        adjusted = {}
        for horizon, ret in forward_returns.items():
            # Subtract cost at entry + estimated cost at exit
            adjusted[horizon] = ret - (2 * cost_pct)

        return adjusted

    def simulate_portfolio_execution(
        self,
        positions: list[dict[str, Any]],
    ) -> dict:
        """Simulate execution costs for a full portfolio rebalance.

        Each position dict should contain: ticker, order_value, price,
        adv, volatility.

        Returns aggregate costs.
        """
        total_cost_usd = 0.0
        total_value = 0.0
        position_costs = []

        for pos in positions:
            result = self.simulate_execution(
                order_value_usd=pos.get("order_value", 0),
                price=pos.get("price", 0),
                adv=pos.get("adv", 1),
                daily_volatility=pos.get("volatility", 0.02),
                spread_bps=pos.get("spread_bps"),
            )
            total_cost_usd += result.get("total_cost_usd", 0)
            total_value += pos.get("order_value", 0)
            position_costs.append({
                "ticker": pos.get("ticker", "?"),
                **result,
            })

        avg_cost_bps = (
            (total_cost_usd / total_value * 10000) if total_value > 0 else 0
        )

        return {
            "total_cost_usd": round(total_cost_usd, 2),
            "total_order_value": round(total_value, 2),
            "avg_cost_bps": round(avg_cost_bps, 2),
            "position_count": len(positions),
            "positions": position_costs,
        }
