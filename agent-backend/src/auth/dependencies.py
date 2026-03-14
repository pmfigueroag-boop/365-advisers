"""
src/auth/dependencies.py
─────────────────────────────────────────────────────────────────────────────
FastAPI dependencies for authentication and role-based authorization.

Usage in route files:

    from src.auth import get_current_user, require_role
    from src.auth.models import Role, User

    @router.get("/protected")
    async def protected(user: User = Depends(get_current_user)):
        ...

    @router.post("/admin-only")
    async def admin_only(user: User = Depends(require_role(Role.ADMIN))):
        ...
"""

from __future__ import annotations

import logging
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.auth.jwt import decode_token
from src.auth.models import Role, User, role_has_access
from src.config import get_settings

logger = logging.getLogger("365advisers.auth.deps")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
) -> User:
    """
    Extract and validate user from JWT Bearer token.

    If AUTH_ENABLED is False (dev mode), returns a default admin user
    to maintain backwards compatibility with existing workflows.
    """
    settings = get_settings()

    if not settings.AUTH_ENABLED:
        return User(username="dev-admin", role=Role.ADMIN)

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(token)
        return User(username=payload.sub, role=payload.role)
    except Exception as exc:
        logger.warning(f"Token validation failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(*roles: Role) -> Callable:
    """
    Factory that returns a dependency requiring the user to have one of
    the specified roles (or a higher role in the hierarchy).

    Usage:
        @router.post("/admin", dependencies=[Depends(require_role(Role.ADMIN))])
    """
    async def _check(user: User = Depends(get_current_user)) -> User:
        for r in roles:
            if role_has_access(user.role, r):
                return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions. Required: {[r.value for r in roles]}",
        )
    return _check
