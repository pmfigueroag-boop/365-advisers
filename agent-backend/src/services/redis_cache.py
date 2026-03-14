"""
src/services/redis_cache.py
─────────────────────────────────────────────────────────────────────────────
Redis-backed TTL cache adapter — drop-in replacement for _MemoryTTLCache.

Provides shared caching across multiple workers/processes via Redis.
Falls back gracefully to in-memory cache if Redis is unavailable.
"""

from __future__ import annotations

import json
import time
import logging
from datetime import datetime, timezone

logger = logging.getLogger("365advisers.cache.redis")

_redis_client = None
_redis_available = False


def _get_redis():
    """Lazy Redis client initialization."""
    global _redis_client, _redis_available

    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        from src.config import get_settings
        settings = get_settings()
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=2,
            socket_connect_timeout=2,
            retry_on_timeout=True,
        )
        _redis_client.ping()
        _redis_available = True
        logger.info(f"Redis connected: {settings.REDIS_URL}")
        return _redis_client
    except Exception as exc:
        logger.warning(f"Redis unavailable, falling back to memory: {exc}")
        _redis_available = False
        _redis_client = None
        return None


class RedisTTLCache:
    """
    Redis-backed TTL cache with the same interface as _MemoryTTLCache.

    Keys are prefixed with cache name to avoid collisions.
    """

    def __init__(self, name: str, ttl_seconds: int, max_size: int = 500):
        self.name = name
        self.ttl = ttl_seconds
        self.max_size = max_size
        self._prefix = f"365adv:{name}:"

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key.upper()}"

    def get(self, key: str) -> dict | None:
        client = _get_redis()
        if client is None:
            return None
        try:
            raw = client.get(self._key(key))
            if raw:
                return json.loads(raw)
            return None
        except Exception as exc:
            logger.warning(f"[{self.name}] Redis GET failed: {exc}")
            return None

    def set(self, key: str, data: dict):
        client = _get_redis()
        if client is None:
            return
        try:
            data["_ts"] = time.time()
            data["_cached_at"] = datetime.now(timezone.utc).isoformat()
            client.setex(
                self._key(key),
                self.ttl,
                json.dumps(data, default=str),
            )
            logger.info(f"[{self.name}] Redis SET {key.upper()} (TTL {self.ttl}s)")
        except Exception as exc:
            logger.warning(f"[{self.name}] Redis SET failed: {exc}")

    def invalidate(self, key: str) -> bool:
        client = _get_redis()
        if client is None:
            return False
        try:
            return bool(client.delete(self._key(key)))
        except Exception:
            return False

    def status(self) -> list[dict]:
        client = _get_redis()
        if client is None:
            return []
        try:
            keys = client.keys(f"{self._prefix}*")
            result = []
            for k in keys[:50]:  # Limit to 50 for performance
                ttl_remaining = client.ttl(k)
                if ttl_remaining > 0:
                    ticker = k.replace(self._prefix, "")
                    result.append({
                        "key": ticker,
                        "expires_in_s": ttl_remaining,
                        "age_s": self.ttl - ttl_remaining,
                    })
            return result
        except Exception:
            return []


class RedisRateLimiter:
    """
    Distributed rate limiter using Redis sliding window.

    Replaces the in-memory per-worker rate limiter for multi-worker deployments.
    """

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._prefix = "365adv:ratelimit:"

    def is_allowed(self, client_id: str) -> tuple[bool, int]:
        """
        Check if a request is allowed for the given client.

        Returns:
            (allowed: bool, remaining: int)
        """
        client = _get_redis()
        if client is None:
            return True, self.max_requests  # Allow if Redis is down

        key = f"{self._prefix}{client_id}"
        now = time.time()
        window_start = now - self.window

        try:
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)  # Remove old entries
            pipe.zadd(key, {str(now): now})               # Add current request
            pipe.zcard(key)                                # Count requests
            pipe.expire(key, self.window)                  # Set TTL
            _, _, count, _ = pipe.execute()

            remaining = max(0, self.max_requests - count)
            return count <= self.max_requests, remaining
        except Exception:
            return True, self.max_requests


def is_redis_available() -> bool:
    """Check if Redis is available (for health checks)."""
    client = _get_redis()
    if client is None:
        return False
    try:
        return client.ping()
    except Exception:
        return False
