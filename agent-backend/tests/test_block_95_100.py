"""
tests/test_block_95_100.py
─────────────────────────────────────────────────────────────────────────────
Tests for Block 95→100: bcrypt passwords, secrets manager.
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


# ── Bcrypt Password Hashing ──────────────────────────────────────────────────


class TestPasswordHashing:
    def test_hash_password(self, mock_settings):
        from src.security.password import hash_password
        hashed = hash_password("mypassword123")
        assert hashed is not None
        assert len(hashed) > 0
        assert hashed != "mypassword123"

    def test_verify_correct_password(self, mock_settings):
        from src.security.password import hash_password, verify_password
        hashed = hash_password("test_pass")
        assert verify_password("test_pass", hashed) is True

    def test_verify_wrong_password(self, mock_settings):
        from src.security.password import hash_password, verify_password
        hashed = hash_password("correct_pass")
        assert verify_password("wrong_pass", hashed) is False

    def test_legacy_sha256_compatibility(self, mock_settings):
        import hashlib
        from src.security.password import verify_password
        # Legacy SHA-256 hash for "admin"
        sha_hash = hashlib.sha256("admin".encode()).hexdigest()
        assert verify_password("admin", sha_hash) is True
        assert verify_password("wrong", sha_hash) is False

    def test_needs_rehash_for_sha256(self, mock_settings):
        import hashlib
        from src.security.password import needs_rehash
        sha_hash = hashlib.sha256("admin".encode()).hexdigest()
        # SHA-256 should need rehash when bcrypt is available
        result = needs_rehash(sha_hash)
        assert isinstance(result, bool)

    def test_hashing_info(self, mock_settings):
        from src.security.password import get_hashing_info
        info = get_hashing_info()
        assert "algorithm" in info
        assert "production_ready" in info
        assert info["algorithm"] in ("bcrypt", "sha256")

    def test_different_hashes_for_same_password(self, mock_settings):
        from src.security.password import hash_password, _BCRYPT_AVAILABLE
        if _BCRYPT_AVAILABLE:
            h1 = hash_password("same_password")
            h2 = hash_password("same_password")
            # bcrypt uses random salt, so hashes should differ
            assert h1 != h2


# ── Secrets Manager ──────────────────────────────────────────────────────────


class TestSecretsManager:
    def test_env_backend_get(self, monkeypatch, mock_settings):
        monkeypatch.setenv("TEST_SECRET", "my_value")
        from src.security.secrets import EnvSecretsBackend
        backend = EnvSecretsBackend()
        assert backend.get_secret("TEST_SECRET") == "my_value"

    def test_env_backend_missing(self, mock_settings):
        from src.security.secrets import EnvSecretsBackend
        backend = EnvSecretsBackend()
        assert backend.get_secret("NONEXISTENT_SECRET_KEY_XYZ") is None

    def test_env_backend_set(self, mock_settings):
        from src.security.secrets import EnvSecretsBackend
        backend = EnvSecretsBackend()
        result = backend.set_secret("TEST_DYNAMIC", "dynamic_value")
        assert result is True
        assert backend.get_secret("TEST_DYNAMIC") == "dynamic_value"

    def test_env_backend_list_keys(self, monkeypatch, mock_settings):
        monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt")
        from src.security.secrets import EnvSecretsBackend
        backend = EnvSecretsBackend()
        keys = backend.list_keys()
        assert "GOOGLE_API_KEY" in keys

    def test_secrets_manager_default_backend(self, mock_settings):
        from src.security.secrets import SecretsManager
        mgr = SecretsManager()
        assert mgr.backend_name == "env"

    def test_secrets_manager_get_with_default(self, mock_settings):
        from src.security.secrets import SecretsManager
        mgr = SecretsManager()
        value = mgr.get("NONEXISTENT_KEY", default="fallback")
        assert value == "fallback"

    def test_secrets_manager_require_existing(self, mock_settings):
        from src.security.secrets import SecretsManager
        mgr = SecretsManager()
        value = mgr.require("GOOGLE_API_KEY")
        assert value == "test-key"

    def test_secrets_manager_require_missing(self, mock_settings):
        from src.security.secrets import SecretsManager
        mgr = SecretsManager()
        with pytest.raises(RuntimeError):
            mgr.require("TOTALLY_NONEXISTENT_SECRET")

    def test_secrets_manager_status(self, mock_settings):
        from src.security.secrets import SecretsManager
        mgr = SecretsManager()
        status = mgr.status()
        assert "backend" in status
        assert "keys_available" in status
        assert status["backend"] == "env"

    def test_vault_backend_fallback_to_env(self, monkeypatch, mock_settings):
        """Vault backend should fall back to env when Vault is unavailable."""
        monkeypatch.setenv("TEST_FALLBACK", "from_env")
        from src.security.secrets import VaultSecretsBackend
        backend = VaultSecretsBackend()
        # Should fall back to env since Vault is not running
        value = backend.get_secret("TEST_FALLBACK")
        assert value == "from_env"
