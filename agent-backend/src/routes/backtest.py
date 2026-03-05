"""
src/routes/backtest.py
──────────────────────────────────────────────────────────────────────────────
REST API endpoints for the Alpha Signal Backtesting Engine.

POST /backtest/run                    → Start a backtest run
GET  /backtest/runs                   → List all backtest runs
GET  /backtest/runs/{id}              → Get report for a specific run
GET  /backtest/signal/{id}            → Get performance for a specific signal
GET  /backtest/calibration            → Get latest calibration suggestions
GET  /backtest/events/{signal_id}     → List historical firing events
GET  /backtest/scorecard/{signal_id}  → Live signal scorecard
GET  /backtest/scorecards             → All signal scorecards
POST /backtest/calibrate/{signal_id}  → Apply a calibration
GET  /backtest/calibration/history    → Calibration audit trail
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.engines.backtesting.engine import BacktestEngine
from src.engines.backtesting.models import (
    BacktestConfig,
    BacktestReport,
    BacktestRunSummary,
    CalibrationSuggestion,
    SignalPerformanceRecord,
    SignalScorecard,
)
from src.engines.backtesting.performance_repository import SignalPerformanceRepository
from src.engines.backtesting.performance_service import SignalPerformanceService

logger = logging.getLogger("365advisers.routes.backtest")

router = APIRouter(prefix="/backtest", tags=["backtesting"])

# Shared instances
_engine = BacktestEngine()
_perf_service = SignalPerformanceService()


# ─── Request / Response Models ───────────────────────────────────────────────

class BacktestStartRequest(BaseModel):
    """API request to start a backtest run."""
    universe: list[str] = Field(
        ..., min_length=1, description="Ticker symbols to backtest",
    )
    start_date: str = Field(
        ..., description="Lookback start date (YYYY-MM-DD)",
    )
    end_date: str | None = Field(
        None, description="Lookback end date (YYYY-MM-DD), defaults to today",
    )
    forward_windows: list[int] = Field(
        default=[1, 5, 10, 20, 60],
        description="T+N days for return measurement",
    )
    min_observations: int = Field(
        30, ge=5, description="Minimum firings for valid statistics",
    )
    signal_ids: list[str] | None = Field(
        None, description="Specific signal IDs (None = all enabled)",
    )
    benchmark_ticker: str = Field(
        "SPY", description="Benchmark ticker for excess returns",
    )


class BacktestStartResponse(BaseModel):
    """API response after starting a backtest."""
    run_id: str
    status: str
    message: str


class CalibrateRequest(BaseModel):
    """API request to apply a calibration suggestion."""
    parameter: str = Field(..., description="threshold | weight | half_life")
    current_value: float
    suggested_value: float
    evidence: str = ""


# ─── Backtest Engine Endpoints ───────────────────────────────────────────────

@router.post("/run", response_model=BacktestStartResponse)
async def start_backtest(request: BacktestStartRequest):
    """Start a new backtest run."""
    try:
        config = BacktestConfig(
            universe=[t.upper() for t in request.universe],
            start_date=date.fromisoformat(request.start_date),
            end_date=(
                date.fromisoformat(request.end_date)
                if request.end_date
                else date.today()
            ),
            forward_windows=request.forward_windows,
            min_observations=request.min_observations,
            signal_ids=request.signal_ids,
            benchmark_ticker=request.benchmark_ticker.upper(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {exc}")

    report = await _engine.run(config)

    return BacktestStartResponse(
        run_id=report.run_id,
        status=report.status.value,
        message=(
            f"Backtest completed in {report.execution_time_seconds:.1f}s — "
            f"{len(report.signal_results)} signal results"
            if report.status.value == "completed"
            else f"Backtest {report.status.value}: {report.error_message or 'unknown error'}"
        ),
    )


@router.get("/runs", response_model=list[BacktestRunSummary])
async def list_runs(limit: int = 20):
    """List recent backtest runs."""
    return _engine.list_runs(limit)


@router.get("/runs/{run_id}")
async def get_report(run_id: str):
    """Get the full report for a specific backtest run."""
    report = await _engine.get_report(run_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return report.model_dump(mode="json")


@router.get("/signal/{signal_id}", response_model=SignalPerformanceRecord | None)
async def get_signal_performance(signal_id: str):
    """Get the latest backtest performance for a specific signal."""
    result = _engine.get_signal_performance(signal_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No backtest results found for signal '{signal_id}'",
        )
    return result


@router.get("/calibration")
async def get_calibration():
    """Get calibration suggestions from the most recent backtest run."""
    runs = _engine.list_runs(limit=1)
    if not runs:
        return {"suggestions": [], "message": "No backtest runs found"}

    report = await _engine.get_report(runs[0].run_id)
    if not report:
        return {"suggestions": [], "message": "Report not available"}

    return {
        "run_id": report.run_id,
        "suggestions": [s.model_dump() for s in report.calibration_suggestions],
        "total": len(report.calibration_suggestions),
    }


# ─── Signal Performance Database Endpoints ──────────────────────────────────

@router.get("/events/{signal_id}")
async def get_signal_events(
    signal_id: str,
    ticker: str | None = None,
    limit: int = 100,
):
    """List historical firing events for a signal."""
    events = SignalPerformanceRepository.get_events(signal_id, ticker, limit)
    return {
        "signal_id": signal_id,
        "events": [e.model_dump(mode="json") for e in events],
        "total": len(events),
    }


@router.get("/scorecard/{signal_id}", response_model=SignalScorecard | None)
async def get_signal_scorecard(signal_id: str):
    """Get the live scorecard for a specific signal."""
    scorecard = _perf_service.get_scorecard(signal_id)
    if not scorecard:
        raise HTTPException(
            status_code=404,
            detail=f"No scorecard available for signal '{signal_id}'",
        )
    return scorecard


@router.get("/scorecards", response_model=list[SignalScorecard])
async def get_all_scorecards():
    """Get scorecards for all signals with sufficient backtest data."""
    return _perf_service.get_all_scorecards()


@router.post("/calibrate/{signal_id}")
async def apply_calibration(signal_id: str, request: CalibrateRequest):
    """Apply a calibration suggestion to a signal."""
    suggestion = CalibrationSuggestion(
        signal_id=signal_id,
        parameter=request.parameter,
        current_value=request.current_value,
        suggested_value=request.suggested_value,
        evidence=request.evidence,
    )
    record = _perf_service.apply_calibration(suggestion, applied_by="manual")
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Signal '{signal_id}' not found in registry",
        )
    return {
        "status": "applied",
        "signal_id": signal_id,
        "parameter": request.parameter,
        "old_value": request.current_value,
        "new_value": request.suggested_value,
    }


@router.get("/calibration/history")
async def get_calibration_history(
    signal_id: str | None = None,
    limit: int = 50,
):
    """Get calibration audit trail."""
    records = SignalPerformanceRepository.get_calibration_history(signal_id, limit)
    return {
        "records": [r.model_dump(mode="json") for r in records],
        "total": len(records),
    }
