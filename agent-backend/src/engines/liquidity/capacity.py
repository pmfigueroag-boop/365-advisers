"""
src/engines/liquidity/capacity.py
─────────────────────────────────────────────────────────────────────────────
CapacityCalculator — Estimates strategy-level capacity (max AUM).
"""

from __future__ import annotations

import logging
from typing import Any

from src.data.database import SessionLocal

logger = logging.getLogger("365advisers.liquidity.capacity")


class CapacityCalculator:
    """Estimates capacity constraints at strategy and portfolio levels."""

    def compute_portfolio_capacity(
        self,
        positions: list[dict[str, Any]],
        target_participation: float = 0.05,
        holding_period_days: int = 20,
    ) -> dict:
        """Estimate portfolio-level capacity from position-level data.

        Each position dict should contain: ticker, weight, adv, price.

        Returns the minimum capacity across all positions (bottleneck),
        plus per-position capacity breakdown.
        """
        if not positions:
            return {"capacity_usd": 0, "bottleneck": "none", "positions": []}

        position_capacities = []
        for pos in positions:
            adv = pos.get("adv", 0)
            price = pos.get("price", 0)
            weight = pos.get("weight", 0)

            # Position capacity = ADV × price × target_part × holding
            pos_capacity = adv * price * target_participation * holding_period_days

            # Strategy capacity is pos_capacity / weight (scale up)
            strategy_capacity = pos_capacity / weight if weight > 0 else float("inf")

            position_capacities.append({
                "ticker": pos.get("ticker", "?"),
                "weight": weight,
                "position_capacity_usd": round(pos_capacity, 2),
                "strategy_capacity_usd": round(strategy_capacity, 2),
            })

        # Bottleneck = position with lowest strategy capacity
        position_capacities.sort(key=lambda p: p["strategy_capacity_usd"])
        bottleneck = position_capacities[0]

        return {
            "capacity_usd": bottleneck["strategy_capacity_usd"],
            "bottleneck_ticker": bottleneck["ticker"],
            "position_capacities": position_capacities,
        }

    def compute_ticker_capacity(
        self,
        ticker: str,
        target_participation: float = 0.05,
        holding_period_days: int = 20,
    ) -> dict:
        """Compute capacity for a single ticker from stored profiles."""
        from src.data.database import LiquidityProfileRecord

        with SessionLocal() as db:
            profile = (
                db.query(LiquidityProfileRecord)
                .filter(LiquidityProfileRecord.ticker == ticker)
                .order_by(LiquidityProfileRecord.updated_at.desc())
                .first()
            )

        if not profile:
            return {"ticker": ticker, "error": "No liquidity profile found"}

        capacity = (
            (profile.avg_daily_volume_20d or 0)
            * target_participation
            * holding_period_days
            * ((profile.market_cap or 0) / (profile.avg_daily_volume_20d or 1))
            if profile.avg_daily_volume_20d
            else 0
        )

        return {
            "ticker": ticker,
            "liquidity_tier": profile.liquidity_tier,
            "estimated_capacity_usd": profile.estimated_capacity_usd,
            "computed_capacity_usd": round(capacity, 2),
            "target_participation": target_participation,
            "holding_period_days": holding_period_days,
        }
