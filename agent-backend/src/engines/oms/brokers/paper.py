"""
src/engines/oms/brokers/paper.py
──────────────────────────────────────────────────────────────────────────────
Paper Trading Broker Adapter — wraps existing in-memory OrderManager.

Simulates fills at current price with optional random slippage.
"""
from __future__ import annotations
import logging
import random
from src.engines.oms.models import Order, Fill, BrokerAccount, PortfolioPosition, OrderStatus
from src.engines.oms.brokers.base import BrokerAdapter, BrokerConfig, BrokerType
from src.engines.oms.order_manager import OrderManager

logger = logging.getLogger("365advisers.oms.broker.paper")


class PaperBrokerAdapter(BrokerAdapter):
    """
    Paper trading adapter.

    Uses the existing in-memory OrderManager for order lifecycle,
    simulates fills with configurable slippage.
    """

    def __init__(self, config: BrokerConfig | None = None):
        cfg = config or BrokerConfig(broker_type=BrokerType.PAPER, paper_mode=True)
        super().__init__(cfg)
        self._order_manager = OrderManager()
        self._account = BrokerAccount(account_id="paper-default")
        self._positions: dict[str, PortfolioPosition] = {}
        self._prices: dict[str, float] = {}
        self._slippage_bps: float = 5.0  # 5 bps default slippage

    async def connect(self) -> bool:
        self._connected = True
        logger.info("Paper broker connected")
        return True

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("Paper broker disconnected")

    async def submit_order(self, order: Order) -> str:
        """Submit order and simulate immediate fill for market orders."""
        internal = self._order_manager.create_order(
            ticker=order.ticker, side=order.side,
            quantity=order.quantity, order_type=order.order_type,
            limit_price=order.limit_price, stop_price=order.stop_price,
        )
        self._order_manager.submit_order(internal.order_id)

        # Auto-fill market orders
        if order.order_type.value == "market":
            price = self._get_fill_price(order.ticker, order.side.value)
            fill = self._order_manager.fill_order(internal.order_id, price)
            if fill:
                self._update_positions(order.ticker, order.side.value, fill.fill_quantity, price)
                self._update_cash(order.side.value, fill.fill_quantity, price)
                logger.info("Paper fill: %s %s %s @ %.2f", order.side.value, order.quantity, order.ticker, price)

        return internal.order_id

    async def cancel_order(self, broker_order_id: str) -> bool:
        return self._order_manager.cancel_order(broker_order_id)

    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        order = self._order_manager.get_order(broker_order_id)
        return order.status if order else OrderStatus.REJECTED

    async def get_account(self) -> BrokerAccount:
        self._account.positions = list(self._positions.values())
        equity = self._account.cash + sum(p.market_value for p in self._positions.values())
        self._account.total_equity = equity
        self._account.buying_power = self._account.cash
        return self._account

    async def get_positions(self) -> list[PortfolioPosition]:
        return list(self._positions.values())

    async def get_quote(self, ticker: str) -> float:
        return self._prices.get(ticker, 100.0)

    def set_price(self, ticker: str, price: float):
        """Set simulated market price for a ticker."""
        self._prices[ticker] = price
        if ticker in self._positions:
            pos = self._positions[ticker]
            pos.current_price = price
            pos.market_value = pos.quantity * price
            pos.unrealized_pnl = (price - pos.avg_cost) * pos.quantity

    def _get_fill_price(self, ticker: str, side: str) -> float:
        """Get fill price with slippage."""
        base_price = self._prices.get(ticker, 100.0)
        slippage = base_price * (self._slippage_bps / 10000) * random.uniform(0.5, 1.5)
        if side == "buy":
            return round(base_price + slippage, 4)
        return round(base_price - slippage, 4)

    def _update_positions(self, ticker: str, side: str, qty: float, price: float):
        """Update position tracking after a fill."""
        if ticker not in self._positions:
            self._positions[ticker] = PortfolioPosition(ticker=ticker)

        pos = self._positions[ticker]
        if side == "buy":
            total_cost = pos.avg_cost * pos.quantity + price * qty
            pos.quantity += qty
            pos.avg_cost = total_cost / pos.quantity if pos.quantity > 0 else 0
        else:
            pos.quantity -= qty
            if pos.quantity <= 0:
                del self._positions[ticker]
                return

        pos.current_price = price
        pos.market_value = pos.quantity * price
        pos.unrealized_pnl = (price - pos.avg_cost) * pos.quantity

    def _update_cash(self, side: str, qty: float, price: float):
        cost = qty * price
        if side == "buy":
            self._account.cash -= cost
        else:
            self._account.cash += cost

    async def health_check(self) -> dict:
        base = await super().health_check()
        base["positions_count"] = len(self._positions)
        base["cash"] = self._account.cash
        base["slippage_bps"] = self._slippage_bps
        return base
