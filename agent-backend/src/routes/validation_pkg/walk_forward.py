"""
src/routes/validation_pkg/walk_forward.py
─────────────────────────────────────────────────────────────────────────────
Walk-forward validation endpoints.
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.engines.walk_forward.engine import WalkForwardEngine
from src.engines.walk_forward.models import (
    WalkForwardConfig,
    WalkForwardMode,
)
from src.engines.walk_forward.repository import WalkForwardRepository

logger = logging.getLogger("365advisers.routes.validation")

router = APIRouter(tags=["Quantitative Validation Framework"])

_wf_engine = WalkForwardEngine()
_wf_repo = WalkForwardRepository()


class WalkForwardRequest(BaseModel):
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    train_days: int = 756
    test_days: int = 126
    step_days: int | None = None
    mode: str = "rolling"
    signal_ids: list[str] | None = None
    benchmark_ticker: str = "SPY"
    min_train_events: int = 30
    is_hit_rate_threshold: float = 0.50


@router.post(
    "/walk-forward",
    summary="Start a walk-forward validation run",
)
async def start_walk_forward(request: WalkForwardRequest):
    try:
        config = WalkForwardConfig(
            universe=request.universe,
            start_date=request.start_date,
            end_date=request.end_date,
            train_days=request.train_days,
            test_days=request.test_days,
            step_days=request.step_days,
            mode=WalkForwardMode(request.mode),
            signal_ids=request.signal_ids,
            benchmark_ticker=request.benchmark_ticker,
            min_train_events=request.min_train_events,
            is_hit_rate_threshold=request.is_hit_rate_threshold,
        )
        run = await _wf_engine.run(config)

        if run.status == "completed":
            _wf_repo.save_run(run)

        return run.model_dump()
    except Exception as exc:
        logger.error("VALIDATION-API: Walk-forward failed — %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/walk-forward/runs",
    summary="List recent walk-forward runs",
)
async def list_walk_forward_runs(limit: int = Query(20, ge=1, le=100)):
    return _wf_repo.list_runs(limit=limit)


@router.get(
    "/walk-forward/{run_id}",
    summary="Get walk-forward run report",
)
async def get_walk_forward_run(run_id: str):
    summary = _wf_repo.get_run_summary(run_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return summary


@router.get(
    "/walk-forward/{run_id}/signal/{signal_id}",
    summary="Get signal detail in a walk-forward run",
)
async def get_walk_forward_signal(run_id: str, signal_id: str):
    results = _wf_repo.get_signal_results(run_id, signal_id)
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No results for signal {signal_id} in run {run_id}",
        )
    return results


@router.get(
    "/walk-forward/stability/{signal_id}",
    summary="Get latest stability score for a signal",
)
async def get_signal_stability(signal_id: str):
    runs = _wf_repo.list_runs(limit=1)
    if not runs:
        raise HTTPException(status_code=404, detail="No walk-forward runs found")

    latest_run_id = runs[0]["run_id"]
    results = _wf_repo.get_signal_results(latest_run_id, signal_id)
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"Signal {signal_id} not found in latest run {latest_run_id}",
        )
    return {
        "signal_id": signal_id,
        "run_id": latest_run_id,
        "fold_results": results,
    }
