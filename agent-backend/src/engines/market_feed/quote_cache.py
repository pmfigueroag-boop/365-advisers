"""
src/engines/market_feed/quote_cache.py — In-memory quote cache with bar aggregation.
"""
from __future__ import annotations
import logging
from collections import deque
from datetime import datetime, timezone
from src.engines.market_feed.models import Quote, Bar

logger = logging.getLogger("365advisers.feed.cache")


class QuoteCache:
    """
    In-memory cache for real-time quotes.

    Features:
    - Last quote per ticker (O(1) lookup)
    - Quote history (configurable depth)
    - 1-minute bar aggregation from trades
    - Snapshot of all quotes
    """

    def __init__(self, history_depth: int = 100):
        self._latest: dict[str, Quote] = {}
        self._history: dict[str, deque[Quote]] = {}
        self._bars: dict[str, list[Bar]] = {}
        self._current_bar: dict[str, dict] = {}
        self._depth = history_depth
        self._total_updates = 0

    def update(self, quote: Quote) -> None:
        """Update cache with new quote."""
        ticker = quote.ticker
        self._latest[ticker] = quote
        self._total_updates += 1

        if ticker not in self._history:
            self._history[ticker] = deque(maxlen=self._depth)
        self._history[ticker].append(quote)

        # Update current bar
        self._update_bar(quote)

    def get_quote(self, ticker: str) -> Quote | None:
        """Get latest quote for a ticker."""
        return self._latest.get(ticker.upper())

    def get_price(self, ticker: str) -> float:
        """Get latest price (last trade or mid)."""
        q = self._latest.get(ticker.upper())
        if not q:
            return 0.0
        return q.last if q.last > 0 else q.mid

    def get_history(self, ticker: str, limit: int = 50) -> list[Quote]:
        """Get recent quote history."""
        hist = self._history.get(ticker.upper())
        if not hist:
            return []
        return list(hist)[-limit:]

    def get_bars(self, ticker: str, limit: int = 60) -> list[Bar]:
        """Get recent 1-min bars."""
        bars = self._bars.get(ticker.upper(), [])
        return bars[-limit:]

    def snapshot(self) -> dict[str, dict]:
        """Snapshot of all latest quotes."""
        return {t: q.model_dump() for t, q in self._latest.items()}

    def get_all_tickers(self) -> list[str]:
        """List all tickers with data."""
        return sorted(self._latest.keys())

    @property
    def total_updates(self) -> int:
        return self._total_updates

    def _update_bar(self, quote: Quote):
        """Aggregate quotes into 1-minute bars."""
        ticker = quote.ticker
        price = quote.last if quote.last > 0 else quote.mid
        if price <= 0:
            return

        now = datetime.now(timezone.utc)
        minute_key = now.strftime("%Y%m%d%H%M")

        if ticker not in self._current_bar:
            self._current_bar[ticker] = {"key": minute_key, "open": price, "high": price, "low": price, "close": price, "volume": 0}

        bar = self._current_bar[ticker]
        if bar["key"] != minute_key:
            # New minute — save completed bar
            completed = Bar(
                ticker=ticker,
                open=bar["open"], high=bar["high"],
                low=bar["low"], close=bar["close"],
                volume=bar["volume"],
            )
            if ticker not in self._bars:
                self._bars[ticker] = []
            self._bars[ticker].append(completed)
            # Keep last 500 bars
            if len(self._bars[ticker]) > 500:
                self._bars[ticker] = self._bars[ticker][-500:]

            self._current_bar[ticker] = {"key": minute_key, "open": price, "high": price, "low": price, "close": price, "volume": 0}
        else:
            bar["high"] = max(bar["high"], price)
            bar["low"] = min(bar["low"], price)
            bar["close"] = price
            bar["volume"] += quote.volume
