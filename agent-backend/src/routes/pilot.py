"""
src/routes/pilot.py
─────────────────────────────────────────────────────────────────────────────
REST API endpoints for the 365 Advisers Pilot Deployment system.

Prefix: /pilot
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.engines.pilot.runner import PilotRunner
from src.engines.pilot.metrics import PilotMetrics
from src.engines.pilot.config import PILOT_TICKERS, PILOT_STRATEGY_CONFIGS
from src.engines.pilot.models import (
    PilotDashboardData,
    PilotStatus,
    PilotSuccessAssessment,
    PilotWeeklyReport,
)

logger = logging.getLogger("365advisers.routes.pilot")
router = APIRouter(prefix="/pilot", tags=["pilot"])

# ── Shared runner instance ──────────────────────────────────────────────────

_runner = PilotRunner()
_metrics = PilotMetrics()


# ── Lifecycle Endpoints ─────────────────────────────────────────────────────


@router.post("/initialize", response_model=dict)
def initialize_pilot():
    """Initialize a new pilot deployment with 3 portfolios."""
    try:
        status = _runner.initialize_pilot()
        return {
            "status": "initialized",
            "pilot_id": status.pilot_id,
            "phase": status.phase.value,
            "research_portfolio_id": status.research_portfolio_id,
            "strategy_portfolio_id": status.strategy_portfolio_id,
            "benchmark_portfolio_id": status.benchmark_portfolio_id,
            "universe": PILOT_TICKERS,
        }
    except Exception as e:
        logger.error("Failed to initialize pilot: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-daily/{pilot_id}", response_model=dict)
def run_daily_cycle(pilot_id: str):
    """Trigger the daily pilot cycle manually."""
    try:
        result = _runner.run_daily_cycle(pilot_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Daily cycle failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/advance-phase/{pilot_id}", response_model=dict)
def advance_phase(pilot_id: str):
    """Advance the pilot to the next phase."""
    try:
        status = _runner.advance_phase(pilot_id)
        return {
            "status": "advanced",
            "pilot_id": status.pilot_id,
            "phase": status.phase.value,
            "current_week": status.current_week,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Query Endpoints ─────────────────────────────────────────────────────────


@router.get("/status/{pilot_id}")
def get_pilot_status(pilot_id: str):
    """Get the current pilot status."""
    status = _runner.get_pilot_status(pilot_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Pilot {pilot_id} not found")
    return status.model_dump()


@router.get("/status")
def get_active_pilot():
    """Get the currently active pilot."""
    status = _runner.get_active_pilot()
    if not status:
        raise HTTPException(status_code=404, detail="No active pilot found")
    return status.model_dump()


@router.get("/dashboard/{pilot_id}")
def get_dashboard(pilot_id: str):
    """Get the full dashboard data payload."""
    try:
        data = _runner.get_dashboard_data(pilot_id)
        return data.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/metrics/{pilot_id}")
def get_metrics(
    pilot_id: str,
    level: str = Query("all", description="Metric level: signal|idea|strategy|portfolio|all"),
):
    """Get current pilot metrics — pulls from stored metric records."""
    status = _runner.get_pilot_status(pilot_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Pilot {pilot_id} not found")

    from src.data.database import SessionLocal, PilotMetricRecord

    with SessionLocal() as db:
        q = db.query(PilotMetricRecord).filter(
            PilotMetricRecord.pilot_id == pilot_id,
        )
        if level != "all":
            q = q.filter(PilotMetricRecord.metric_type == level)

        rows = q.order_by(PilotMetricRecord.computed_at.desc()).limit(100).all()

    metrics_by_type: dict[str, list[dict]] = {}
    for row in rows:
        metrics_by_type.setdefault(row.metric_type, []).append({
            "name": row.metric_name,
            "value": row.value,
            "category": row.category,
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
        })

    return {
        "pilot_id": pilot_id,
        "level": level,
        "metrics": metrics_by_type,
    }


@router.get("/alerts/{pilot_id}")
def get_alerts(
    pilot_id: str,
    severity: str | None = Query(None, description="Filter by severity: info|warning|critical"),
    limit: int = Query(50, ge=1, le=200),
):
    """Get pilot alert history."""
    alerts = _runner.get_alerts(pilot_id, severity=severity, limit=limit)
    return {
        "pilot_id": pilot_id,
        "total": len(alerts),
        "alerts": [a.model_dump() for a in alerts],
    }


@router.get("/leaderboards/{pilot_id}")
def get_leaderboards(pilot_id: str):
    """Get signal and strategy leaderboards from stored metrics."""
    status = _runner.get_pilot_status(pilot_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Pilot {pilot_id} not found")

    from src.data.database import SessionLocal, PilotMetricRecord

    with SessionLocal() as db:
        # Signal metrics
        signal_rows = (
            db.query(PilotMetricRecord)
            .filter(
                PilotMetricRecord.pilot_id == pilot_id,
                PilotMetricRecord.metric_type == "signal",
            )
            .order_by(PilotMetricRecord.computed_at.desc())
            .limit(20)
            .all()
        )

        # Portfolio metrics
        portfolio_rows = (
            db.query(PilotMetricRecord)
            .filter(
                PilotMetricRecord.pilot_id == pilot_id,
                PilotMetricRecord.metric_type == "portfolio",
            )
            .order_by(PilotMetricRecord.computed_at.desc())
            .limit(20)
            .all()
        )

    return {
        "pilot_id": pilot_id,
        "signal_leaderboard": [
            {"name": r.metric_name, "value": r.value, "category": r.category}
            for r in signal_rows
        ],
        "strategy_leaderboard": [
            {"name": r.metric_name, "value": r.value, "category": r.category}
            for r in portfolio_rows
        ],
    }


@router.get("/portfolios/{pilot_id}")
def get_portfolios(pilot_id: str):
    """Get all 3 pilot portfolio summaries."""
    from src.engines.shadow.manager import ShadowPortfolioManager

    status = _runner.get_pilot_status(pilot_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Pilot {pilot_id} not found")

    mgr = ShadowPortfolioManager()
    portfolios = {}

    for label, pid in [
        ("research", status.research_portfolio_id),
        ("strategy", status.strategy_portfolio_id),
        ("benchmark", status.benchmark_portfolio_id),
    ]:
        if pid:
            summary = mgr.get(pid)
            portfolios[label] = summary.model_dump() if summary else None
        else:
            portfolios[label] = None

    return {"pilot_id": pilot_id, "portfolios": portfolios}


@router.get("/report/weekly/{pilot_id}")
def get_weekly_report(
    pilot_id: str,
    week: int | None = Query(None, description="Specific week number (default: current)"),
):
    """Generate a weekly report for the pilot."""
    try:
        report = _runner.generate_weekly_report(pilot_id, week=week)
        return report.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/success-criteria/{pilot_id}")
def check_success_criteria(pilot_id: str):
    """Evaluate Go/No-Go success criteria using stored metrics."""
    status = _runner.get_pilot_status(pilot_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Pilot {pilot_id} not found")

    # Try to pull latest computed metrics
    from src.data.database import SessionLocal, PilotMetricRecord

    metric_values: dict[str, float] = {}
    with SessionLocal() as db:
        rows = (
            db.query(PilotMetricRecord)
            .filter(PilotMetricRecord.pilot_id == pilot_id)
            .order_by(PilotMetricRecord.computed_at.desc())
            .limit(50)
            .all()
        )
        for row in rows:
            key = f"{row.metric_type}_{row.metric_name}"
            if key not in metric_values:
                metric_values[key] = row.value

    assessment = _metrics.check_success_criteria(
        signal_hit_rate=metric_values.get("signal_overall_hit_rate", 0.0),
        research_alpha=metric_values.get("portfolio_research_sharpe", 0.0),
        strategy_sharpe=metric_values.get("portfolio_strategy_sharpe", 0.0),
        max_drawdown=metric_values.get("portfolio_research_max_dd", 0.0),
        strategy_quality=0.0,
        system_uptime=1.0,
        pilot_id=pilot_id,
    )

    return assessment.model_dump()


@router.get("/config")
def get_pilot_config():
    """Get the current pilot configuration values."""
    from src.engines.pilot.config import (
        PILOT_DURATION_WEEKS,
        PILOT_INITIAL_CAPITAL,
        PILOT_UNIVERSE,
        AlertThresholds,
        MetricTargets,
    )

    return {
        "duration_weeks": PILOT_DURATION_WEEKS,
        "initial_capital": PILOT_INITIAL_CAPITAL,
        "universe": PILOT_UNIVERSE,
        "tickers": PILOT_TICKERS,
        "strategies": [c["name"] for c in PILOT_STRATEGY_CONFIGS],
        "alert_thresholds": {
            "signal_hr_warning": AlertThresholds.SIGNAL_HR_WARNING,
            "strategy_dd_warning": AlertThresholds.STRATEGY_DD_WARNING,
            "strategy_dd_critical": AlertThresholds.STRATEGY_DD_CRITICAL,
            "portfolio_vol_warning": AlertThresholds.PORTFOLIO_VOL_WARNING,
            "portfolio_vol_critical": AlertThresholds.PORTFOLIO_VOL_CRITICAL,
            "data_staleness_hours": AlertThresholds.DATA_STALENESS_HOURS,
        },
        "metric_targets": {
            "signal_hit_rate": MetricTargets.SIGNAL_HIT_RATE,
            "strategy_sharpe": MetricTargets.STRATEGY_SHARPE,
            "max_drawdown": MetricTargets.MAX_DRAWDOWN,
            "system_uptime": MetricTargets.SYSTEM_UPTIME,
            "min_criteria_for_go": MetricTargets.MIN_CRITERIA_FOR_GO,
        },
    }
