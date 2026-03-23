"""src/routes/factor_risk.py — Factor Risk Decomposition API."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from src.engines.factor_risk.engine import FactorRiskEngine

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/alpha/factor-risk", tags=["Alpha: Factor Risk"], dependencies=[Depends(get_current_user)])


class BuildModelRequest(BaseModel):
    asset_returns: dict[str, list[float]]
    factor_returns: dict[str, list[float]]

class DecomposeRequest(BaseModel):
    weights: dict[str, float]
    asset_returns: dict[str, list[float]]
    factor_returns: dict[str, list[float]]

class SyntheticRequest(BaseModel):
    n_obs: int = 252
    seed: int | None = None


@router.post("/model")
async def build_model(req: BuildModelRequest):
    """Build factor model (exposures + covariance)."""
    try:
        result = FactorRiskEngine.build_model(req.asset_returns, req.factor_returns)
        return result.model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/decompose")
async def decompose_risk(req: DecomposeRequest):
    """Full risk decomposition: exposures → covariance → factor contributions."""
    try:
        result = FactorRiskEngine.decompose_risk(req.weights, req.asset_returns, req.factor_returns)
        return result.model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/synthetic-factors")
async def synthetic_factors(req: SyntheticRequest):
    """Generate synthetic factor returns for demo/testing."""
    factors = FactorRiskEngine.generate_synthetic_factors(req.n_obs, req.seed)
    return {"factors": list(factors.keys()), "n_obs": req.n_obs, "data": factors}
