"""
src/routes/health.py
──────────────────────────────────────────────────────────────────────────────
Health and root endpoints — extracted from main.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/")
def read_root():
    return {"message": "365 Advisers API is running"}


@router.get("/health")
def health_check():
    """System health check for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "3.0.0",
    }
