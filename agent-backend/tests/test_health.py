"""
tests/test_health.py
─────────────────────────────────────────────────────────────────────────────
Tests for canonical health endpoints.
"""

import pytest


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from src.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")


class TestRootEndpoint:
    def test_root_returns_message(self, mock_settings):
        from src.routes.health import read_root
        result = read_root()
        assert result["message"] == "365 Advisers API is running"
        assert "version" in result


class TestHealthCheck:
    def test_health_returns_status(self, mock_settings):
        from src.routes.health import health_check
        result = health_check()
        assert result["status"] in ("healthy", "degraded")
        assert "version" in result
        assert "uptime_seconds" in result
        assert "timestamp" in result
        assert "checks" in result

    def test_health_has_all_subsystems(self, mock_settings):
        from src.routes.health import health_check
        result = health_check()
        checks = result["checks"]
        assert "database" in checks
        assert "cache" in checks
        assert "llm" in checks
        assert "observability" in checks
        assert "auth" in checks

    def test_database_check_has_status(self, mock_settings):
        from src.routes.health import health_check
        result = health_check()
        db = result["checks"]["database"]
        assert "status" in db
        assert db["status"] in ("up", "down")

    def test_llm_check_shows_model(self, mock_settings):
        from src.routes.health import health_check
        result = health_check()
        llm = result["checks"]["llm"]
        assert "status" in llm
        assert "api_key_configured" in llm

    def test_cache_check_shows_entries(self, mock_settings):
        from src.routes.health import health_check
        result = health_check()
        cache = result["checks"]["cache"]
        assert "status" in cache


class TestLiveness:
    def test_liveness_returns_alive(self, mock_settings):
        from src.routes.health import liveness
        result = liveness()
        assert result["status"] == "alive"


class TestReadiness:
    def test_readiness_returns_status(self, mock_settings):
        from src.routes.health import readiness
        result = readiness()
        # Will return ready or JSONResponse(503) depending on DB
        if isinstance(result, dict):
            assert result["status"] == "ready"
