"""
src/auth/models.py
─────────────────────────────────────────────────────────────────────────────
Authentication data models — roles, tokens, and user representations.
"""

from __future__ import annotations

from enum import Enum
from datetime import datetime
from pydantic import BaseModel


class Role(str, Enum):
    """Platform access roles (hierarchical)."""
    VIEWER = "viewer"       # Read-only access to dashboards and analysis results
    ANALYST = "analyst"     # Full analysis, ideas, portfolio operations
    ADMIN = "admin"         # System config, governance, compliance, user management


# Ordered hierarchy for permission checks
_ROLE_HIERARCHY = {Role.VIEWER: 0, Role.ANALYST: 1, Role.ADMIN: 2}


def role_has_access(user_role: Role, required_role: Role) -> bool:
    """Check if user_role meets or exceeds required_role."""
    return _ROLE_HIERARCHY.get(user_role, -1) >= _ROLE_HIERARCHY.get(required_role, 99)


class TokenPayload(BaseModel):
    """JWT token payload (claims)."""
    sub: str                    # username
    role: Role
    exp: datetime               # expiration


class User(BaseModel):
    """Authenticated user context, available via Depends(get_current_user)."""
    username: str
    role: Role
