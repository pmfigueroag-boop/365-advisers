"""
tests/test_auth.py
─────────────────────────────────────────────────────────────────────────────
Tests for the JWT authentication and authorization layer.
"""

import pytest
import time
from datetime import timedelta
from unittest.mock import patch

# ── Helpers ───────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Clear lru_cache between tests."""
    from src.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_settings(monkeypatch):
    """Ensure test settings."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("AUTH_ENABLED", "True")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing")
    monkeypatch.setenv("JWT_EXPIRATION_MINUTES", "60")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv(
        "ADMIN_PASSWORD_HASH",
        "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918",
    )


# ── Models ────────────────────────────────────────────────────────────────────


class TestRole:
    def test_role_values(self):
        from src.auth.models import Role
        assert Role.VIEWER.value == "viewer"
        assert Role.ANALYST.value == "analyst"
        assert Role.ADMIN.value == "admin"

    def test_role_hierarchy(self):
        from src.auth.models import Role, role_has_access
        assert role_has_access(Role.ADMIN, Role.VIEWER) is True
        assert role_has_access(Role.ADMIN, Role.ANALYST) is True
        assert role_has_access(Role.ADMIN, Role.ADMIN) is True
        assert role_has_access(Role.ANALYST, Role.VIEWER) is True
        assert role_has_access(Role.ANALYST, Role.ADMIN) is False
        assert role_has_access(Role.VIEWER, Role.ANALYST) is False
        assert role_has_access(Role.VIEWER, Role.VIEWER) is True


class TestUser:
    def test_user_creation(self):
        from src.auth.models import Role, User
        user = User(username="testuser", role=Role.ANALYST)
        assert user.username == "testuser"
        assert user.role == Role.ANALYST


# ── JWT ───────────────────────────────────────────────────────────────────────


class TestJWT:
    def test_create_and_decode_roundtrip(self, mock_settings):
        from src.auth.jwt import create_access_token, decode_token
        from src.auth.models import Role

        token = create_access_token("testuser", Role.ANALYST)
        assert isinstance(token, str)
        assert len(token) > 20

        payload = decode_token(token)
        assert payload.sub == "testuser"
        assert payload.role == Role.ANALYST

    def test_token_with_custom_expiry(self, mock_settings):
        from src.auth.jwt import create_access_token, decode_token
        from src.auth.models import Role

        token = create_access_token(
            "admin", Role.ADMIN, expires_delta=timedelta(hours=24)
        )
        payload = decode_token(token)
        assert payload.sub == "admin"
        assert payload.role == Role.ADMIN

    def test_expired_token_raises(self, mock_settings):
        import jwt as pyjwt
        from src.auth.jwt import create_access_token, decode_token
        from src.auth.models import Role

        token = create_access_token(
            "expired", Role.VIEWER, expires_delta=timedelta(seconds=-1)
        )
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_token(token)

    def test_invalid_token_raises(self, mock_settings):
        import jwt as pyjwt
        from src.auth.jwt import decode_token

        with pytest.raises(pyjwt.InvalidTokenError):
            decode_token("this.is.not.valid")

    def test_all_roles_can_be_encoded(self, mock_settings):
        from src.auth.jwt import create_access_token, decode_token
        from src.auth.models import Role

        for role in Role:
            token = create_access_token("user", role)
            payload = decode_token(token)
            assert payload.role == role


# ── Dependencies ──────────────────────────────────────────────────────────────


class TestAuthDependencies:
    def test_auth_disabled_returns_admin(self, monkeypatch):
        import asyncio
        monkeypatch.setenv("GOOGLE_API_KEY", "test")
        monkeypatch.setenv("AUTH_ENABLED", "False")
        from src.auth.dependencies import get_current_user
        from src.auth.models import Role

        user = asyncio.run(get_current_user(token=None))
        assert user.username == "dev-admin"
        assert user.role == Role.ADMIN

    def test_auth_enabled_no_token_raises(self, mock_settings):
        import asyncio
        from src.auth.dependencies import get_current_user
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(token=None))
        assert exc_info.value.status_code == 401

    def test_auth_enabled_valid_token_works(self, mock_settings):
        import asyncio
        from src.auth.dependencies import get_current_user
        from src.auth.jwt import create_access_token
        from src.auth.models import Role

        token = create_access_token("analyst1", Role.ANALYST)
        user = asyncio.run(get_current_user(token=token))
        assert user.username == "analyst1"
        assert user.role == Role.ANALYST

    def test_require_role_passes_with_sufficient_role(self, mock_settings):
        import asyncio
        from src.auth.dependencies import require_role
        from src.auth.models import Role, User

        checker = require_role(Role.ANALYST)
        user = User(username="admin1", role=Role.ADMIN)
        result = asyncio.run(checker(user=user))
        assert result.username == "admin1"

    def test_require_role_blocks_insufficient_role(self, mock_settings):
        import asyncio
        from src.auth.dependencies import require_role
        from src.auth.models import Role, User
        from fastapi import HTTPException

        checker = require_role(Role.ADMIN)
        user = User(username="viewer1", role=Role.VIEWER)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(checker(user=user))
        assert exc_info.value.status_code == 403

