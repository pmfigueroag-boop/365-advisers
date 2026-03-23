"""
src/routes/crowding.py
──────────────────────────────────────────────────────────────────────────────
REST API endpoints for the Signal Crowding Detection Engine.

GET  /crowding/{ticker}   → Crowding assessment for a ticker
POST /crowding/batch       → Batch assessment for multiple tickers
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.engines.crowding.engine import CrowdingEngine

logger = logging.getLogger("365advisers.routes.crowding")

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/crowding", tags=["crowding"], dependencies=[Depends(get_current_user)])

_engine = CrowdingEngine()


# ─── Request Models ─────────────────────────────────────────────────────────

class CrowdingBatchRequest(BaseModel):
    """Request for batch crowding assessment."""
    tickers: list[str] = Field(..., min_length=1)
    flow_data: dict[str, dict] = Field(
        default_factory=dict,
        description="{ticker: {net_flows_5d, mean_flow_60d, std_flow_60d}}",
    )
    inst_data: dict[str, dict] = Field(
        default_factory=dict,
        description="{ticker: {inst_ownership_change, sector_avg_change}}",
    )
    vol_data: dict[str, dict] = Field(
        default_factory=dict,
        description="{ticker: {realized_vol_20d, implied_vol_30d}}",
    )


# ─── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/{ticker}")
async def get_crowding_assessment(ticker: str):
    """Get crowding risk assessment for a single ticker."""
    result = _engine.assess(ticker=ticker.upper())
    return result.model_dump(mode="json")


@router.post("/batch")
async def batch_crowding_assessment(request: CrowdingBatchRequest):
    """Batch crowding assessment for multiple tickers."""
    results = _engine.assess_batch(
        tickers=[t.upper() for t in request.tickers],
        flow_data=request.flow_data,
        inst_data=request.inst_data,
        vol_data=request.vol_data,
    )
    return {
        "results": {t: r.model_dump(mode="json") for t, r in results.items()},
        "count": len(results),
    }
