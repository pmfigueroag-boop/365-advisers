"""
src/engines/market_feed/engine.py — Market Feed Orchestrator.
"""
from __future__ import annotations
import logging
import time
from datetime import datetime, timezone
from src.engines.market_feed.models import FeedConfig, FeedType, Quote, Bar, TradeUpdate, FeedHealth
from src.engines.market_feed.base import DataFeedAdapter
from src.engines.market_feed.simulated_feed import SimulatedFeed
from src.engines.market_feed.alpaca_feed import AlpacaFeed
from src.engines.market_feed.quote_cache import QuoteCache
from src.engines.market_feed.subscription_manager import SubscriptionManager

logger = logging.getLogger("365advisers.feed.engine")


class MarketFeedEngine:
    """
    Orchestrator: connects feed adapter → cache → SSE clients.
    """

    def __init__(self, config: FeedConfig | None = None):
        self.config = config or FeedConfig()
        self.cache = QuoteCache()
        self.subscriptions = SubscriptionManager()
        self._adapter: DataFeedAdapter | None = None
        self._start_time: float | None = None
        self._sse_clients: list = []  # list of asyncio.Queue for SSE
        self._last_quote_at: datetime | None = None

    async def start(self, config: FeedConfig | None = None) -> dict:
        """Start the market feed."""
        if config:
            self.config = config

        self._adapter = self._create_adapter(self.config)
        self._adapter.on_quote(self._handle_quote)
        self._adapter.on_bar(self._handle_bar)
        self._adapter.on_trade(self._handle_trade)

        success = await self._adapter.connect()
        if success:
            self._start_time = time.time()

        # Auto-subscribe configured symbols
        if self.config.symbols:
            await self.subscribe(self.config.symbols)

        return {"started": success, "feed": self.config.feed_type.value}

    async def stop(self) -> None:
        if self._adapter:
            await self._adapter.disconnect()
        self._start_time = None

    async def subscribe(self, tickers: list[str]) -> dict:
        """Subscribe to tickers."""
        new_tickers = []
        for t in tickers:
            is_new = self.subscriptions.subscribe(t, self.config.feed_type.value)
            if is_new:
                new_tickers.append(t.upper())

        if new_tickers and self._adapter:
            await self._adapter.subscribe(new_tickers)

        return {"subscribed": new_tickers, "total": self.subscriptions.count}

    async def unsubscribe(self, tickers: list[str]) -> dict:
        """Unsubscribe from tickers."""
        removed = []
        for t in tickers:
            if self.subscriptions.unsubscribe(t):
                removed.append(t.upper())

        if removed and self._adapter:
            await self._adapter.unsubscribe(removed)

        return {"unsubscribed": removed, "total": self.subscriptions.count}

    def get_quote(self, ticker: str) -> dict | None:
        q = self.cache.get_quote(ticker)
        return q.model_dump() if q else None

    def get_all_quotes(self) -> dict:
        return self.cache.snapshot()

    def get_bars(self, ticker: str, limit: int = 60) -> list[dict]:
        bars = self.cache.get_bars(ticker, limit)
        return [b.model_dump() for b in bars]

    def health(self) -> FeedHealth:
        uptime = time.time() - self._start_time if self._start_time else 0
        return FeedHealth(
            feed_type=self.config.feed_type.value,
            connected=self._adapter.is_connected if self._adapter else False,
            active_subscriptions=self.subscriptions.count,
            quotes_received=self.cache.total_updates,
            last_quote_at=self._last_quote_at,
            uptime_seconds=round(uptime, 1),
        )

    # ── SSE Support ──────────────────────────────────────────────────────

    def register_sse_client(self, queue) -> None:
        self._sse_clients.append(queue)

    def unregister_sse_client(self, queue) -> None:
        if queue in self._sse_clients:
            self._sse_clients.remove(queue)

    # ── Internal Handlers ────────────────────────────────────────────────

    def _handle_quote(self, quote: Quote):
        self.cache.update(quote)
        self._last_quote_at = quote.timestamp
        self._broadcast_sse({"type": "quote", "data": quote.model_dump()})

    def _handle_bar(self, bar: Bar):
        self._broadcast_sse({"type": "bar", "data": bar.model_dump()})

    def _handle_trade(self, trade: TradeUpdate):
        self._broadcast_sse({"type": "trade", "data": trade.model_dump()})

    def _broadcast_sse(self, event: dict):
        for q in self._sse_clients:
            try:
                q.put_nowait(event)
            except Exception:
                pass  # queue full or closed

    @staticmethod
    def _create_adapter(config: FeedConfig) -> DataFeedAdapter:
        if config.feed_type == FeedType.ALPACA:
            return AlpacaFeed(config)
        return SimulatedFeed(config)
