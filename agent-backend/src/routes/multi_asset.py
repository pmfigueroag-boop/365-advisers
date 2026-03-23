"""src/routes/multi_asset.py — Multi-Asset Data Layer API."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from src.engines.multi_asset.engine import MultiAssetEngine

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/alpha/multi-asset", tags=["Alpha: Multi-Asset"], dependencies=[Depends(get_current_user)])
_engine = MultiAssetEngine()

class CorrelationRequest(BaseModel):
    prices: dict[str, list[float]] = Field(..., description="Ticker → price series")
    method: str = "pearson"
    return_type: str = "log"

@router.post("/correlations")
async def compute_correlations(req: CorrelationRequest):
    try:
        result = MultiAssetEngine.normalise_and_correlate(req.prices, req.method, req.return_type)
        return result.model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/universe")
async def get_universe():
    return _engine.get_universe().model_dump()
