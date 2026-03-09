"""
src/engines/oms/brokers/ib_adapter.py
──────────────────────────────────────────────────────────────────────────────
Interactive Brokers Adapter — Interface stub.

Ready for ib_insync integration. Requires IB Gateway or TWS running.
"""
from __future__ import annotations
import logging
from src.engines.oms.models import Order, BrokerAccount, PortfolioPosition, OrderStatus
from src.engines.oms.brokers.base import BrokerAdapter, BrokerConfig, BrokerType

logger = logging.getLogger("365advisers.oms.broker.ib")

_IB_NOT_CONFIGURED = (
    "Interactive Brokers adapter not configured. "
    "To use IB: (1) Install ib_insync: pip install ib_insync, "
    "(2) Run IB Gateway or TWS, "
    "(3) Configure host/port in BrokerConfig."
)


class IBBrokerAdapter(BrokerAdapter):
    """
    Interactive Brokers adapter stub.

    Provides the full BrokerAdapter interface with NotImplementedError
    guidance. Replace method bodies with ib_insync calls to activate.

    Example integration pattern:
        from ib_insync import IB, MarketOrder, LimitOrder
        ib = IB()
        ib.connect('127.0.0.1', 7497, clientId=1)  # TWS paper
    """

    def __init__(self, config: BrokerConfig | None = None):
        cfg = config or BrokerConfig(broker_type=BrokerType.INTERACTIVE_BROKERS)
        super().__init__(cfg)
        self._ib = None  # placeholder for ib_insync.IB instance

    async def connect(self) -> bool:
        """
        Connect to IB Gateway / TWS.

        Requires ib_insync and a running IB Gateway instance.
        Default paper port: 7497, live port: 7496.
        """
        try:
            from ib_insync import IB
            host = self.config.base_url or "127.0.0.1"
            port = 7497 if self.config.paper_mode else 7496
            self._ib = IB()
            self._ib.connect(host, port, clientId=1)
            self._connected = True
            logger.info("Connected to IB Gateway at %s:%d", host, port)
            return True
        except ImportError:
            logger.error("ib_insync not installed. Run: pip install ib_insync")
            return False
        except Exception as e:
            logger.error("Failed to connect to IB: %s", e)
            return False

    async def disconnect(self) -> None:
        if self._ib:
            self._ib.disconnect()
        self._ib = None
        self._connected = False
        logger.info("Disconnected from IB")

    async def submit_order(self, order: Order) -> str:
        """Submit order to IB. Requires active connection."""
        if not self._ib or not self._connected:
            raise ConnectionError(_IB_NOT_CONFIGURED)
        try:
            from ib_insync import Stock, MarketOrder, LimitOrder
            contract = Stock(order.ticker, "SMART", "USD")
            action = "BUY" if order.side.value == "buy" else "SELL"

            if order.order_type.value == "market":
                ib_order = MarketOrder(action, order.quantity)
            elif order.order_type.value == "limit" and order.limit_price:
                ib_order = LimitOrder(action, order.quantity, order.limit_price)
            else:
                raise ValueError(f"Unsupported IB order type: {order.order_type}")

            trade = self._ib.placeOrder(contract, ib_order)
            broker_id = str(trade.order.orderId)
            logger.info("IB order submitted: %s → %s", order.ticker, broker_id)
            return broker_id
        except ImportError:
            raise ConnectionError(_IB_NOT_CONFIGURED)

    async def cancel_order(self, broker_order_id: str) -> bool:
        if not self._ib:
            raise ConnectionError(_IB_NOT_CONFIGURED)
        try:
            for trade in self._ib.openTrades():
                if str(trade.order.orderId) == broker_order_id:
                    self._ib.cancelOrder(trade.order)
                    return True
            return False
        except Exception as e:
            logger.error("IB cancel failed: %s", e)
            return False

    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        if not self._ib:
            return OrderStatus.REJECTED
        try:
            for trade in self._ib.trades():
                if str(trade.order.orderId) == broker_order_id:
                    status = trade.orderStatus.status.lower()
                    mapping = {
                        "submitted": OrderStatus.SUBMITTED,
                        "filled": OrderStatus.FILLED,
                        "cancelled": OrderStatus.CANCELLED,
                        "inactive": OrderStatus.REJECTED,
                    }
                    return mapping.get(status, OrderStatus.PENDING)
            return OrderStatus.REJECTED
        except Exception:
            return OrderStatus.REJECTED

    async def get_account(self) -> BrokerAccount:
        if not self._ib:
            raise ConnectionError(_IB_NOT_CONFIGURED)
        try:
            acct_values = self._ib.accountValues()
            cash = 0.0
            equity = 0.0
            for av in acct_values:
                if av.tag == "CashBalance" and av.currency == "USD":
                    cash = float(av.value)
                elif av.tag == "NetLiquidation" and av.currency == "USD":
                    equity = float(av.value)
            positions = await self.get_positions()
            return BrokerAccount(
                account_id="ib-live",
                cash=cash, buying_power=cash, total_equity=equity,
                positions=positions,
            )
        except Exception as e:
            logger.error("Failed to get IB account: %s", e)
            raise

    async def get_positions(self) -> list[PortfolioPosition]:
        if not self._ib:
            return []
        try:
            result = []
            for p in self._ib.positions():
                result.append(PortfolioPosition(
                    ticker=p.contract.symbol,
                    quantity=float(p.position),
                    avg_cost=float(p.avgCost),
                    market_value=float(p.position * p.avgCost),
                ))
            return result
        except Exception as e:
            logger.error("Failed to get IB positions: %s", e)
            return []

    async def get_quote(self, ticker: str) -> float:
        if not self._ib:
            raise ConnectionError(_IB_NOT_CONFIGURED)
        try:
            from ib_insync import Stock
            contract = Stock(ticker, "SMART", "USD")
            self._ib.qualifyContracts(contract)
            snapshot = self._ib.reqMktData(contract, snapshot=True)
            self._ib.sleep(2)
            price = snapshot.last if snapshot.last > 0 else snapshot.close
            return float(price)
        except Exception as e:
            logger.error("IB quote failed for %s: %s", ticker, e)
            raise

    async def health_check(self) -> dict:
        base = await super().health_check()
        base["ib_gateway_required"] = True
        base["default_paper_port"] = 7497
        base["default_live_port"] = 7496
        if self._ib and self._connected:
            base["status"] = "connected"
        else:
            base["status"] = "disconnected"
            base["setup_guide"] = _IB_NOT_CONFIGURED
        return base
