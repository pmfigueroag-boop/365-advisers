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

    data = report.model_dump(mode="json")

    # ── Flatten dict-keyed metrics for the frontend ───────────────────────
    # Backend stores metrics keyed by forward window: {1: 0.5, 5: 0.6, 20: 0.7}
    # Frontend expects flat scalars: win_rate, avg_return, sharpe_ratio, etc.
    # We use T+20 as the reference window (most common for swing analysis).
    if data.get("signal_results"):
        for sr in data["signal_results"]:
            _ref = 20  # Reference forward window
            _best_window = max(
                (sr.get("sharpe_ratio") or {}).keys(),
                key=lambda w: (sr.get("sharpe_ratio") or {}).get(w, 0.0),
                default=_ref,
            ) if sr.get("sharpe_ratio") else _ref

            # Flatten hit_rate → win_rate (as percentage)
            hit_rate = sr.get("hit_rate", {})
            sr["win_rate"] = (
                hit_rate.get(str(_ref)) or hit_rate.get(_ref, 0.0)
            ) * 100

            # Flatten avg_return
            avg_ret = sr.get("avg_return", {})
            sr["avg_return_flat"] = (
                avg_ret.get(str(_ref)) or avg_ret.get(_ref, 0.0)
            )

            # Flatten sharpe_ratio
            sharpe = sr.get("sharpe_ratio", {})
            sr["sharpe_ratio_flat"] = (
                sharpe.get(str(_ref)) or sharpe.get(_ref, 0.0)
            )

            # Compute max/min returns from all events (approximation from avg ± 2σ)
            sr["max_return"] = max(
                ((sr.get("avg_return") or {}).get(str(w)) or
                 (sr.get("avg_return") or {}).get(w, 0.0))
                for w in [1, 5, 10, 20, 60]
                if ((sr.get("avg_return") or {}).get(str(w)) or
                    (sr.get("avg_return") or {}).get(w)) is not None
            ) if sr.get("avg_return") else 0.0

            sr["min_return"] = min(
                ((sr.get("avg_return") or {}).get(str(w)) or
                 (sr.get("avg_return") or {}).get(w, 0.0))
                for w in [1, 5, 10, 20, 60]
                if ((sr.get("avg_return") or {}).get(str(w)) or
                    (sr.get("avg_return") or {}).get(w)) is not None
            ) if sr.get("avg_return") else 0.0

            # Profit factor (wins / abs(losses)), estimate from hit_rate + avg_return
            hr = sr["win_rate"] / 100.0 if sr["win_rate"] else 0.0
            ar = sr["avg_return_flat"]
            if hr > 0.0 and hr < 1.0 and ar != 0.0:
                avg_win = abs(ar) / hr if hr > 0 else 0.0
                avg_loss = abs(ar) / (1.0 - hr) if (1.0 - hr) > 0 else 0.0
                sr["profit_factor"] = round(
                    (avg_win * hr) / max(avg_loss * (1.0 - hr), 0.001), 2
                )
            else:
                sr["profit_factor"] = 0.0

            # Also set ticker field (frontend expects it)
            if not sr.get("ticker"):
                sr["ticker"] = sr.get("signal_name", sr.get("signal_id", ""))

    # ── LLM Backtest Memo (non-blocking) ──────────────────────────────────
    if data.get("signal_results"):
        try:
            import asyncio
            from src.engines.backtesting.backtest_memo_agent import synthesize_backtest_memo

            backtest_memo = await asyncio.to_thread(
                synthesize_backtest_memo,
                ticker=data.get("ticker", run_id),
                backtest_results=data["signal_results"],
            )
            data["backtest_memo"] = backtest_memo
            logger.info(f"BACKTEST: LLM memo generated for run {run_id}")
        except Exception as exc:
            logger.warning(f"BACKTEST: Memo agent failed for {run_id}: {exc}")
            # Non-fatal — response is complete without memo

    return data


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


@router.get("/weights")
async def get_dynamic_weights():
    """Get current dynamic weights for all signals with backtest data."""
    from src.engines.backtesting.dynamic_weights import DynamicWeightEngine

    engine = DynamicWeightEngine()
    profile = engine.compute_all()
    return {
        "weights": profile.weights,
        "details": [d.model_dump() for d in profile.details],
        "signal_count": profile.signal_count,
        "computed_at": profile.computed_at.isoformat(),
        "config": profile.config.model_dump(),
    }
