"""src/routes/attribution.py — Performance Attribution API."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from src.engines.attribution.engine import AttributionEngine

router = APIRouter(prefix="/alpha/attribution", tags=["Alpha: Attribution"])

class SinglePeriodRequest(BaseModel):
    portfolio_weights: dict[str, float]
    benchmark_weights: dict[str, float]
    portfolio_returns: dict[str, float]
    benchmark_returns: dict[str, float]

class MultiPeriodRequest(BaseModel):
    periods: list[dict]

@router.post("/single")
async def single_period(req: SinglePeriodRequest):
    try:
        return AttributionEngine.single_period(
            req.portfolio_weights, req.benchmark_weights,
            req.portfolio_returns, req.benchmark_returns,
        ).model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/multi")
async def multi_period(req: MultiPeriodRequest):
    try:
        periods = AttributionEngine.multi_period(req.periods)
        cumulative = AttributionEngine.cumulative_attribution(periods)
        return {"periods": [p.model_dump() for p in periods], "cumulative": cumulative}
    except Exception as e:
        raise HTTPException(500, str(e))
