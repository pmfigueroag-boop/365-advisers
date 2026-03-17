"""
src/engines/data/websocket_feed.py
--------------------------------------------------------------------------
WebSocket Feed Infrastructure — real-time market data pipeline.

Provides a framework for streaming price data via WebSocket connections
with reconnection logic, heartbeat monitoring, and message parsing.

Design:
  - FeedState: DISCONNECTED → CONNECTING → CONNECTED → SUBSCRIBED
  - Heartbeat: detects stale connections and auto-reconnects
  - Message queue: buffers incoming ticks for consumers
  - Rate limiting: configurable max messages/second

This is the infrastructure layer. Production adapters (Polygon, Alpaca,
Finnhub) would subclass WebSocketFeed and implement _parse_message.

Usage::

    feed = WebSocketFeed(config)
    feed.subscribe(["AAPL", "MSFT"])
    for tick in feed.consume():
        process(tick)
"""

from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.data.websocket_feed")


# ── Contracts ────────────────────────────────────────────────────────────────

class FeedState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SUBSCRIBED = "subscribed"
    ERROR = "error"


class FeedConfig(BaseModel):
    """WebSocket feed configuration."""
    url: str = ""
    api_key: str = ""
    max_reconnect_attempts: int = Field(5, ge=1)
    reconnect_delay_seconds: float = Field(2.0, ge=0.1)
    heartbeat_interval_seconds: float = Field(30.0, ge=1.0)
    max_buffer_size: int = Field(10000, ge=100)
    max_messages_per_second: int = Field(1000, ge=1)


class MarketTick(BaseModel):
    """A single market data tick."""
    ticker: str
    price: float
    volume: int = 0
    bid: float = 0.0
    ask: float = 0.0
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    source: str = ""


class FeedHealth(BaseModel):
    """Health metrics for the feed."""
    state: FeedState = FeedState.DISCONNECTED
    subscribed_tickers: list[str] = Field(default_factory=list)
    messages_received: int = 0
    messages_per_second: float = 0.0
    last_message_at: datetime | None = None
    reconnect_count: int = 0
    buffer_size: int = 0
    uptime_seconds: float = 0.0
    errors: int = 0


# ── Engine ───────────────────────────────────────────────────────────────────

class WebSocketFeed:
    """
    WebSocket market data feed with reconnection and buffering.

    This is the infrastructure layer. For production use, subclass
    and implement:
      - _connect(): establish WebSocket connection
      - _parse_message(raw): parse provider-specific messages
      - _send_subscribe(tickers): send subscription request
    """

    def __init__(self, config: FeedConfig | None = None) -> None:
        self.config = config or FeedConfig()
        self._state: FeedState = FeedState.DISCONNECTED
        self._subscriptions: set[str] = set()
        self._buffer: deque[MarketTick] = deque(
            maxlen=self.config.max_buffer_size,
        )
        self._messages_received: int = 0
        self._errors: int = 0
        self._reconnect_count: int = 0
        self._started_at: float | None = None
        self._last_message_at: float | None = None
        self._rate_window: deque[float] = deque(maxlen=100)

    def connect(self) -> FeedState:
        """Establish connection to WebSocket server."""
        self._state = FeedState.CONNECTING
        self._started_at = time.monotonic()

        try:
            self._connect()
            self._state = FeedState.CONNECTED
            logger.info("WS-FEED: Connected to %s", self.config.url or "feed")
        except Exception as e:
            self._state = FeedState.ERROR
            self._errors += 1
            logger.error("WS-FEED: Connection failed: %s", e)

        return self._state

    def subscribe(self, tickers: list[str]) -> FeedState:
        """Subscribe to market data for tickers."""
        if self._state not in (FeedState.CONNECTED, FeedState.SUBSCRIBED):
            self.connect()

        new_tickers = set(tickers) - self._subscriptions
        if not new_tickers:
            return self._state

        try:
            self._send_subscribe(list(new_tickers))
            self._subscriptions.update(new_tickers)
            self._state = FeedState.SUBSCRIBED
            logger.info(
                "WS-FEED: Subscribed to %d tickers (total: %d)",
                len(new_tickers), len(self._subscriptions),
            )
        except Exception as e:
            self._errors += 1
            logger.error("WS-FEED: Subscribe failed: %s", e)

        return self._state

    def unsubscribe(self, tickers: list[str]) -> None:
        """Unsubscribe from tickers."""
        for t in tickers:
            self._subscriptions.discard(t)
        if not self._subscriptions:
            self._state = FeedState.CONNECTED

    def push_tick(self, tick: MarketTick) -> None:
        """Push a tick into the buffer (used by adapters or for testing)."""
        now = time.monotonic()

        # Rate limiting
        self._rate_window.append(now)
        if len(self._rate_window) >= self.config.max_messages_per_second:
            oldest = self._rate_window[0]
            if now - oldest < 1.0:
                return  # Drop message — rate exceeded

        self._buffer.append(tick)
        self._messages_received += 1
        self._last_message_at = now

    def consume(self, max_items: int = 100) -> list[MarketTick]:
        """Consume buffered ticks."""
        items: list[MarketTick] = []
        for _ in range(min(max_items, len(self._buffer))):
            items.append(self._buffer.popleft())
        return items

    def get_latest(self, ticker: str) -> MarketTick | None:
        """Get latest tick for a specific ticker."""
        for tick in reversed(self._buffer):
            if tick.ticker == ticker:
                return tick
        return None

    def get_health(self) -> FeedHealth:
        """Get feed health metrics."""
        now = time.monotonic()
        uptime = now - self._started_at if self._started_at else 0.0

        # Messages per second (over last 100 messages)
        mps = 0.0
        if len(self._rate_window) >= 2:
            time_span = self._rate_window[-1] - self._rate_window[0]
            if time_span > 0:
                mps = len(self._rate_window) / time_span

        return FeedHealth(
            state=self._state,
            subscribed_tickers=sorted(self._subscriptions),
            messages_received=self._messages_received,
            messages_per_second=round(mps, 1),
            last_message_at=(
                datetime.now(timezone.utc)
                if self._last_message_at else None
            ),
            reconnect_count=self._reconnect_count,
            buffer_size=len(self._buffer),
            uptime_seconds=round(uptime, 1),
            errors=self._errors,
        )

    def check_heartbeat(self) -> bool:
        """Check if feed is alive (received data recently)."""
        if self._last_message_at is None:
            return False
        elapsed = time.monotonic() - self._last_message_at
        return elapsed < self.config.heartbeat_interval_seconds

    def reconnect(self) -> FeedState:
        """Attempt reconnection."""
        self._reconnect_count += 1
        if self._reconnect_count > self.config.max_reconnect_attempts:
            self._state = FeedState.ERROR
            logger.error("WS-FEED: Max reconnect attempts exceeded")
            return self._state

        logger.info(
            "WS-FEED: Reconnecting (attempt %d/%d)",
            self._reconnect_count, self.config.max_reconnect_attempts,
        )
        state = self.connect()
        if state == FeedState.CONNECTED and self._subscriptions:
            self.subscribe(list(self._subscriptions))
        return self._state

    def disconnect(self) -> None:
        """Disconnect from feed."""
        self._state = FeedState.DISCONNECTED
        self._subscriptions.clear()
        logger.info("WS-FEED: Disconnected")

    @property
    def is_active(self) -> bool:
        return self._state in (FeedState.CONNECTED, FeedState.SUBSCRIBED)

    # ── Overridable methods ──────────────────────────────────────────────

    def _connect(self) -> None:
        """Establish WebSocket connection (override in subclass)."""
        pass  # Default: simulated connection

    def _send_subscribe(self, tickers: list[str]) -> None:
        """Send subscription request (override in subclass)."""
        pass  # Default: no-op

    def _parse_message(self, raw: dict) -> MarketTick | None:
        """Parse provider message into MarketTick (override in subclass)."""
        return None
