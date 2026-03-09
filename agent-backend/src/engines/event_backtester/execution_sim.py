"""
src/engines/event_backtester/execution_sim.py — Execution simulator with slippage and commission.
"""
from __future__ import annotations
import random
import logging
from datetime import datetime, timezone
from src.engines.event_backtester.models import (
    OrderEvent, FillEvent, BacktestConfig,
)

logger = logging.getLogger("365advisers.backtester.exec")


class ExecutionSimulator:
    """Simulate order execution with realistic slippage and commissions."""

    def __init__(self, config: BacktestConfig):
        self.config = config

    def execute(self, order: OrderEvent, market_price: float) -> FillEvent:
        """Execute an order at market price with slippage + commission."""
        slippage_pct = self.config.slippage_bps / 10000 * random.uniform(0.5, 1.5)

        if order.side == "buy":
            fill_price = market_price * (1 + slippage_pct)
        else:
            fill_price = market_price * (1 - slippage_pct)

        commission = abs(order.quantity * fill_price * self.config.commission_bps / 10000)

        return FillEvent(
            timestamp=order.timestamp,
            ticker=order.ticker,
            side=order.side,
            quantity=order.quantity,
            fill_price=round(fill_price, 4),
            commission=round(commission, 4),
            slippage=round(abs(fill_price - market_price), 4),
        )

    def execute_limit(self, order: OrderEvent, market_price: float) -> FillEvent | None:
        """Execute limit order only if price is favourable."""
        if order.limit_price is None:
            return self.execute(order, market_price)

        if order.side == "buy" and market_price <= order.limit_price:
            return self.execute(order, market_price)
        elif order.side == "sell" and market_price >= order.limit_price:
            return self.execute(order, market_price)

        return None  # not filled
