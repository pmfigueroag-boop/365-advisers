"""
src/engines/market_feed/models.py — Real-time market data contracts.
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class FeedType(str, Enum):
    SIMULATED = "simulated"
    ALPACA = "alpaca"
    POLYGON = "polygon"


class FeedConfig(BaseModel):
    feed_type: FeedType = FeedType.SIMULATED
    api_key: str = ""
    api_secret: str = ""
    base_url: str = ""
    symbols: list[str] = Field(default_factory=list)
    tick_interval_ms: int = 1000  # simulated feed tick rate


class Quote(BaseModel):
    ticker: str
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    mid: float = 0.0
    spread: float = 0.0
    volume: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context):
        if self.bid > 0 and self.ask > 0:
            self.mid = round((self.bid + self.ask) / 2, 4)
            self.spread = round(self.ask - self.bid, 4)


class Bar(BaseModel):
    ticker: str
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    vwap: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    period: str = "1min"


class TradeUpdate(BaseModel):
    ticker: str
    price: float
    size: int = 0
    exchange: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Subscription(BaseModel):
    ticker: str
    feed_source: str = "simulated"
    subscribed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True


class FeedHealth(BaseModel):
    feed_type: str = "simulated"
    connected: bool = False
    active_subscriptions: int = 0
    quotes_received: int = 0
    last_quote_at: datetime | None = None
    uptime_seconds: float = 0.0
