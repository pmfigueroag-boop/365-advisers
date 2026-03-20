"""
tests/test_cache_manager.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for CacheManager and _MemoryTTLCache.
"""

import time
import pytest


class TestMemoryTTLCache:
    """Tests for the in-memory TTL cache."""

    def _make_cache(self, ttl: int = 10, max_size: int = 5):
        from src.services.cache_manager import _MemoryTTLCache
        return _MemoryTTLCache("test", ttl, max_size)

    def test_set_and_get(self):
        cache = self._make_cache()
        cache.set("FOO", {"value": 42})
        result = cache.get("FOO")
        assert result is not None
        assert result["value"] == 42

    def test_get_case_insensitive(self):
        cache = self._make_cache()
        cache.set("bar", {"value": 1})
        assert cache.get("BAR") is not None
        assert cache.get("bar") is not None

    def test_get_returns_none_for_missing_key(self):
        cache = self._make_cache()
        assert cache.get("NONEXISTENT") is None

    def test_ttl_expiration(self):
        cache = self._make_cache(ttl=0)  # Expire immediately
        cache.set("FOO", {"value": 1})
        time.sleep(0.01)
        assert cache.get("FOO") is None

    def test_invalidate_removes_key(self):
        cache = self._make_cache()
        cache.set("FOO", {"value": 1})
        assert cache.invalidate("FOO") is True
        assert cache.get("FOO") is None

    def test_invalidate_returns_false_for_missing(self):
        cache = self._make_cache()
        assert cache.invalidate("NONEXISTENT") is False

    def test_max_size_eviction(self):
        cache = self._make_cache(max_size=2)
        cache.set("A", {"v": 1})
        cache.set("B", {"v": 2})
        cache.set("C", {"v": 3})  # Should evict oldest (A)
        assert cache.get("A") is None
        assert cache.get("B") is not None
        assert cache.get("C") is not None

    def test_status_returns_valid_entries(self):
        cache = self._make_cache()
        cache.set("X", {"v": 1})
        cache.set("Y", {"v": 2})
        entries = cache.status()
        assert len(entries) == 2
        keys = {e["key"] for e in entries}
        assert "X" in keys
        assert "Y" in keys

    def test_status_filters_expired(self):
        cache = self._make_cache(ttl=0)
        cache.set("STALE", {"v": 1})
        time.sleep(0.01)
        entries = cache.status()
        assert len(entries) == 0

    def test_set_adds_timestamp(self):
        cache = self._make_cache()
        cache.set("TS", {"v": 1})
        result = cache.get("TS")
        assert "_ts" in result
        assert "_cached_at" in result


class TestAnalysisMemoryCache:
    """Tests for the specialized analysis cache."""

    def _make_cache(self):
        from src.services.cache_manager import _AnalysisMemoryCache
        return _AnalysisMemoryCache()

    def test_set_and_get(self):
        cache = self._make_cache()
        cache.set("AAPL", {"test": True}, agents=["a1"], dalio={"pos": "BUY"})
        result = cache.get("AAPL")
        assert result is not None
        assert result["agents"] == ["a1"]
        assert result["dalio"]["pos"] == "BUY"

    def test_ticker_info_cache(self):
        cache = self._make_cache()
        cache.set_ticker_info("MSFT", {"name": "Microsoft"})
        info = cache.get_ticker_info("MSFT")
        assert info is not None
        assert info["name"] == "Microsoft"

    def test_ticker_info_case_insensitive(self):
        cache = self._make_cache()
        cache.set_ticker_info("goog", {"name": "Google"})
        assert cache.get_ticker_info("GOOG") is not None


class TestCacheManager:
    """Tests for the unified CacheManager facade."""

    def test_cache_manager_has_all_subsystems(self):
        from src.services.cache_manager import CacheManager
        cm = CacheManager()
        assert hasattr(cm, "analysis")
        assert hasattr(cm, "decision")
        assert hasattr(cm, "fundamental")
        assert hasattr(cm, "technical")

    def test_status_all_returns_dict(self):
        from src.services.cache_manager import CacheManager
        cm = CacheManager()
        status = cm.status_all()
        assert "backend" in status
        assert "analysis" in status
        assert "decision" in status

    def test_default_backend_is_memory(self):
        from src.services.cache_manager import CacheManager
        cm = CacheManager()
        # Without Redis running, should be memory
        assert cm._backend in ("memory", "redis")
