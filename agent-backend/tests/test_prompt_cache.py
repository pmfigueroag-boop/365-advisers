"""
tests/test_prompt_cache.py
─────────────────────────────────────────────────────────────────────────────
Tests for prompt caching service.
"""

import pytest


class TestPromptCache:
    """Tests for the prompt cache module."""

    def setup_method(self):
        from src.services.prompt_cache import clear_cache
        clear_cache()

    def test_get_cached_system_prompt_returns_string(self):
        from src.services.prompt_cache import get_cached_system_prompt
        result = get_cached_system_prompt("Value Agent", "Graham/Buffett", "intrinsic value")
        assert isinstance(result, str)
        assert "Value Agent" in result

    def test_same_inputs_return_same_prompt(self):
        from src.services.prompt_cache import get_cached_system_prompt
        p1 = get_cached_system_prompt("A", "B", "C")
        p2 = get_cached_system_prompt("A", "B", "C")
        assert p1 is p2  # Same object reference (cached)

    def test_different_inputs_return_different_prompts(self):
        from src.services.prompt_cache import get_cached_system_prompt
        p1 = get_cached_system_prompt("A", "B", "C")
        p2 = get_cached_system_prompt("X", "Y", "Z")
        assert p1 != p2

    def test_cache_stats_track_hits(self):
        from src.services.prompt_cache import get_cached_system_prompt, get_cache_stats
        get_cached_system_prompt("A", "B", "C")  # miss
        get_cached_system_prompt("A", "B", "C")  # hit
        stats = get_cache_stats()
        assert stats["cache_hits"] >= 1
        assert stats["cache_misses"] >= 1
        assert stats["cached_prompts"] >= 1

    def test_cache_stats_hit_rate(self):
        from src.services.prompt_cache import get_cached_system_prompt, get_cache_stats
        get_cached_system_prompt("A", "B", "C")  # miss
        get_cached_system_prompt("A", "B", "C")  # hit
        get_cached_system_prompt("A", "B", "C")  # hit
        stats = get_cache_stats()
        assert stats["hit_rate_pct"] > 0

    def test_clear_cache_resets_everything(self):
        from src.services.prompt_cache import (
            get_cached_system_prompt, get_cache_stats, clear_cache,
        )
        get_cached_system_prompt("A", "B", "C")
        clear_cache()
        stats = get_cache_stats()
        assert stats["cached_prompts"] == 0
        assert stats["cache_hits"] == 0

    def test_build_agent_prompt_with_cache(self):
        from src.services.prompt_cache import build_agent_prompt_with_cache
        system, user = build_agent_prompt_with_cache(
            ticker="AAPL",
            agent_name="Test Agent",
            framework="DCF",
            focus="valuation",
            data={"pe_ratio": 25.0},
        )
        assert isinstance(system, str)
        assert "Test Agent" in system
        assert "AAPL" in user

    def test_estimated_tokens_saved(self):
        from src.services.prompt_cache import get_cached_system_prompt, get_cache_stats
        get_cached_system_prompt("A", "B", "C")  # miss
        for _ in range(5):
            get_cached_system_prompt("A", "B", "C")  # 5 hits
        stats = get_cache_stats()
        assert stats["estimated_tokens_saved"] > 0
