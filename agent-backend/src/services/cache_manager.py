"""
src/services/cache_manager.py
─────────────────────────────────────────────────────────────────────────────
Unified cache facade — consolidates all 4 cache systems into one interface.
Fixes audit finding #6.
"""

import time
import logging
from datetime import datetime, timezone
from src.data.database import FundamentalDBCache, TechnicalDBCache

logger = logging.getLogger("365advisers.cache")


class _MemoryTTLCache:
    """Generic in-memory TTL cache with lazy eviction."""

    def __init__(self, name: str, ttl_seconds: int):
        self.name = name
        self.ttl = ttl_seconds
        self._store: dict[str, dict] = {}

    def get(self, key: str) -> dict | None:
        entry = self._store.get(key.upper())
        if entry and (time.time() - entry["_ts"]) < self.ttl:
            return entry
        if entry:
            del self._store[key.upper()]
        return None

    def set(self, key: str, data: dict):
        data["_ts"] = time.time()
        data["_cached_at"] = datetime.fromtimestamp(time.time(), tz=timezone.utc).isoformat()
        self._store[key.upper()] = data
        logger.info(f"[{self.name}] Stored {key.upper()} (TTL {self.ttl}s)")

    def invalidate(self, key: str) -> bool:
        return self._store.pop(key.upper(), None) is not None

    def status(self) -> list[dict]:
        now = time.time()
        result = []
        for k, entry in list(self._store.items()):
            age = now - entry["_ts"]
            if age < self.ttl:
                result.append({
                    "key": k, "age_s": round(age),
                    "expires_in_s": round(self.ttl - age),
                })
            else:
                del self._store[k]
        return result


class _AnalysisMemoryCache(_MemoryTTLCache):
    """
    Specialized analysis cache with backward-compatible interface.
    Supports: set(ticker, data_ready, agents, dalio) and get_ticker_info/set_ticker_info.
    """
    TTL_ANALYSIS = 300
    TTL_TICKER = 900

    def __init__(self):
        super().__init__("AnalysisCache", self.TTL_ANALYSIS)
        self._ticker_store: dict[str, dict] = {}

    def set(self, key: str, data_ready_or_dict=None, agents=None, dalio=None):  # type: ignore[override]
        """Backward-compatible: set(ticker, data_ready, agents, dalio)"""
        now = time.time()
        entry = {
            "data_ready": data_ready_or_dict,
            "agents": agents or [],
            "dalio": dalio or {},
            "cached_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            "ts": now,
            "_ts": now,
        }
        self._store[key.upper()] = entry
        logger.info(f"[AnalysisCache] Stored {key.upper()} (TTL {self.ttl}s)")

    def get(self, key: str) -> dict | None:
        entry = self._store.get(key.upper())
        if entry and (time.time() - entry.get("ts", entry.get("_ts", 0))) < self.ttl:
            return entry
        if entry:
            del self._store[key.upper()]
        return None

    def status(self) -> list[dict]:
        now = time.time()
        result = []
        for t, entry in list(self._store.items()):
            ts = entry.get("ts", entry.get("_ts", 0))
            age = now - ts
            if age < self.ttl:
                result.append({
                    "ticker": t,
                    "cached_at": entry.get("cached_at", ""),
                    "age_s": round(age),
                    "expires_in_s": round(self.ttl - age),
                })
            else:
                del self._store[t]
        return result

    # ---- Ticker-info cache (separate store) ----
    def get_ticker_info(self, ticker: str) -> dict | None:
        entry = self._ticker_store.get(ticker.upper())
        if entry and (time.time() - entry["ts"]) < self.TTL_TICKER:
            return entry["data"]
        if entry:
            del self._ticker_store[ticker.upper()]
        return None

    def set_ticker_info(self, ticker: str, data: dict):
        self._ticker_store[ticker.upper()] = {"data": data, "ts": time.time()}


class CacheManager:
    """
    Single facade for all caching in 365 Advisers.

    Subsystems:
      - analysis: in-memory, TTL 5min (legacy LangGraph results + ticker info)
      - decision: in-memory, TTL 15min (CIO memo results)
      - fundamental: DB-backed, TTL 24h (fundamental engine events)
      - technical: DB-backed, TTL 15min (technical engine data)
    """

    def __init__(self):
        self.analysis = _AnalysisMemoryCache()
        self.decision = _MemoryTTLCache("DecisionCache", 900)
        self.fundamental = FundamentalDBCache()
        self.technical = TechnicalDBCache()

    def status_all(self) -> dict:
        return {
            "analysis": self.analysis.status(),
            "decision": self.decision.status(),
        }

    def invalidate_all(self, ticker: str) -> dict:
        return {
            "analysis": self.analysis.invalidate(ticker),
            "decision": self.decision.invalidate(ticker),
            "fundamental": self.fundamental.invalidate(ticker),
            "technical": self.technical.invalidate(ticker),
        }


# Singleton instance
cache_manager = CacheManager()

