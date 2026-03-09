"""
src/engines/oms/brokers/alpaca_adapter.py
──────────────────────────────────────────────────────────────────────────────
Alpaca Markets Broker Adapter.

Uses the alpaca-py SDK for paper and live trading.
Requires: pip install alpaca-py
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from src.engines.oms.models import (
    Order, Fill, BrokerAccount, PortfolioPosition, OrderStatus, OrderType, OrderSide,
)
from src.engines.oms.brokers.base import BrokerAdapter, BrokerConfig, BrokerType

logger = logging.getLogger("365advisers.oms.broker.alpaca")

# Alpaca SDK status → internal status mapping
_STATUS_MAP = {
    "new": OrderStatus.SUBMITTED,
    "accepted": OrderStatus.SUBMITTED,
    "pending_new": OrderStatus.PENDING,
    "partially_filled": OrderStatus.PARTIAL,
    "filled": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELLED,
    "expired": OrderStatus.CANCELLED,
    "rejected": OrderStatus.REJECTED,
    "pending_cancel": OrderStatus.SUBMITTED,
    "pending_replace": OrderStatus.SUBMITTED,
    "replaced": OrderStatus.SUBMITTED,
}


class AlpacaBrokerAdapter(BrokerAdapter):
    """
    Alpaca Markets broker adapter.

    Supports both paper and live trading via the Alpaca Trading API.
    """

    def __init__(self, config: BrokerConfig):
        super().__init__(config)
        self._client = None

    async def connect(self) -> bool:
        """Connect to Alpaca API."""
        try:
            from alpaca.trading.client import TradingClient
            self._client = TradingClient(
                api_key=self.config.api_key,
                secret_key=self.config.api_secret,
                paper=self.config.paper_mode,
                url_override=self.config.base_url or None,
            )
            # Verify connectivity
            acct = self._client.get_account()
            self._connected = True
            logger.info(
                "Connected to Alpaca (%s) — equity: $%s",
                "paper" if self.config.paper_mode else "LIVE",
                acct.equity,
            )
            return True
        except ImportError:
            logger.error("alpaca-py not installed. Run: pip install alpaca-py")
            return False
        except Exception as e:
            logger.error("Failed to connect to Alpaca: %s", e)
            return False

    async def disconnect(self) -> None:
        self._client = None
        self._connected = False
        logger.info("Disconnected from Alpaca")

    async def submit_order(self, order: Order) -> str:
        """Submit order to Alpaca and return broker order ID."""
        if not self._client:
            raise ConnectionError("Not connected to Alpaca")

        try:
            from alpaca.trading.requests import (
                MarketOrderRequest, LimitOrderRequest,
                StopOrderRequest, StopLimitOrderRequest,
            )
            from alpaca.trading.enums import OrderSide as AlpacaSide, TimeInForce

            side = AlpacaSide.BUY if order.side == OrderSide.BUY else AlpacaSide.SELL

            if order.order_type == OrderType.MARKET:
                req = MarketOrderRequest(
                    symbol=order.ticker,
                    qty=order.quantity,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                )
            elif order.order_type == OrderType.LIMIT:
                req = LimitOrderRequest(
                    symbol=order.ticker,
                    qty=order.quantity,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=order.limit_price,
                )
            elif order.order_type == OrderType.STOP:
                req = StopOrderRequest(
                    symbol=order.ticker,
                    qty=order.quantity,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                    stop_price=order.stop_price,
                )
            elif order.order_type == OrderType.STOP_LIMIT:
                req = StopLimitOrderRequest(
                    symbol=order.ticker,
                    qty=order.quantity,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=order.limit_price,
                    stop_price=order.stop_price,
                )
            else:
                raise ValueError(f"Unsupported order type: {order.order_type}")

            result = self._client.submit_order(req)
            broker_id = str(result.id)
            logger.info("Alpaca order submitted: %s → %s", order.ticker, broker_id)
            return broker_id

        except Exception as e:
            logger.error("Alpaca order submission failed: %s", e)
            raise

    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel an order via Alpaca."""
        if not self._client:
            return False
        try:
            self._client.cancel_order_by_id(broker_order_id)
            logger.info("Alpaca order cancelled: %s", broker_order_id)
            return True
        except Exception as e:
            logger.error("Alpaca cancel failed: %s", e)
            return False

    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        """Get order status from Alpaca."""
        if not self._client:
            return OrderStatus.REJECTED
        try:
            alpaca_order = self._client.get_order_by_id(broker_order_id)
            status_str = str(alpaca_order.status.value).lower()
            return _STATUS_MAP.get(status_str, OrderStatus.PENDING)
        except Exception as e:
            logger.error("Failed to get Alpaca order status: %s", e)
            return OrderStatus.REJECTED

    async def get_account(self) -> BrokerAccount:
        """Fetch account from Alpaca."""
        if not self._client:
            raise ConnectionError("Not connected to Alpaca")
        try:
            acct = self._client.get_account()
            positions = await self.get_positions()
            return BrokerAccount(
                account_id=str(acct.account_number),
                cash=float(acct.cash),
                buying_power=float(acct.buying_power),
                total_equity=float(acct.equity),
                positions=positions,
            )
        except Exception as e:
            logger.error("Failed to get Alpaca account: %s", e)
            raise

    async def get_positions(self) -> list[PortfolioPosition]:
        """Fetch all positions from Alpaca."""
        if not self._client:
            return []
        try:
            alpaca_positions = self._client.get_all_positions()
            result = []
            for p in alpaca_positions:
                result.append(PortfolioPosition(
                    ticker=p.symbol,
                    quantity=float(p.qty),
                    avg_cost=float(p.avg_entry_price),
                    current_price=float(p.current_price),
                    market_value=float(p.market_value),
                    unrealized_pnl=float(p.unrealized_pl),
                ))
            return result
        except Exception as e:
            logger.error("Failed to get Alpaca positions: %s", e)
            return []

    async def get_quote(self, ticker: str) -> float:
        """Get latest trade price from Alpaca."""
        if not self._client:
            raise ConnectionError("Not connected to Alpaca")
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockLatestTradeRequest
            data_client = StockHistoricalDataClient(
                api_key=self.config.api_key,
                secret_key=self.config.api_secret,
            )
            trade = data_client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=ticker))
            if isinstance(trade, dict):
                return float(trade[ticker].price)
            return float(trade.price)
        except Exception as e:
            logger.error("Failed to get Alpaca quote for %s: %s", ticker, e)
            raise

    async def health_check(self) -> dict:
        base = await super().health_check()
        if self._client:
            try:
                acct = self._client.get_account()
                base["equity"] = float(acct.equity)
                base["cash"] = float(acct.cash)
                base["status"] = str(acct.status)
                base["trading_blocked"] = bool(acct.trading_blocked)
            except Exception:
                base["error"] = "Failed to fetch account"
        return base
