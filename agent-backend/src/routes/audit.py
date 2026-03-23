"""
src/routes/audit.py
─────────────────────────────────────────────────────────────────────────────
Audit Trail API — admin-only access to request audit logs.

GET /api/audit/recent   — Last N audit events (in-memory buffer)
GET /api/audit/stats    — Aggregated audit statistics
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.middleware.audit import get_recent_events, get_audit_stats

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/audit", tags=["Audit Trail"], dependencies=[Depends(get_current_user)])


@router.get("/recent")
async def recent_events(limit: int = 50):
    """Return recent audit events from the in-memory ring buffer."""
    events = get_recent_events(limit)
    return {
        "count": len(events),
        "events": events,
    }


@router.get("/stats")
async def audit_stats():
    """Return aggregated audit statistics."""
    return get_audit_stats()
