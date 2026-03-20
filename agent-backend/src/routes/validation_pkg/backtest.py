"""
src/routes/validation_pkg/backtest.py
─────────────────────────────────────────────────────────────────────────────
Combination and regime-conditional backtesting endpoints.
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.engines.backtesting.engine import BacktestEngine
from src.engines.backtesting.models import (
    BacktestConfig,
    CombinationBacktestResult,
    RegimePerformanceReport,
)

logger = logging.getLogger("365advisers.routes.validation")

router = APIRouter(tags=["Quantitative Validation Framework"])

_backtest_engine = BacktestEngine()


class CombinationBacktestRequest(BaseModel):
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_groups: list[list[str]] = Field(
        ...,
        description="Each inner list is a combination of signal IDs to test jointly",
    )
    benchmark_ticker: str = "SPY"


class RegimeBacktestRequest(BaseModel):
    universe: list[str] = Field(..., min_length=1)
    start_date: date
    end_date: date = Field(default_factory=date.today)
    signal_ids: list[str] | None = None
    benchmark_ticker: str = "SPY"


@router.post(
    "/backtest/combination",
    response_model=list[CombinationBacktestResult],
    summary="Run combination backtesting",
)
async def run_combination_backtest(request: CombinationBacktestRequest):
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


@router.post(
    "/backtest/regime",
    response_model=list[RegimePerformanceReport],
    summary="Run regime-conditional backtesting",
)
async def run_regime_backtest(request: RegimeBacktestRequest):
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
