"""
src/data/cache.py
──────────────────────────────────────────────────────────────────────────────
Generic TTL cache for market data with freshness metadata.

Provides transparent caching with data source tracking so the frontend
can display whether data is live or cached, and how old it is.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("365advisers.data.cache")


# ── TTL defaults (seconds) ──────────────────────────────────────────────────

TTL_FUNDAMENTAL = 30 * 60   # 30 minutes — ratios don't change intraday
TTL_TECHNICAL = 5 * 60      # 5 minutes  — price/RSI need freshness
TTL_SIGNALS = 10 * 60       # 10 minutes — depends on fund + tech


# ── Freshness metadata ──────────────────────────────────────────────────────

@dataclass
class FreshnessInfo:
    """Metadata about data freshness for a single domain."""
    source: str                       # "live" | "cached"
    fetched_at: str                   # ISO timestamp
    age_seconds: int                  # seconds since fetch
    ttl_seconds: int                  # configured TTL
    domain: str = ""                  # "fundamental" | "technical" | "signals"

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "fetched_at": self.fetched_at,
            "age_seconds": self.age_seconds,
            "ttl_seconds": self.ttl_seconds,
            "domain": self.domain,
        }


@dataclass
class CacheEntry:
    """A single cached data item with metadata."""
    data: Any
    fetched_at: float               # time.time() when fetched
    ttl_seconds: int                # TTL in seconds
    domain: str = ""                # "fundamental" | "technical"

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.fetched_at) > self.ttl_seconds

    @property
    def age_seconds(self) -> int:
        return int(time.time() - self.fetched_at)

    @property
    def freshness(self) -> FreshnessInfo:
        return FreshnessInfo(
            source="cached",
            fetched_at=datetime.fromtimestamp(
                self.fetched_at, tz=timezone.utc
            ).isoformat(),
            age_seconds=self.age_seconds,
            ttl_seconds=self.ttl_seconds,
            domain=self.domain,
        )


class DataCache:
    """
    Thread-safe in-memory TTL cache for market data.

    Keys are (ticker, domain) tuples.
    Expired entries are lazily evicted on access.

    Usage::

        cache = DataCache()
        entry = cache.get("AAPL", "fundamental")
        if entry is None:
            data = fetch_fundamental_data("AAPL")
            cache.set("AAPL", "fundamental", data, ttl_seconds=TTL_FUNDAMENTAL)
    """

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], CacheEntry] = {}

    def get(self, ticker: str, domain: str) -> CacheEntry | None:
        """Get cached entry if exists and not expired."""
        key = (ticker.upper(), domain)
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.is_expired:
            del self._store[key]
            logger.debug(f"CACHE: expired {key} (age={entry.age_seconds}s)")
            return None
        return entry

    def set(
        self,
        ticker: str,
        domain: str,
        data: Any,
        ttl_seconds: int,
    ) -> CacheEntry:
        """Store data with TTL. Returns the created entry."""
        key = (ticker.upper(), domain)
        entry = CacheEntry(
            data=data,
            fetched_at=time.time(),
            ttl_seconds=ttl_seconds,
            domain=domain,
        )
        self._store[key] = entry
        logger.debug(f"CACHE: stored {key} (ttl={ttl_seconds}s)")
        return entry

    def invalidate(self, ticker: str, domain: str | None = None) -> int:
        """
        Invalidate cache entries for a ticker.

        If domain is None, invalidates ALL domains for that ticker.
        Returns the number of entries removed.
        """
        ticker_upper = ticker.upper()
        removed = 0
        keys_to_remove = []
        for key in self._store:
            if key[0] == ticker_upper:
                if domain is None or key[1] == domain:
                    keys_to_remove.append(key)
        for key in keys_to_remove:
            del self._store[key]
            removed += 1
        if removed:
            logger.info(f"CACHE: invalidated {removed} entries for {ticker_upper}")
        return removed

    def stats(self) -> dict:
        """Return cache statistics."""
        total = len(self._store)
        expired = sum(1 for e in self._store.values() if e.is_expired)
        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
        }

    def make_live_freshness(self, domain: str, ttl_seconds: int) -> FreshnessInfo:
        """Create a FreshnessInfo for a fresh (non-cached) fetch."""
        return FreshnessInfo(
            source="live",
            fetched_at=datetime.now(timezone.utc).isoformat(),
            age_seconds=0,
            ttl_seconds=ttl_seconds,
            domain=domain,
        )


# ── Module-level singleton ──────────────────────────────────────────────────

_cache = DataCache()


def get_cache() -> DataCache:
    """Get the module-level cache singleton."""
    return _cache
