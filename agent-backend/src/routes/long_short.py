"""
src/routes/long_short.py
──────────────────────────────────────────────────────────────────────────────
API endpoints for the Long/Short Equity Engine.

Provides:
  POST /alpha/long-short/construct   → Build a L/S portfolio
  POST /alpha/long-short/exposure    → Calculate exposure metrics
  GET  /alpha/long-short/borrow-cost/{ticker} → Estimate borrow cost
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.engines.long_short.engine import LongShortEngine
from src.engines.long_short.exposure import ExposureCalculator
from src.engines.long_short.borrow_cost import BorrowCostEstimator
from src.engines.long_short.models import (
    LongShortPosition,
    PositionSide,
    ExposureMetrics,
    BorrowCostEstimate,
)

logger = logging.getLogger("365advisers.routes.long_short")

router = APIRouter(prefix="/alpha/long-short", tags=["Alpha: Long/Short"])


# ── Request / Response schemas ───────────────────────────────────────────────

class ConstructRequest(BaseModel):
    """Request to build a Long/Short portfolio."""
    long_candidates: list[dict[str, Any]] = Field(
        ..., description="List of long candidate dicts (ticker, weight, beta, sector, volatility_atr)"
    )
    short_candidates: list[dict[str, Any]] = Field(
        ..., description="List of short candidate dicts (same schema)"
    )
    max_gross_exposure: float = Field(2.0, ge=0.5, le=5.0)
    max_net_exposure: float = Field(0.30, ge=0.0, le=1.0)
    max_single_position: float = Field(0.10, ge=0.01, le=0.50)


class ExposureRequest(BaseModel):
    """Request to calculate exposure from position lists."""
    long_positions: list[dict[str, Any]] = Field(default_factory=list)
    short_positions: list[dict[str, Any]] = Field(default_factory=list)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/construct")
async def construct_portfolio(req: ConstructRequest):
    """
    Build a Long/Short portfolio from candidate lists.

    Applies volatility parity sizing per leg, borrow-cost estimation,
    and enforces gross/net/beta exposure constraints.
    """
    try:
        result = LongShortEngine.construct(
            long_candidates=req.long_candidates,
            short_candidates=req.short_candidates,
            max_gross_exposure=req.max_gross_exposure,
            max_net_exposure=req.max_net_exposure,
            max_single_position=req.max_single_position,
        )
        return result.model_dump()
    except Exception as e:
        logger.error("L/S construct failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/exposure")
async def calculate_exposure(req: ExposureRequest):
    """
    Calculate exposure metrics for a set of positions.

    Returns gross, net, beta exposure, and leverage ratio.
    """
    try:
        longs = [
            LongShortPosition(
                ticker=p.get("ticker", "???"),
                side=PositionSide.LONG,
                weight=p.get("weight", 0.0),
                beta=p.get("beta", 1.0),
            )
            for p in req.long_positions
            if p.get("weight", 0) > 0
        ]
        shorts = [
            LongShortPosition(
                ticker=p.get("ticker", "???"),
                side=PositionSide.SHORT,
                weight=p.get("weight", 0.0),
                beta=p.get("beta", 1.0),
            )
            for p in req.short_positions
            if p.get("weight", 0) > 0
        ]
        exposure = ExposureCalculator.calculate(longs, shorts)
        return {
            **exposure.model_dump(),
            "is_market_neutral": ExposureCalculator.is_market_neutral(exposure),
            "is_dollar_neutral": ExposureCalculator.is_dollar_neutral(exposure),
        }
    except Exception as e:
        logger.error("Exposure calc failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/borrow-cost/{ticker}")
async def get_borrow_cost(
    ticker: str,
    market_cap: float | None = None,
    avg_volume: float | None = None,
    short_interest: float | None = None,
):
    """
    Estimate the borrow cost for shorting a ticker.

    Query params allow overriding the proxy inputs; otherwise defaults
    are used.
    """
    try:
        estimate = BorrowCostEstimator.estimate(
            ticker=ticker.upper(),
            market_cap=market_cap,
            avg_daily_volume=avg_volume,
            short_interest_pct=short_interest,
        )
        return estimate.model_dump()
    except Exception as e:
        logger.error("Borrow cost failed for %s: %s", ticker, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
