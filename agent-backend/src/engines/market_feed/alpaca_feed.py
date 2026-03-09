"""
src/engines/market_feed/alpaca_feed.py — Alpaca WebSocket data feed.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from src.engines.market_feed.base import DataFeedAdapter
from src.engines.market_feed.models import FeedConfig, FeedType, Quote, Bar, TradeUpdate

logger = logging.getLogger("365advisers.feed.alpaca")


class AlpacaFeed(DataFeedAdapter):
    """
    Alpaca Markets real-time data feed via WebSocket.

    Uses alpaca-py StockDataStream for:
    - Real-time quotes (NBBO)
    - Real-time trades
    - 1-minute bars
    """

    def __init__(self, config: FeedConfig):
        super().__init__(config)
        self._stream = None
        self._subscriptions: set[str] = set()

    async def connect(self) -> bool:
        try:
            from alpaca.data.live import StockDataStream
            self._stream = StockDataStream(
                api_key=self.config.api_key,
                secret_key=self.config.api_secret,
            )

            # Register handlers
            async def _handle_quote(data):
                quote = Quote(
                    ticker=data.symbol,
                    bid=float(data.bid_price),
                    ask=float(data.ask_price),
                    volume=int(data.bid_size + data.ask_size),
                )
                if self._on_quote:
                    self._on_quote(quote)

            async def _handle_trade(data):
                trade = TradeUpdate(
                    ticker=data.symbol,
                    price=float(data.price),
                    size=int(data.size),
                    exchange=str(data.exchange) if hasattr(data, 'exchange') else "",
                )
                if self._on_trade:
                    self._on_trade(trade)
                # Also update quote with last trade price
                if self._on_quote:
                    self._on_quote(Quote(ticker=data.symbol, last=float(data.price)))

            async def _handle_bar(data):
                bar = Bar(
                    ticker=data.symbol,
                    open=float(data.open),
                    high=float(data.high),
                    low=float(data.low),
                    close=float(data.close),
                    volume=int(data.volume),
                    vwap=float(data.vwap) if hasattr(data, 'vwap') else 0.0,
                )
                if self._on_bar:
                    self._on_bar(bar)

            self._stream.subscribe_quotes(_handle_quote)
            self._stream.subscribe_trades(_handle_trade)
            self._stream.subscribe_bars(_handle_bar)

            self._connected = True
            logger.info("Alpaca feed connected")
            return True

        except ImportError:
            logger.error("alpaca-py not installed. Run: pip install alpaca-py")
            return False
        except Exception as e:
            logger.error("Failed to connect Alpaca feed: %s", e)
            return False

    async def disconnect(self) -> None:
        if self._stream:
            try:
                self._stream.stop()
            except Exception:
                pass
        self._stream = None
        self._connected = False
        logger.info("Alpaca feed disconnected")

    async def subscribe(self, tickers: list[str]) -> None:
        symbols = [t.upper() for t in tickers]
        self._subscriptions.update(symbols)
        if self._stream:
            try:
                self._stream.subscribe_quotes(*symbols)
                self._stream.subscribe_trades(*symbols)
                self._stream.subscribe_bars(*symbols)
                logger.info("Alpaca subscribed: %s", symbols)
            except Exception as e:
                logger.error("Alpaca subscribe failed: %s", e)

    async def unsubscribe(self, tickers: list[str]) -> None:
        symbols = [t.upper() for t in tickers]
        self._subscriptions -= set(symbols)
        if self._stream:
            try:
                self._stream.unsubscribe_quotes(*symbols)
                self._stream.unsubscribe_trades(*symbols)
                logger.info("Alpaca unsubscribed: %s", symbols)
            except Exception as e:
                logger.error("Alpaca unsubscribe failed: %s", e)

    def run(self):
        """Start the WebSocket stream (blocking). Call in a background thread."""
        if self._stream:
            self._stream.run()
