"""
src/routes/auth.py
─────────────────────────────────────────────────────────────────────────────
Authentication endpoints for JWT token management.

POST /auth/token  — Obtain access token
GET  /auth/me     — Current user info (protected)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from src.auth.dependencies import get_current_user
from src.auth.jwt import create_access_token
from src.auth.models import Role, User
from src.config import get_settings
from src.security.password import verify_password

logger = logging.getLogger("365advisers.routes.auth")
router = APIRouter(prefix="/auth", tags=["Authentication"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


@router.post("/token", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate and receive a JWT access token.

    For pilot/development: uses configurable admin credentials from settings.
    For production: integrate with your identity provider (Auth0, Okta, etc.).
    """
    settings = get_settings()

    # Validate credentials against configured admin user
    if (
        form_data.username == settings.ADMIN_USERNAME
        and verify_password(form_data.password, settings.ADMIN_PASSWORD_HASH)
    ):
        role = Role.ADMIN
    elif (
        form_data.username == "analyst"
        and verify_password(form_data.password, settings.ANALYST_PASSWORD_HASH)
    ):
        role = Role.ANALYST
    elif (
        form_data.username == "viewer"
        and verify_password(form_data.password, settings.VIEWER_PASSWORD_HASH)
    ):
        role = Role.VIEWER
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(username=form_data.username, role=role)
    logger.info(f"Login successful: user={form_data.username} role={role.value}")

    return TokenResponse(
        access_token=token,
        role=role.value,
        username=form_data.username,
    )


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    """Return the authenticated user's identity and role."""
    return {"username": user.username, "role": user.role.value}
