"""
src/engines/market_feed/base.py — Abstract Data Feed Adapter.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable
from src.engines.market_feed.models import FeedConfig, Quote, Bar, TradeUpdate


class DataFeedAdapter(ABC):
    """Abstract interface for real-time market data feeds."""

    def __init__(self, config: FeedConfig):
        self.config = config
        self._connected = False
        self._on_quote: Callable[[Quote], None] | None = None
        self._on_bar: Callable[[Bar], None] | None = None
        self._on_trade: Callable[[TradeUpdate], None] | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def on_quote(self, callback: Callable[[Quote], None]):
        """Register quote callback."""
        self._on_quote = callback

    def on_bar(self, callback: Callable[[Bar], None]):
        """Register bar callback."""
        self._on_bar = callback

    def on_trade(self, callback: Callable[[TradeUpdate], None]):
        """Register trade callback."""
        self._on_trade = callback

    @abstractmethod
    async def connect(self) -> bool:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...

    @abstractmethod
    async def subscribe(self, tickers: list[str]) -> None:
        ...

    @abstractmethod
    async def unsubscribe(self, tickers: list[str]) -> None:
        ...
