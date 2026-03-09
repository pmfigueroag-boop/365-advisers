"""
src/engines/market_feed/subscription_manager.py — Subscription tracking.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from src.engines.market_feed.models import Subscription

logger = logging.getLogger("365advisers.feed.subscriptions")


class SubscriptionManager:
    """
    Track active symbol subscriptions with reference counting.

    Multiple clients can subscribe to the same symbol;
    unsubscription only happens when ref count reaches 0.
    """

    MAX_SUBSCRIPTIONS = 500

    def __init__(self):
        self._subs: dict[str, Subscription] = {}
        self._ref_count: dict[str, int] = {}

    def subscribe(self, ticker: str, feed_source: str = "simulated") -> bool:
        """Add subscription. Returns True if new, False if already subscribed."""
        t = ticker.upper()
        if len(self._subs) >= self.MAX_SUBSCRIPTIONS and t not in self._subs:
            logger.warning("Max subscriptions (%d) reached", self.MAX_SUBSCRIPTIONS)
            return False

        if t not in self._subs:
            self._subs[t] = Subscription(ticker=t, feed_source=feed_source)
            self._ref_count[t] = 1
            return True
        else:
            self._ref_count[t] = self._ref_count.get(t, 0) + 1
            return False

    def unsubscribe(self, ticker: str) -> bool:
        """Decrement ref count. Returns True if fully unsubscribed."""
        t = ticker.upper()
        if t not in self._ref_count:
            return False
        self._ref_count[t] -= 1
        if self._ref_count[t] <= 0:
            del self._ref_count[t]
            if t in self._subs:
                self._subs[t].active = False
                del self._subs[t]
            return True
        return False

    def get_active_tickers(self) -> list[str]:
        return sorted(self._subs.keys())

    def get_subscription(self, ticker: str) -> Subscription | None:
        return self._subs.get(ticker.upper())

    def is_subscribed(self, ticker: str) -> bool:
        return ticker.upper() in self._subs

    @property
    def count(self) -> int:
        return len(self._subs)

    def get_all(self) -> list[Subscription]:
        return list(self._subs.values())
