"""
src/engines/oms/engine.py — OMS orchestrator with risk gate.
"""
from __future__ import annotations
import logging
from src.engines.oms.models import Order, BrokerAccount, OrderStatus
from src.engines.oms.order_manager import OrderManager
from src.engines.oms.risk_checks import PreTradeRiskChecker

logger = logging.getLogger("365advisers.oms.engine")


class OMSEngine:
    """Full OMS: order lifecycle with pre-trade risk gate."""

    def __init__(self, account: BrokerAccount | None = None):
        self.order_manager = OrderManager()
        self.account = account or BrokerAccount()

    def place_order(self, ticker: str, side: str, quantity: float, price: float, **kwargs) -> dict:
        """Create, risk-check, and submit an order."""
        order = self.order_manager.create_order(ticker=ticker, side=side, quantity=quantity, **kwargs)

        checks = PreTradeRiskChecker.run_all(order, self.account, price)
        if not PreTradeRiskChecker.all_passed(checks):
            failed = [c for c in checks if not c.passed]
            reason = "; ".join(c.message for c in failed)
            self.order_manager.reject_order(order.order_id, reason)
            return {"order": order.model_dump(), "risk_checks": [c.model_dump() for c in checks], "status": "rejected"}

        self.order_manager.submit_order(order.order_id)
        return {"order": order.model_dump(), "risk_checks": [c.model_dump() for c in checks], "status": "submitted"}

    def simulate_fill(self, order_id: str, fill_price: float) -> dict | None:
        """Simulate an order fill (for paper trading)."""
        fill = self.order_manager.fill_order(order_id, fill_price)
        if not fill:
            return None
        order = self.order_manager.get_order(order_id)
        if order and order.status == OrderStatus.FILLED:
            self._update_account(order, fill_price)
        return {"fill": fill.model_dump(), "order": order.model_dump() if order else None}

    def _update_account(self, order: Order, price: float):
        cost = order.quantity * price
        if order.side.value == "buy":
            self.account.cash -= cost
            self.account.buying_power -= cost
        else:
            self.account.cash += cost
            self.account.buying_power += cost

    def get_open_orders(self) -> list[dict]:
        return [o.model_dump() for o in self.order_manager.get_open_orders()]

    def get_account(self) -> dict:
        return self.account.model_dump()
