"""
src/routes/monitoring.py
──────────────────────────────────────────────────────────────────────────────
REST API endpoints for the Opportunity Monitoring Engine.

POST  /monitoring/scan              → Trigger a monitoring scan
GET   /monitoring/alerts            → List alerts (filter by ticker/severity/unread)
PATCH /monitoring/alerts/{id}/read  → Mark alert as read
GET   /monitoring/config            → Current monitoring config
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.engines.monitoring.engine import MonitoringEngine
from src.engines.monitoring.models import MonitoringConfig

logger = logging.getLogger("365advisers.routes.monitoring")

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

_engine = MonitoringEngine()


# ─── Request Models ─────────────────────────────────────────────────────────

class MonitoringScanRequest(BaseModel):
    """Request to trigger a monitoring scan."""
    tickers: list[str] = Field(
        ..., min_length=1, description="Tickers to monitor",
    )
    case_scores: dict[str, float] = Field(
        default_factory=dict, description="{ticker: CASE 0-100}",
    )
    opp_scores: dict[str, float] = Field(
        default_factory=dict, description="{ticker: OppScore 0-10}",
    )
    signals: dict[str, list[str]] = Field(
        default_factory=dict, description="{ticker: [signal_ids]}",
    )
    uos_scores: dict[str, float] = Field(
        default_factory=dict, description="{ticker: UOS 0-100}",
    )
    tiers: dict[str, str] = Field(
        default_factory=dict, description="{ticker: tier label}",
    )


# ─── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/scan")
async def trigger_scan(request: MonitoringScanRequest):
    """Trigger a monitoring scan and return any generated alerts."""
    result = _engine.scan(
        tickers=[t.upper() for t in request.tickers],
        case_scores=request.case_scores,
        opp_scores=request.opp_scores,
        signals=request.signals,
        uos_scores=request.uos_scores,
        tiers=request.tiers,
    )
    return {
        "tickers_monitored": result.tickers_monitored,
        "alerts_generated": result.alerts_generated,
        "alerts": [a.model_dump(mode="json") for a in result.alerts],
        "scan_duration_ms": result.scan_duration_ms,
        "scanned_at": result.scanned_at.isoformat(),
    }


@router.get("/alerts")
async def list_alerts(
    ticker: str | None = None,
    severity: str | None = None,
    unread_only: bool = False,
    limit: int = 50,
):
    """List monitoring alerts with optional filters."""
    alerts = _engine.get_alerts(
        ticker=ticker,
        severity=severity,
        unread_only=unread_only,
        limit=limit,
    )
    return {
        "alerts": [a.model_dump(mode="json") for a in alerts],
        "total": len(alerts),
    }


@router.patch("/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: str):
    """Mark an alert as read."""
    success = _engine.mark_read(alert_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Alert '{alert_id}' not found",
        )
    return {"status": "read", "alert_id": alert_id}


@router.get("/config")
async def get_config():
    """Get the current monitoring configuration."""
    return _engine.config.model_dump()


# ═══════════════════════════════════════════════════════════════════════════════
#  SIGNAL HEALTH & CIRCUIT BREAKER
# ═══════════════════════════════════════════════════════════════════════════════

from src.engines.monitoring.health import (
    CircuitBreakerConfig,
    MonitoringSweepEngine,
)

_sweep_engine = MonitoringSweepEngine()


class HealthSweepRequest(BaseModel):
    """Request body for a health monitoring sweep."""
    signal_metrics: list[dict] = Field(
        ..., description="List of {signal_id, hit_rate, signal_stability, avg_return}",
    )
    drift_data: dict[str, float] = Field(
        default_factory=dict, description="{signal_id: drift_severity (0-1)}",
    )


@router.post("/health/sweep")
async def run_health_sweep(request: HealthSweepRequest):
    """Run a unified health monitoring sweep across all signals.

    Evaluates health scores, applies circuit breaker logic, and returns
    a consolidated result with per-signal health breakdowns.
    """
    result = _sweep_engine.run_sweep(
        signal_metrics=request.signal_metrics,
        drift_data=request.drift_data,
    )
    return result.model_dump(mode="json")


@router.get("/health/scores")
async def get_health_scores():
    """Get current health scores for all evaluated signals."""
    result = _sweep_engine.run_sweep(signal_metrics=[])
    return {
        "signals": [s.model_dump() for s in result.signal_scores],
        "summary": {
            "healthy": result.signals_healthy,
            "warning": result.signals_warning,
            "critical": result.signals_critical,
            "disabled": result.signals_auto_disabled,
        },
    }


@router.get("/circuit-breaker/status")
async def get_circuit_breaker_status():
    """Get current circuit breaker status showing all disabled signals."""
    disabled = _sweep_engine.circuit_breaker.get_disabled_signals()
    return {
        "disabled_signals": disabled,
        "disabled_count": len(disabled),
    }


@router.post("/circuit-breaker/{signal_id}/enable")
async def force_enable_signal(signal_id: str):
    """Manually re-enable a disabled signal."""
    ok = _sweep_engine.circuit_breaker.force_enable(signal_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Signal not currently disabled")
    return {"signal_id": signal_id, "status": "re-enabled"}


@router.post("/circuit-breaker/{signal_id}/disable")
async def force_disable_signal(signal_id: str, reason: str = "manual"):
    """Manually disable a signal via circuit breaker."""
    _sweep_engine.circuit_breaker.force_disable(signal_id, reason)
    return {"signal_id": signal_id, "status": "disabled", "reason": reason}

