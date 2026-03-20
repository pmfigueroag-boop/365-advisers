"""
src/routes/validation_pkg/performance.py
─────────────────────────────────────────────────────────────────────────────
Rolling performance, degradation alerts, recalibration, and QVF dashboard.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.engines.backtesting.models import CalibrationSuggestion
from src.engines.backtesting.recalibration_engine import RecalibrationEngine
from src.engines.backtesting.rolling_analyzer import (
    DegradationReport,
    RollingPerformanceSnapshot,
)
from src.engines.opportunity_tracking.tracker import OpportunityTracker
from src.engines.opportunity_tracking.models import (
    DetectorAccuracy,
    OpportunityPerformanceSummary,
)
from src.engines.opportunity_tracking.repository import OpportunityRepository

logger = logging.getLogger("365advisers.routes.validation")

router = APIRouter(tags=["Quantitative Validation Framework"])

_recalibration_engine = RecalibrationEngine()
_opportunity_tracker = OpportunityTracker()


class RecalibrationRequest(BaseModel):
    suggestion_ids: list[int] | None = None
    dry_run: bool = True


class QVFDashboardResponse(BaseModel):
    rolling_snapshots: list[RollingPerformanceSnapshot] = Field(default_factory=list)
    degradation_alerts: list[DegradationReport] = Field(default_factory=list)
    opportunity_summary: OpportunityPerformanceSummary | None = None
    top_performers: list[str] = Field(default_factory=list)
    recalibration_suggestions: list[CalibrationSuggestion] = Field(default_factory=list)


@router.get(
    "/performance/rolling/{signal_id}",
    response_model=list[RollingPerformanceSnapshot],
    summary="Get rolling performance snapshots",
)
async def get_rolling_performance(signal_id: str):
    from src.engines.backtesting.performance_repository import SignalPerformanceRepository
    from src.engines.backtesting.rolling_analyzer import RollingAnalyzer

    events = SignalPerformanceRepository.get_events_for_signal(signal_id)
    if not events:
        return []
    analyzer = RollingAnalyzer()
    return analyzer.compute_rolling_metrics(signal_id, events)


@router.get(
    "/performance/degradation",
    response_model=list[DegradationReport],
    summary="Get active degradation alerts",
)
async def get_degradation_alerts():
    return _recalibration_engine.scan_for_degradation()


@router.get(
    "/opportunities/summary",
    response_model=OpportunityPerformanceSummary,
    summary="Get opportunity tracking summary",
)
async def get_opportunity_summary(
    idea_type: str | None = Query(None, description="Filter by detector type"),
    min_age_days: int = Query(20, ge=1, le=365),
):
    return _opportunity_tracker.get_performance_summary(idea_type, min_age_days)


@router.get(
    "/opportunities/{idea_uid}",
    summary="Get single idea forward performance",
)
async def get_opportunity_detail(idea_uid: str):
    record = OpportunityRepository.get_by_idea_uid(idea_uid)
    if not record:
        raise HTTPException(status_code=404, detail=f"Idea {idea_uid} not found")
    return {
        "idea_uid": record.idea_uid,
        "ticker": record.ticker,
        "idea_type": record.idea_type,
        "confidence": record.confidence,
        "signal_strength": record.signal_strength,
        "opportunity_score": record.opportunity_score,
        "price_at_gen": record.price_at_gen,
        "generated_at": record.generated_at.isoformat() if record.generated_at else None,
        "return_1d": record.return_1d,
        "return_5d": record.return_5d,
        "return_20d": record.return_20d,
        "return_60d": record.return_60d,
        "benchmark_return_20d": record.benchmark_return_20d,
        "excess_return_20d": record.excess_return_20d,
        "tracking_status": record.tracking_status,
    }


@router.get(
    "/opportunities/accuracy",
    response_model=dict[str, DetectorAccuracy],
    summary="Get per-detector accuracy",
)
async def get_detector_accuracy():
    return _opportunity_tracker.get_detector_accuracy()


@router.post(
    "/recalibrate",
    response_model=list[CalibrationSuggestion],
    summary="Run recalibration scan (dry-run)",
)
async def run_recalibration():
    degraded = _recalibration_engine.scan_for_degradation()
    return _recalibration_engine.generate_recalibration_plan(degraded)


@router.post(
    "/recalibrate/apply",
    summary="Apply recalibration suggestions",
)
async def apply_recalibration(request: RecalibrationRequest):
    degraded = _recalibration_engine.scan_for_degradation()
    suggestions = _recalibration_engine.generate_recalibration_plan(degraded)
    records = _recalibration_engine.auto_apply(suggestions, dry_run=request.dry_run)
    return {
        "mode": "dry_run" if request.dry_run else "live",
        "applied": len(records),
        "records": [r.model_dump() for r in records],
    }


@router.get(
    "/dashboard",
    response_model=QVFDashboardResponse,
    summary="Unified QVF dashboard",
)
async def get_qvf_dashboard():
    try:
        snapshots = _recalibration_engine.compute_rolling_snapshots()
        degraded = _recalibration_engine.scan_for_degradation()
        opp_summary = _opportunity_tracker.get_performance_summary()
        top = _recalibration_engine.identify_top_performers()
        suggestions = _recalibration_engine.generate_recalibration_plan(degraded)

        return QVFDashboardResponse(
            rolling_snapshots=snapshots[:50],
            degradation_alerts=degraded,
            opportunity_summary=opp_summary,
            top_performers=top,
            recalibration_suggestions=suggestions,
        )
    except Exception as exc:
        logger.error("VALIDATION-API: Dashboard failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# Validation Intelligence Dashboard
from src.engines.validation_dashboard.aggregator import DashboardAggregator
from src.engines.validation_dashboard.models import ValidationIntelligence

_dashboard_aggregator = DashboardAggregator()


@router.get(
    "/intelligence",
    response_model=ValidationIntelligence,
    summary="Validation Intelligence Dashboard",
)
async def get_validation_intelligence():
    try:
        return _dashboard_aggregator.aggregate()
    except Exception as exc:
        logger.error("VALIDATION-API: Intelligence dashboard failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
