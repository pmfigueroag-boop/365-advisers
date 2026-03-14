"""
src/auth/jwt.py
─────────────────────────────────────────────────────────────────────────────
JWT creation and verification using PyJWT (HS256).
No external auth services — self-contained for pilot deployment.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import jwt

from src.auth.models import Role, TokenPayload
from src.config import get_settings

logger = logging.getLogger("365advisers.auth.jwt")

_settings = get_settings()
_ALGORITHM = "HS256"


def create_access_token(
    username: str,
    role: Role,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=_settings.JWT_EXPIRATION_MINUTES)
    )
    payload = {
        "sub": username,
        "role": role.value,
        "exp": expire,
    }
    token = jwt.encode(payload, _settings.JWT_SECRET_KEY, algorithm=_ALGORITHM)
    logger.info(f"Token created for user={username} role={role.value} exp={expire.isoformat()}")
    return token


def decode_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT token.

    Raises
    ------
    jwt.ExpiredSignatureError
        If the token has expired.
    jwt.InvalidTokenError
        If the token is malformed or signature is invalid.
    """
    payload = jwt.decode(token, _settings.JWT_SECRET_KEY, algorithms=[_ALGORITHM])
    return TokenPayload(
        sub=payload["sub"],
        role=Role(payload["role"]),
        exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
    )
