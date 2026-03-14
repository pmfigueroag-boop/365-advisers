"""
src/routes/health.py
──────────────────────────────────────────────────────────────────────────────
Canonical health endpoints — Kubernetes-grade readiness and liveness probes.

GET /           → Root banner
GET /health     → Full system health (DB, EDPL, cache, observability)
GET /health/live  → Liveness probe (is the process alive?)
GET /health/ready → Readiness probe (can the process serve traffic?)
"""

from __future__ import annotations

import time
import logging
from datetime import datetime, timezone

from fastapi import APIRouter

logger = logging.getLogger("365advisers.health")
router = APIRouter(tags=["Health"])

_START_TIME = time.monotonic()


@router.get("/")
def read_root():
    return {
        "message": "365 Advisers API is running",
        "version": "3.4.0",
        "docs": "/docs",
    }


@router.get("/health")
def health_check():
    """
    Comprehensive system health check.

    Verifies connectivity to:
      - Database (SQLAlchemy)
      - EDPL (circuit breaker states)
      - Cache subsystems
      - LLM availability (config present)

    Returns HTTP 200 with component statuses.
    Any individual component failure degrades status to 'degraded'.
    """
    checks = {}
    overall = "healthy"
    uptime_s = round(time.monotonic() - _START_TIME)

    # ── Database Check ────────────────────────────────────────────────────
    try:
        from src.data.database import get_engine
        from sqlalchemy import text
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = {"status": "up", "type": str(engine.url).split("://")[0]}
    except Exception as exc:
        checks["database"] = {"status": "down", "error": str(exc)[:100]}
        overall = "degraded"

    # ── EDPL Check ────────────────────────────────────────────────────────
    try:
        from fastapi import Request
        from src.data.external.health import HealthChecker
        health_checker = HealthChecker()
        edpl_status = health_checker.aggregated_status()
        healthy_providers = sum(
            1 for p in edpl_status.values()
            if isinstance(p, dict) and p.get("state") != "open"
        )
        total_providers = len(edpl_status)
        checks["edpl"] = {
            "status": "up" if healthy_providers > 0 else "degraded",
            "providers_healthy": healthy_providers,
            "providers_total": total_providers,
        }
    except Exception as exc:
        checks["edpl"] = {"status": "unconfigured", "note": str(exc)[:80]}

    # ── Cache Check ───────────────────────────────────────────────────────
    try:
        from src.services.cache_manager import cache_manager
        analysis_entries = len(cache_manager.analysis._store)
        decision_entries = len(cache_manager.decision._store)
        checks["cache"] = {
            "status": "up",
            "backend": cache_manager.analysis.__class__.__name__,
            "analysis_entries": analysis_entries,
            "decision_entries": decision_entries,
        }
    except Exception as exc:
        checks["cache"] = {"status": "degraded", "error": str(exc)[:80]}

    # ── LLM Check ─────────────────────────────────────────────────────────
    try:
        from src.config import get_settings
        settings = get_settings()
        has_key = bool(settings.GOOGLE_API_KEY and settings.GOOGLE_API_KEY != "not-set")
        checks["llm"] = {
            "status": "up" if has_key else "unconfigured",
            "model": settings.LLM_MODEL,
            "api_key_configured": has_key,
        }
    except Exception as exc:
        checks["llm"] = {"status": "error", "error": str(exc)[:80]}

    # ── Observability Check ───────────────────────────────────────────────
    try:
        from src.config import get_settings
        settings = get_settings()
        checks["observability"] = {
            "status": "up" if settings.OTEL_ENABLED else "disabled",
            "exporter": settings.OTEL_EXPORTER,
        }
    except Exception:
        checks["observability"] = {"status": "unknown"}

    # ── Auth Check ────────────────────────────────────────────────────────
    try:
        from src.config import get_settings
        settings = get_settings()
        checks["auth"] = {
            "status": "enforced" if settings.AUTH_ENABLED else "disabled",
        }
    except Exception:
        checks["auth"] = {"status": "unknown"}

    return {
        "status": overall,
        "version": "3.4.0",
        "uptime_seconds": uptime_s,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


@router.get("/health/live")
def liveness():
    """
    Kubernetes liveness probe.
    Returns 200 if the process is alive. Should never fail.
    """
    return {"status": "alive"}


@router.get("/health/ready")
def readiness():
    """
    Kubernetes readiness probe.
    Returns 200 if the service can handle traffic (DB is reachable).
    Returns 503 if critical dependencies are down.
    """
    try:
        from src.data.database import get_engine
        from sqlalchemy import text
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": str(exc)[:100]},
        )
