"""
tests/test_prompt_cache.py
─────────────────────────────────────────────────────────────────────────────
Tests for prompt caching system.
"""

import pytest


class TestPromptCache:
    def setup_method(self):
        from src.services.prompt_cache import clear_cache
        clear_cache()

    def test_cache_miss_then_hit(self):
        from src.services.prompt_cache import get_cached_system_prompt, get_cache_stats
        # First call = miss
        p1 = get_cached_system_prompt("Value Agent", "Graham", "Valuation")
        stats = get_cache_stats()
        assert stats["cache_misses"] == 1

        # Second call = hit
        p2 = get_cached_system_prompt("Value Agent", "Graham", "Valuation")
        stats = get_cache_stats()
        assert stats["cache_hits"] == 1
        assert p1 == p2

    def test_different_agents_different_prompts(self):
        from src.services.prompt_cache import get_cached_system_prompt
        p1 = get_cached_system_prompt("Value Agent", "Graham", "Valuation")
        p2 = get_cached_system_prompt("Quality Agent", "Munger", "Quality")
        assert p1 != p2

    def test_prompt_contains_agent_identity(self):
        from src.services.prompt_cache import get_cached_system_prompt
        prompt = get_cached_system_prompt("Value Agent", "Graham", "Valuation")
        assert "Value Agent" in prompt
        assert "Graham" in prompt
        assert "SPANISH" in prompt  # Output language

    def test_build_agent_prompt_with_cache(self):
        from src.services.prompt_cache import build_agent_prompt_with_cache
        system, user = build_agent_prompt_with_cache(
            "AAPL", "Value Agent", "Graham", "Valuation",
            {"pe_ratio": 25.0, "pb_ratio": 8.5},
        )
        assert "Value Agent" in system
        assert "AAPL" in user
        assert "pe_ratio" in user

    def test_cache_stats_token_savings(self):
        from src.services.prompt_cache import get_cached_system_prompt, get_cache_stats
        # Generate 5 cache hits
        for _ in range(5):
            get_cached_system_prompt("Value Agent", "Graham", "Valuation")
        stats = get_cache_stats()
        assert stats["estimated_tokens_saved"] > 0
        assert stats["hit_rate_pct"] > 0

    def test_clear_cache(self):
        from src.services.prompt_cache import get_cached_system_prompt, clear_cache, get_cache_stats
        get_cached_system_prompt("Agent", "FW", "Focus")
        clear_cache()
        stats = get_cache_stats()
        assert stats["cached_prompts"] == 0
        assert stats["cache_hits"] == 0


class TestRedisCache:
    def test_redis_cache_init_without_server(self):
        """RedisTTLCache should handle missing Redis gracefully."""
        from src.services.redis_cache import RedisTTLCache
        cache = RedisTTLCache("test", 60)
        result = cache.get("nonexistent")
        assert result is None

    def test_redis_available_check(self):
        from src.services.redis_cache import is_redis_available
        # Redis likely not running in test environment
        result = is_redis_available()
        assert isinstance(result, bool)

    def test_redis_rate_limiter_no_server(self):
        """Rate limiter should allow requests when Redis is down."""
        from src.services.redis_cache import RedisRateLimiter
        limiter = RedisRateLimiter(max_requests=10, window_seconds=60)
        allowed, remaining = limiter.is_allowed("test-client")
        assert allowed is True
        assert remaining == 10
