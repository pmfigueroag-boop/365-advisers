"""
src/engines/oms/engine.py — OMS orchestrator with broker adapter integration.
"""
from __future__ import annotations
import logging
from src.engines.oms.models import Order, BrokerAccount, OrderStatus, OrderSide
from src.engines.oms.order_manager import OrderManager
from src.engines.oms.risk_checks import PreTradeRiskChecker
from src.engines.oms.position_sync import PositionSyncEngine, SyncReport
from src.engines.oms.brokers.base import BrokerAdapter, BrokerConfig, BrokerType
from src.engines.oms.brokers.paper import PaperBrokerAdapter

logger = logging.getLogger("365advisers.oms.engine")


class OMSEngine:
    """
    Full OMS: order lifecycle with pre-trade risk gate and broker routing.

    Supports pluggable broker adapters (paper, Alpaca, IB).
    Defaults to paper trading if no adapter is provided.
    """

    def __init__(self, account: BrokerAccount | None = None, adapter: BrokerAdapter | None = None):
        self.order_manager = OrderManager()
        self.account = account or BrokerAccount()
        self._adapter: BrokerAdapter = adapter or PaperBrokerAdapter()
        self._adapter_connected = False

    @property
    def broker_type(self) -> str:
        return self._adapter.broker_type.value

    async def connect_broker(self, config: BrokerConfig | None = None) -> dict:
        """Connect to broker. Optionally switch adapter via config."""
        if config:
            self._adapter = self._create_adapter(config)

        success = await self._adapter.connect()
        self._adapter_connected = success

        if success:
            # Sync account state from broker
            self.account = await self._adapter.get_account()

        return {
            "connected": success,
            "broker": self._adapter.broker_type.value,
            "paper_mode": self._adapter.config.paper_mode,
        }

    async def disconnect_broker(self) -> None:
        await self._adapter.disconnect()
        self._adapter_connected = False

    def place_order(self, ticker: str, side: str, quantity: float, price: float, **kwargs) -> dict:
        """Create, risk-check, and submit an order (sync — for backward compat)."""
        order = self.order_manager.create_order(ticker=ticker, side=side, quantity=quantity, **kwargs)
        order.broker_type = self._adapter.broker_type.value

        checks = PreTradeRiskChecker.run_all(order, self.account, price)
        if not PreTradeRiskChecker.all_passed(checks):
            failed = [c for c in checks if not c.passed]
            reason = "; ".join(c.message for c in failed)
            self.order_manager.reject_order(order.order_id, reason)
            return {"order": order.model_dump(), "risk_checks": [c.model_dump() for c in checks], "status": "rejected"}

        self.order_manager.submit_order(order.order_id)
        return {"order": order.model_dump(), "risk_checks": [c.model_dump() for c in checks], "status": "submitted"}

    async def place_order_async(self, ticker: str, side: str, quantity: float, price: float, **kwargs) -> dict:
        """Create, risk-check, and route order through broker adapter."""
        order = self.order_manager.create_order(ticker=ticker, side=side, quantity=quantity, **kwargs)
        order.broker_type = self._adapter.broker_type.value

        checks = PreTradeRiskChecker.run_all(order, self.account, price)
        if not PreTradeRiskChecker.all_passed(checks):
            failed = [c for c in checks if not c.passed]
            reason = "; ".join(c.message for c in failed)
            self.order_manager.reject_order(order.order_id, reason)
            return {"order": order.model_dump(), "risk_checks": [c.model_dump() for c in checks], "status": "rejected"}

        try:
            broker_id = await self._adapter.submit_order(order)
            order.broker_order_id = broker_id
            order.status = OrderStatus.SUBMITTED
            return {
                "order": order.model_dump(),
                "risk_checks": [c.model_dump() for c in checks],
                "status": "submitted",
                "broker_order_id": broker_id,
            }
        except Exception as e:
            self.order_manager.reject_order(order.order_id, str(e))
            return {"order": order.model_dump(), "risk_checks": [c.model_dump() for c in checks], "status": "rejected", "error": str(e)}

    async def cancel_order_async(self, order_id: str) -> dict:
        """Cancel order via broker adapter."""
        order = self.order_manager.get_order(order_id)
        if not order:
            return {"success": False, "error": "Order not found"}

        if order.broker_order_id:
            success = await self._adapter.cancel_order(order.broker_order_id)
        else:
            success = self.order_manager.cancel_order(order_id)

        if success:
            self.order_manager.cancel_order(order_id)
        return {"success": success, "order_id": order_id}

    async def sync_positions(self) -> SyncReport:
        """Sync positions between local state and broker."""
        broker_positions = await self._adapter.get_positions()
        local_positions = self.account.positions
        report = PositionSyncEngine.reconcile(local_positions, broker_positions)

        # Update local to match broker
        self.account.positions = broker_positions
        return report

    async def sync_account(self) -> dict:
        """Refresh account state from broker."""
        self.account = await self._adapter.get_account()
        return self.account.model_dump()

    async def get_quote(self, ticker: str) -> float:
        """Get current price from broker."""
        return await self._adapter.get_quote(ticker)

    async def broker_health(self) -> dict:
        """Get broker health status."""
        return await self._adapter.health_check()

    def simulate_fill(self, order_id: str, fill_price: float) -> dict | None:
        """Simulate an order fill (for paper trading — backward compat)."""
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

    @staticmethod
    def _create_adapter(config: BrokerConfig) -> BrokerAdapter:
        """Factory method to create the right adapter from config."""
        if config.broker_type == BrokerType.ALPACA:
            from src.engines.oms.brokers.alpaca_adapter import AlpacaBrokerAdapter
            return AlpacaBrokerAdapter(config)
        elif config.broker_type == BrokerType.INTERACTIVE_BROKERS:
            from src.engines.oms.brokers.ib_adapter import IBBrokerAdapter
            return IBBrokerAdapter(config)
        else:
            return PaperBrokerAdapter(config)
