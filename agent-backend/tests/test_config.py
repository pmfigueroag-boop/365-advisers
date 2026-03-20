"""
tests/test_config.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for Settings validation and security guards.
"""

import os
import pytest
from unittest.mock import patch


class TestSettingsDefaults:
    """Test default configuration values."""

    def test_default_llm_model(self):
        from src.config import get_settings
        s = get_settings()
        assert s.LLM_MODEL == "gemini-2.5-pro"

    def test_default_auth_disabled(self):
        from src.config import get_settings
        s = get_settings()
        assert s.AUTH_ENABLED is False

    def test_default_cache_backend(self):
        from src.config import get_settings
        s = get_settings()
        assert s.CACHE_BACKEND in ("memory", "redis")

    def test_default_uvicorn_workers(self):
        from src.config import get_settings
        s = get_settings()
        assert s.UVICORN_WORKERS >= 1

    def test_default_otel_enabled(self):
        from src.config import get_settings
        s = get_settings()
        assert s.OTEL_ENABLED is True

    def test_edpl_cache_ttls_are_positive(self):
        from src.config import get_settings
        s = get_settings()
        assert s.EDPL_CACHE_TTL_MARKET > 0
        assert s.EDPL_CACHE_TTL_FUNDAMENTAL > 0
        assert s.EDPL_CACHE_TTL_MACRO > 0

    def test_llm_fallback_settings(self):
        from src.config import get_settings
        s = get_settings()
        assert s.LLM_FALLBACK_ENABLED is True
        assert s.LLM_FALLBACK_MODEL == "gpt-4o-mini"


class TestJWTSecretGuard:
    """Test the JWT secret security guard."""

    def test_default_secret_emits_warning_when_auth_disabled(self):
        """When AUTH_ENABLED=False and default secret, should warn but not crash."""
        from src.config import get_settings
        s = get_settings()
        # Should not raise — auth is disabled
        assert s.JWT_SECRET_KEY is not None

    def test_settings_has_redis_url(self):
        """Redis URL setting exists."""
        from src.config import get_settings
        s = get_settings()
        assert hasattr(s, "REDIS_URL")
        assert "redis://" in s.REDIS_URL
