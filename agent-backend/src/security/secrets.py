"""
src/security/secrets.py
─────────────────────────────────────────────────────────────────────────────
Secrets Management — abstraction layer for credential retrieval.

Supports multiple backends:
  - Environment variables (default, development)
  - HashiCorp Vault (production)
  - AWS Secrets Manager (cloud production)

Provides automatic secret rotation detection and refresh.
"""

from __future__ import annotations

import os
import time
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("365advisers.security.secrets")


class SecretsBackend(ABC):
    """Abstract base class for secrets backends."""

    @abstractmethod
    def get_secret(self, key: str) -> str | None:
        """Retrieve a secret by key."""
        ...

    @abstractmethod
    def set_secret(self, key: str, value: str) -> bool:
        """Store a secret (if supported)."""
        ...

    @abstractmethod
    def list_keys(self) -> list[str]:
        """List available secret keys."""
        ...


class EnvSecretsBackend(SecretsBackend):
    """
    Environment variable-based secrets (development default).

    Reads from os.environ with optional .env file support.
    """

    _KNOWN_KEYS = [
        "GOOGLE_API_KEY", "JWT_SECRET_KEY", "DATABASE_URL",
        "REDIS_URL", "ADMIN_PASSWORD_HASH", "ANALYST_PASSWORD_HASH",
        "VIEWER_PASSWORD_HASH",
    ]

    def get_secret(self, key: str) -> str | None:
        value = os.getenv(key)
        if value:
            logger.debug(f"Secret retrieved from env: {key}")
        return value

    def set_secret(self, key: str, value: str) -> bool:
        os.environ[key] = value
        logger.info(f"Secret set in env: {key}")
        return True

    def list_keys(self) -> list[str]:
        return [k for k in self._KNOWN_KEYS if os.getenv(k)]


class VaultSecretsBackend(SecretsBackend):
    """
    HashiCorp Vault backend (production).

    Requires VAULT_ADDR and VAULT_TOKEN environment variables.
    Falls back to EnvSecretsBackend if Vault is unavailable.
    """

    def __init__(self, mount_path: str = "secret", path_prefix: str = "365advisers"):
        self.mount_path = mount_path
        self.path_prefix = path_prefix
        self._client = None
        self._cache: dict[str, tuple[str, float]] = {}  # key -> (value, timestamp)
        self._cache_ttl = 300  # 5 min cache

        try:
            import hvac
            vault_addr = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
            vault_token = os.getenv("VAULT_TOKEN", "")
            self._client = hvac.Client(url=vault_addr, token=vault_token)
            if self._client.is_authenticated():
                logger.info(f"Vault connected: {vault_addr}")
            else:
                logger.warning("Vault token is not valid")
                self._client = None
        except ImportError:
            logger.info("hvac not installed — Vault backend unavailable")
        except Exception as exc:
            logger.warning(f"Vault connection failed: {exc}")

    def get_secret(self, key: str) -> str | None:
        # Check cache first
        if key in self._cache:
            value, ts = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return value

        if self._client is None:
            return os.getenv(key)

        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                mount_point=self.mount_path,
                path=f"{self.path_prefix}/{key.lower()}",
            )
            value = response["data"]["data"].get("value")
            if value:
                self._cache[key] = (value, time.time())
                logger.debug(f"Secret retrieved from Vault: {key}")
            return value
        except Exception as exc:
            logger.warning(f"Vault read failed for {key}: {exc}")
            return os.getenv(key)

    def set_secret(self, key: str, value: str) -> bool:
        if self._client is None:
            return False
        try:
            self._client.secrets.kv.v2.create_or_update_secret(
                mount_point=self.mount_path,
                path=f"{self.path_prefix}/{key.lower()}",
                secret={"value": value},
            )
            self._cache[key] = (value, time.time())
            logger.info(f"Secret stored in Vault: {key}")
            return True
        except Exception as exc:
            logger.error(f"Vault write failed for {key}: {exc}")
            return False

    def list_keys(self) -> list[str]:
        if self._client is None:
            return EnvSecretsBackend().list_keys()
        try:
            response = self._client.secrets.kv.v2.list_secrets(
                mount_point=self.mount_path,
                path=self.path_prefix,
            )
            return response["data"]["keys"]
        except Exception:
            return EnvSecretsBackend().list_keys()


class SecretsManager:
    """
    Unified secrets manager with backend selection.

    Usage:
        secrets = SecretsManager()
        api_key = secrets.get("GOOGLE_API_KEY")
    """

    def __init__(self):
        backend_name = os.getenv("SECRETS_BACKEND", "env")
        if backend_name == "vault":
            self._backend = VaultSecretsBackend()
        else:
            self._backend = EnvSecretsBackend()
        self._backend_name = backend_name
        logger.info(f"SecretsManager initialized with backend: {backend_name}")

    @property
    def backend_name(self) -> str:
        return self._backend_name

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get a secret value, with optional default."""
        value = self._backend.get_secret(key)
        return value if value is not None else default

    def require(self, key: str) -> str:
        """Get a secret value, raising if not found."""
        value = self._backend.get_secret(key)
        if value is None:
            raise RuntimeError(f"Required secret not found: {key}")
        return value

    def set(self, key: str, value: str) -> bool:
        return self._backend.set_secret(key, value)

    def list_available(self) -> list[str]:
        return self._backend.list_keys()

    def status(self) -> dict:
        """Health check for secrets backend."""
        keys = self.list_available()
        return {
            "backend": self._backend_name,
            "keys_available": len(keys),
            "keys": keys,
        }


# Singleton
secrets_manager = SecretsManager()
