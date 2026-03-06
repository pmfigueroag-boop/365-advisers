"""
src/routes/validation.py
──────────────────────────────────────────────────────────────────────────────
REST API endpoints for the Quantitative Validation Framework (QVF).

Provides access to:
  - Combination and regime-conditional backtesting
  - Rolling performance snapshots and degradation alerts
  - Opportunity performance tracking
  - Automated recalibration (with dry-run support)
  - Unified QVF dashboard
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.engines.backtesting.engine import BacktestEngine
from src.engines.backtesting.models import (
    BacktestConfig,
    CombinationBacktestResult,
    RegimePerformanceReport,
    CalibrationSuggestion,
)
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

router = APIRouter(prefix="/validation", tags=["Quantitative Validation Framework"])


# ─── Request Models ──────────────────────────────────────────────────────────

class CombinationBacktestRequest(BaseModel):
    """Request to run combination backtesting."""
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_groups: list[list[str]] = Field(
        ...,
        description="Each inner list is a combination of signal IDs to test jointly",
    )
    benchmark_ticker: str = "SPY"


class RegimeBacktestRequest(BaseModel):
    """Request to run regime-conditional backtesting."""
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_ids: list[str] | None = None
    benchmark_ticker: str = "SPY"


class RecalibrationRequest(BaseModel):
    """Request to apply recalibration suggestions."""
    suggestion_ids: list[int] | None = None
    dry_run: bool = True


class QVFDashboardResponse(BaseModel):
    """Unified dashboard data for the QVF."""
    rolling_snapshots: list[RollingPerformanceSnapshot] = Field(default_factory=list)
    degradation_alerts: list[DegradationReport] = Field(default_factory=list)
    opportunity_summary: OpportunityPerformanceSummary | None = None
    top_performers: list[str] = Field(default_factory=list)
    recalibration_suggestions: list[CalibrationSuggestion] = Field(default_factory=list)


# ─── Singleton engine instances ──────────────────────────────────────────────

_backtest_engine = BacktestEngine()
_recalibration_engine = RecalibrationEngine()
_opportunity_tracker = OpportunityTracker()


# ─── Combination Backtest ────────────────────────────────────────────────────

@router.post(
    "/backtest/combination",
    response_model=list[CombinationBacktestResult],
    summary="Run combination backtesting",
)
async def run_combination_backtest(request: CombinationBacktestRequest):
    """
    Test signal combinations using AND logic.

    For each group, finds dates where ALL signals fired simultaneously,
    then measures joint forward returns and computes incremental alpha.
    """
    config = BacktestConfig(
        universe=request.universe,
        start_date=request.start_date,
        end_date=request.end_date,
        benchmark_ticker=request.benchmark_ticker,
    )
    try:
        results = await _backtest_engine.run_combination(config, request.signal_groups)
        return results
    except Exception as exc:
        logger.error("VALIDATION-API: Combination backtest failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Regime-Conditional Backtest ─────────────────────────────────────────────

@router.post(
    "/backtest/regime",
    response_model=list[RegimePerformanceReport],
    summary="Run regime-conditional backtesting",
)
async def run_regime_backtest(request: RegimeBacktestRequest):
    """
    Partition historical data into Bull/Bear/Range/HighVol regimes
    and compute per-signal performance within each regime.
    """
    config = BacktestConfig(
        universe=request.universe,
        start_date=request.start_date,
        end_date=request.end_date,
        signal_ids=request.signal_ids,
        benchmark_ticker=request.benchmark_ticker,
    )
    try:
        results = await _backtest_engine.run_regime_conditional(config)
        return results
    except Exception as exc:
        logger.error("VALIDATION-API: Regime backtest failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Rolling Performance ────────────────────────────────────────────────────

@router.get(
    "/performance/rolling/{signal_id}",
    response_model=list[RollingPerformanceSnapshot],
    summary="Get rolling performance snapshots",
)
async def get_rolling_performance(signal_id: str):
    """Return rolling performance snapshots (30D/90D/252D) for a signal."""
    from src.engines.backtesting.performance_repository import SignalPerformanceRepository
    from src.engines.backtesting.rolling_analyzer import RollingAnalyzer

    events = SignalPerformanceRepository.get_events_for_signal(signal_id)
    if not events:
        return []

    analyzer = RollingAnalyzer()
    return analyzer.compute_rolling_metrics(signal_id, events)


# ─── Degradation Alerts ─────────────────────────────────────────────────────

@router.get(
    "/performance/degradation",
    response_model=list[DegradationReport],
    summary="Get active degradation alerts",
)
async def get_degradation_alerts():
    """Return all active (unresolved) signal degradation alerts."""
    return _recalibration_engine.scan_for_degradation()


# ─── Opportunity Tracking ───────────────────────────────────────────────────

@router.get(
    "/opportunities/summary",
    response_model=OpportunityPerformanceSummary,
    summary="Get opportunity tracking summary",
)
async def get_opportunity_summary(
    idea_type: str | None = Query(None, description="Filter by detector type"),
    min_age_days: int = Query(20, ge=1, le=365),
):
    """Aggregate performance of generated ideas by detector type and confidence."""
    return _opportunity_tracker.get_performance_summary(idea_type, min_age_days)


@router.get(
    "/opportunities/{idea_uid}",
    summary="Get single idea forward performance",
)
async def get_opportunity_detail(idea_uid: str):
    """Return tracking record for a specific idea."""
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
    """Per-detector precision: what % of ideas generated positive returns."""
    return _opportunity_tracker.get_detector_accuracy()


# ─── Recalibration ──────────────────────────────────────────────────────────

@router.post(
    "/recalibrate",
    response_model=list[CalibrationSuggestion],
    summary="Run recalibration scan (dry-run)",
)
async def run_recalibration():
    """
    Scan all signals for degradation and generate recalibration suggestions.
    Does NOT apply changes — use /recalibrate/apply for that.
    """
    degraded = _recalibration_engine.scan_for_degradation()
    return _recalibration_engine.generate_recalibration_plan(degraded)


@router.post(
    "/recalibrate/apply",
    summary="Apply recalibration suggestions",
)
async def apply_recalibration(request: RecalibrationRequest):
    """Apply recalibration suggestions to the live registry."""
    degraded = _recalibration_engine.scan_for_degradation()
    suggestions = _recalibration_engine.generate_recalibration_plan(degraded)
    records = _recalibration_engine.auto_apply(suggestions, dry_run=request.dry_run)
    return {
        "mode": "dry_run" if request.dry_run else "live",
        "applied": len(records),
        "records": [r.model_dump() for r in records],
    }


# ─── Dashboard ──────────────────────────────────────────────────────────────

@router.get(
    "/dashboard",
    response_model=QVFDashboardResponse,
    summary="Unified QVF dashboard",
)
async def get_qvf_dashboard():
    """
    Aggregated view of the Quantitative Validation Framework.

    Returns rolling performance, degradation alerts, opportunity summary,
    top performers, and pending recalibration suggestions.
    """
    try:
        # Rolling snapshots (latest for all signals)
        snapshots = _recalibration_engine.compute_rolling_snapshots()

        # Degradation
        degraded = _recalibration_engine.scan_for_degradation()

        # Opportunities
        opp_summary = _opportunity_tracker.get_performance_summary()

        # Top performers
        top = _recalibration_engine.identify_top_performers()

        # Suggestions
        suggestions = _recalibration_engine.generate_recalibration_plan(degraded)

        return QVFDashboardResponse(
            rolling_snapshots=snapshots[:50],  # Limit for response size
            degradation_alerts=degraded,
            opportunity_summary=opp_summary,
            top_performers=top,
            recalibration_suggestions=suggestions,
        )
    except Exception as exc:
        logger.error("VALIDATION-API: Dashboard failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
