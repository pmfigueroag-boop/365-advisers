"""
src/engines/market_feed/simulated_feed.py — Simulated market data for development.
"""
from __future__ import annotations
import asyncio
import logging
import random
from datetime import datetime, timezone
from src.engines.market_feed.base import DataFeedAdapter
from src.engines.market_feed.models import FeedConfig, FeedType, Quote, Bar, TradeUpdate

logger = logging.getLogger("365advisers.feed.simulated")

# Default base prices for common tickers
_BASE_PRICES = {
    "AAPL": 175.0, "MSFT": 420.0, "GOOGL": 175.0, "AMZN": 185.0,
    "META": 500.0, "NVDA": 900.0, "TSLA": 250.0, "JPM": 195.0,
    "V": 280.0, "JNJ": 155.0, "SPY": 520.0, "QQQ": 450.0,
}


class SimulatedFeed(DataFeedAdapter):
    """
    Simulated market data feed.

    Generates random price movements around base prices.
    Useful for development, paper trading, and testing.
    """

    def __init__(self, config: FeedConfig | None = None):
        cfg = config or FeedConfig(feed_type=FeedType.SIMULATED)
        super().__init__(cfg)
        self._subscriptions: set[str] = set()
        self._prices: dict[str, float] = dict(_BASE_PRICES)
        self._task: asyncio.Task | None = None
        self._running = False
        self._tick_count = 0

    async def connect(self) -> bool:
        self._connected = True
        self._running = True
        logger.info("Simulated feed connected")
        return True

    async def disconnect(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._connected = False
        logger.info("Simulated feed disconnected")

    async def subscribe(self, tickers: list[str]) -> None:
        for t in tickers:
            self._subscriptions.add(t.upper())
            if t.upper() not in self._prices:
                self._prices[t.upper()] = random.uniform(50, 500)
        logger.info("Subscribed to %s (total: %d)", tickers, len(self._subscriptions))

    async def unsubscribe(self, tickers: list[str]) -> None:
        for t in tickers:
            self._subscriptions.discard(t.upper())

    def start_streaming(self) -> asyncio.Task:
        """Start the background tick generator."""
        self._task = asyncio.create_task(self._tick_loop())
        return self._task

    async def _tick_loop(self):
        """Generate ticks at configured interval."""
        interval = self.config.tick_interval_ms / 1000.0
        while self._running and self._connected:
            for ticker in list(self._subscriptions):
                quote = self._generate_tick(ticker)
                if self._on_quote:
                    self._on_quote(quote)
                if self._on_trade:
                    trade = TradeUpdate(
                        ticker=ticker, price=quote.last,
                        size=random.randint(10, 1000),
                    )
                    self._on_trade(trade)
                self._tick_count += 1
            await asyncio.sleep(interval)

    def generate_tick(self, ticker: str) -> Quote:
        """Generate a single tick (public, for testing)."""
        return self._generate_tick(ticker.upper())

    def _generate_tick(self, ticker: str) -> Quote:
        """Generate a random tick around the base price."""
        base = self._prices.get(ticker, 100.0)
        # Random walk: ±0.3% per tick
        change = base * random.gauss(0, 0.003)
        new_price = max(base + change, 0.01)
        self._prices[ticker] = new_price

        spread = new_price * random.uniform(0.0001, 0.001)
        bid = round(new_price - spread / 2, 4)
        ask = round(new_price + spread / 2, 4)

        return Quote(
            ticker=ticker, bid=bid, ask=ask,
            last=round(new_price, 4),
            volume=random.randint(1000, 100000),
        )

    def set_price(self, ticker: str, price: float):
        """Set base price for a ticker."""
        self._prices[ticker.upper()] = price

    @property
    def tick_count(self) -> int:
        return self._tick_count
