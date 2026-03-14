"""
src/middleware/audit.py
─────────────────────────────────────────────────────────────────────────────
Audit Trail middleware — logs all API requests with user, endpoint,
method, status code, and duration.

Stores audit events in the database for compliance (GDPR/SOC2)
and in-memory buffer for real-time monitoring.
"""

from __future__ import annotations

import time
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("365advisers.audit")

# In-memory ring buffer for recent audit events (last 1000)
_audit_buffer: deque[dict] = deque(maxlen=1000)

# Paths to skip auditing (high-frequency health checks)
_SKIP_PATHS = {"/health", "/health/live", "/health/ready", "/docs", "/openapi.json", "/favicon.ico"}


class AuditMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that logs every request to the audit trail.

    Captures:
      - timestamp, method, path, status_code
      - client_ip, user_agent
      - authenticated user (from JWT when available)
      - response duration_ms
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip health checks and docs
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        t0 = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - t0) * 1000

        # Extract user info from auth header (if present)
        user = "anonymous"
        try:
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                from src.auth.jwt import decode_token
                payload = decode_token(auth_header[7:])
                user = payload.sub
        except Exception:
            pass

        # Build audit event
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params) if request.query_params else None,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 1),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "")[:100],
            "user": user,
        }

        _audit_buffer.append(event)

        # Log with appropriate level
        if response.status_code >= 500:
            logger.error(f"AUDIT: {event['method']} {event['path']} → {event['status_code']} ({event['duration_ms']}ms) user={user}")
        elif response.status_code >= 400:
            logger.warning(f"AUDIT: {event['method']} {event['path']} → {event['status_code']} ({event['duration_ms']}ms) user={user}")
        else:
            logger.info(f"AUDIT: {event['method']} {event['path']} → {event['status_code']} ({event['duration_ms']}ms) user={user}")

        # Async DB write (best-effort, don't block the response)
        try:
            _persist_audit_event(event)
        except Exception:
            pass  # Audit persistence is best-effort

        return response


def _persist_audit_event(event: dict) -> None:
    """
    Persist audit event to database (non-blocking best-effort).

    Uses the AuditLog model if available.
    """
    try:
        from src.data.database import SessionLocal
        from src.data.models.audit import AuditLog

        with SessionLocal() as session:
            log = AuditLog(
                timestamp=event["timestamp"],
                method=event["method"],
                path=event["path"],
                query_params=event.get("query"),
                status_code=event["status_code"],
                duration_ms=event["duration_ms"],
                client_ip=event["client_ip"],
                user_agent=event.get("user_agent", ""),
                username=event["user"],
            )
            session.add(log)
            session.commit()
    except ImportError:
        pass  # Model not yet created
    except Exception as exc:
        logger.debug(f"Audit DB write failed (non-critical): {exc}")


def get_recent_events(limit: int = 100) -> list[dict]:
    """Return recent audit events from the in-memory buffer."""
    events = list(_audit_buffer)
    return events[-limit:]


def get_audit_stats() -> dict:
    """Return aggregated audit statistics."""
    events = list(_audit_buffer)
    if not events:
        return {"total_events": 0}

    status_counts: dict[str, int] = {}
    path_counts: dict[str, int] = {}
    user_counts: dict[str, int] = {}
    total_duration = 0.0

    for e in events:
        sc = str(e.get("status_code", "unknown"))
        status_counts[sc] = status_counts.get(sc, 0) + 1

        path = e.get("path", "unknown")
        path_counts[path] = path_counts.get(path, 0) + 1

        user = e.get("user", "anonymous")
        user_counts[user] = user_counts.get(user, 0) + 1

        total_duration += e.get("duration_ms", 0)

    # Top 10 paths
    top_paths = sorted(path_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "total_events": len(events),
        "buffer_capacity": _audit_buffer.maxlen,
        "status_distribution": status_counts,
        "top_paths": dict(top_paths),
        "unique_users": len(user_counts),
        "avg_duration_ms": round(total_duration / len(events), 1) if events else 0,
    }
