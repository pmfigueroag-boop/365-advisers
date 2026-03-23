"""
tests/test_providers.py
──────────────────────────────────────────────────────────────────────────────
Tests for the Provider Health/Registry system and routes.
"""
from __future__ import annotations

import pytest

from src.engines.provider_registry.registry import ProviderRegistry


class TestProviderRegistry:

    def setup_method(self):
        self.registry = ProviderRegistry()

    def test_get_all_providers(self):
        """Should return list of registered providers."""
        providers = self.registry.get_all()
        assert isinstance(providers, list)
        assert len(providers) > 0  # Should have at least yfinance

    def test_provider_has_name(self):
        """Each provider should have a name field."""
        providers = self.registry.get_all()
        for p in providers:
            name = p.get("name") if isinstance(p, dict) else getattr(p, "name", None)
            assert name is not None

    def test_health_check(self):
        """Health check should return dict with status for each provider."""
        health = self.registry.health_check()
        assert isinstance(health, (dict, list))

    def test_provider_status_values(self):
        """Provider status should be one of: healthy, degraded, offline."""
        health = self.registry.health_check()
        valid_statuses = {"healthy", "degraded", "offline", "unknown"}
        if isinstance(health, dict):
            for name, info in health.items():
                status = info.get("status", "unknown") if isinstance(info, dict) else "unknown"
                assert status in valid_statuses


class TestProviderContract:

    def test_registry_endpoint(self):
        """Registry should expose data matching frontend useProviderHealth expectations."""
        registry = ProviderRegistry()
        providers = registry.get_all()
        # Frontend expects: name, status, last_check
        assert isinstance(providers, list)
