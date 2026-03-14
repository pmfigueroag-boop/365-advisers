"""
src/auth — 365 Advisers Authentication & Authorization Layer

Public API:
    get_current_user    — FastAPI dependency for extracting authenticated user
    require_role        — Factory dependency for role-based access control
    create_access_token — Generate a signed JWT
    Role                — Access role enum (VIEWER, ANALYST, ADMIN)
    User                — Authenticated user model
"""

from src.auth.dependencies import get_current_user, require_role
from src.auth.jwt import create_access_token
from src.auth.models import Role, User

__all__ = [
    "get_current_user",
    "require_role",
    "create_access_token",
    "Role",
    "User",
]
