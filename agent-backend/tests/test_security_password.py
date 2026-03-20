"""
tests/test_security_password.py
──────────────────────────────────────────────────────────────────────────────
Tests for the password hashing module — verifies bcrypt hashing,
SHA256 backward compatibility, and rehash detection.
"""

import pytest
import hashlib


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from src.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _mock_google_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")


# ── hash_password ─────────────────────────────────────────────────────────────


class TestHashPassword:
    def test_produces_bcrypt_hash(self):
        from src.security.password import hash_password, _BCRYPT_AVAILABLE
        hashed = hash_password("testpassword")
        if _BCRYPT_AVAILABLE:
            assert hashed.startswith("$2b$")
            assert len(hashed) == 60
        else:
            # SHA256 fallback
            assert len(hashed) == 64

    def test_different_passwords_produce_different_hashes(self):
        from src.security.password import hash_password
        h1 = hash_password("password1")
        h2 = hash_password("password2")
        assert h1 != h2

    def test_same_password_produces_different_salts(self):
        """bcrypt generates unique salts each time."""
        from src.security.password import hash_password, _BCRYPT_AVAILABLE
        if not _BCRYPT_AVAILABLE:
            pytest.skip("bcrypt not installed")
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2  # Different salts


# ── verify_password ───────────────────────────────────────────────────────────


class TestVerifyPassword:
    def test_verify_bcrypt_hash(self):
        from src.security.password import hash_password, verify_password, _BCRYPT_AVAILABLE
        if not _BCRYPT_AVAILABLE:
            pytest.skip("bcrypt not installed")
        hashed = hash_password("MySecurePassword123!")
        assert verify_password("MySecurePassword123!", hashed) is True
        assert verify_password("WrongPassword", hashed) is False

    def test_verify_legacy_sha256_hash(self):
        """Backward compat: verify_password should accept old SHA256 hashes."""
        from src.security.password import verify_password
        sha_hash = hashlib.sha256("admin".encode()).hexdigest()
        assert verify_password("admin", sha_hash) is True
        assert verify_password("wrong", sha_hash) is False

    def test_verify_actual_default_admin_hash(self):
        """Verify the old default admin hash still works via backward compat."""
        from src.security.password import verify_password
        old_admin_hash = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
        assert verify_password("admin", old_admin_hash) is True

    def test_verify_new_bcrypt_default_admin_hash(self):
        """Verify the new bcrypt admin hash works."""
        from src.security.password import verify_password, _BCRYPT_AVAILABLE
        if not _BCRYPT_AVAILABLE:
            pytest.skip("bcrypt not installed")
        new_hash = "$2b$12$oWydfZyOI4zn0SdQxebEVe9KCgbOR/R3EV4S1mHfohysI3nXqb3qC"
        assert verify_password("admin", new_hash) is True
        assert verify_password("wrong", new_hash) is False


# ── needs_rehash ──────────────────────────────────────────────────────────────


class TestNeedsRehash:
    def test_sha256_needs_rehash(self):
        from src.security.password import needs_rehash, _BCRYPT_AVAILABLE
        if not _BCRYPT_AVAILABLE:
            pytest.skip("bcrypt not installed")
        sha_hash = hashlib.sha256("test".encode()).hexdigest()
        assert needs_rehash(sha_hash) is True

    def test_bcrypt_does_not_need_rehash(self):
        from src.security.password import hash_password, needs_rehash, _BCRYPT_AVAILABLE
        if not _BCRYPT_AVAILABLE:
            pytest.skip("bcrypt not installed")
        bcrypt_hash = hash_password("test")
        assert needs_rehash(bcrypt_hash) is False


# ── get_hashing_info ──────────────────────────────────────────────────────────


class TestHashingInfo:
    def test_returns_expected_keys(self):
        from src.security.password import get_hashing_info
        info = get_hashing_info()
        assert "algorithm" in info
        assert "bcrypt_available" in info
        assert "production_ready" in info
        assert isinstance(info["bcrypt_available"], bool)
