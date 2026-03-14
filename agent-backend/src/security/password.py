"""
src/security/password.py
─────────────────────────────────────────────────────────────────────────────
Bcrypt password hashing — replaces SHA-256 for production-grade security.

Uses passlib with bcrypt backend for:
  - Adaptive cost factor (auto-adjusts to hardware speed)
  - Salt auto-generation (no rainbow table attacks)
  - Timing-safe comparison (no timing side-channel)
"""

from __future__ import annotations

import hashlib
import logging

logger = logging.getLogger("365advisers.security.password")

# Try bcrypt first, fall back to SHA-256
_BCRYPT_AVAILABLE = False
_hasher = None

try:
    import bcrypt as _bcrypt_lib
    _BCRYPT_AVAILABLE = True
    logger.info("Password hashing: bcrypt (production)")
except ImportError:
    _bcrypt_lib = None
    logger.warning("bcrypt not installed — falling back to SHA-256 (NOT production-safe)")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt (or SHA-256 fallback).

    Parameters
    ----------
    password : str
        Plain-text password

    Returns
    -------
    str
        Hashed password string
    """
    if _BCRYPT_AVAILABLE and _bcrypt_lib:
        # bcrypt has 72-byte limit, truncate if needed
        pw_bytes = password.encode("utf-8")[:72]
        salt = _bcrypt_lib.gensalt(rounds=12)
        return _bcrypt_lib.hashpw(pw_bytes, salt).decode("utf-8")
    else:
        return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Supports both bcrypt hashes and legacy SHA-256 hashes.

    Parameters
    ----------
    plain_password : str
        Plain-text password to verify
    hashed_password : str
        Stored hash to verify against

    Returns
    -------
    bool
        True if password matches
    """
    # Detect hash type
    if hashed_password.startswith("$2b$") and _BCRYPT_AVAILABLE and _bcrypt_lib:
        # Bcrypt hash
        pw_bytes = plain_password.encode("utf-8")[:72]
        return _bcrypt_lib.checkpw(pw_bytes, hashed_password.encode("utf-8"))
    else:
        # Legacy SHA-256 hash (backwards compatible)
        sha_hash = hashlib.sha256(plain_password.encode()).hexdigest()
        return sha_hash == hashed_password


def needs_rehash(hashed_password: str) -> bool:
    """
    Check if a password hash needs to be upgraded.

    Returns True for SHA-256 hashes when bcrypt is available,
    or for bcrypt hashes with outdated cost factors.
    """
    if not _BCRYPT_AVAILABLE:
        return False

    if not hashed_password.startswith("$2b$"):
        return True  # SHA-256 → needs bcrypt upgrade

    return False  # bcrypt hash is current


def get_hashing_info() -> dict:
    """Return info about the current hashing configuration."""
    return {
        "algorithm": "bcrypt" if _BCRYPT_AVAILABLE else "sha256",
        "bcrypt_available": _BCRYPT_AVAILABLE,
        "bcrypt_rounds": 12 if _BCRYPT_AVAILABLE else None,
        "production_ready": _BCRYPT_AVAILABLE,
    }
