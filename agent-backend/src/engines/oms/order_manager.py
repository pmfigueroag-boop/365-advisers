"""
src/engines/oms/order_manager.py — Order lifecycle management.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from src.engines.oms.models import Order, OrderStatus, OrderSide, Fill

logger = logging.getLogger("365advisers.oms.order_manager")


class OrderManager:
    """In-memory order book with full lifecycle."""

    def __init__(self):
        self._orders: dict[str, Order] = {}
        self._fills: list[Fill] = []

    def create_order(self, **kwargs) -> Order:
        order = Order(**kwargs)
        self._orders[order.order_id] = order
        logger.info("Order created: %s %s %s qty=%s", order.order_id, order.side.value, order.ticker, order.quantity)
        return order

    def submit_order(self, order_id: str) -> Order | None:
        order = self._orders.get(order_id)
        if not order or order.status != OrderStatus.PENDING:
            return None
        order.status = OrderStatus.SUBMITTED
        order.updated_at = datetime.now(timezone.utc)
        return order

    def fill_order(self, order_id: str, fill_price: float, fill_quantity: float | None = None) -> Fill | None:
        order = self._orders.get(order_id)
        if not order or order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
            return None

        qty = fill_quantity or (order.quantity - order.filled_quantity)
        qty = min(qty, order.quantity - order.filled_quantity)

        fill = Fill(order_id=order_id, fill_price=fill_price, fill_quantity=qty)
        self._fills.append(fill)

        # Update order
        total_cost = order.avg_fill_price * order.filled_quantity + fill_price * qty
        order.filled_quantity += qty
        order.avg_fill_price = total_cost / order.filled_quantity if order.filled_quantity > 0 else 0
        order.status = OrderStatus.FILLED if order.filled_quantity >= order.quantity else OrderStatus.PARTIAL
        order.updated_at = datetime.now(timezone.utc)
        return fill

    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if not order or order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED):
            return False
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc)
        return True

    def reject_order(self, order_id: str, reason: str = "") -> bool:
        order = self._orders.get(order_id)
        if not order:
            return False
        order.status = OrderStatus.REJECTED
        order.rejection_reason = reason
        order.updated_at = datetime.now(timezone.utc)
        return True

    def get_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def get_open_orders(self) -> list[Order]:
        return [o for o in self._orders.values() if o.status in (OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL)]

    def get_order_history(self, ticker: str | None = None) -> list[Order]:
        orders = list(self._orders.values())
        if ticker:
            orders = [o for o in orders if o.ticker == ticker]
        return sorted(orders, key=lambda o: o.created_at, reverse=True)

    def get_fills(self, order_id: str) -> list[Fill]:
        return [f for f in self._fills if f.order_id == order_id]

    @property
    def total_orders(self) -> int:
        return len(self._orders)
