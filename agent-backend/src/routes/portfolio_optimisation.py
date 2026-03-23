"""src/routes/portfolio_optimisation.py — Portfolio Optimisation API."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from src.engines.portfolio_optimisation.models import OptimisationObjective, PortfolioConstraints
from src.engines.portfolio_optimisation.engine import PortfolioOptimisationEngine

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/alpha/optimise", tags=["Alpha: Portfolio Optimisation"], dependencies=[Depends(get_current_user)])

class OptimiseRequest(BaseModel):
    expected_returns: dict[str, float]
    covariance: list[list[float]]
    objective: OptimisationObjective = OptimisationObjective.MAX_SHARPE
    risk_free_rate: float = 0.0
    target_return: float | None = None
    target_risk: float | None = None
    constraints: PortfolioConstraints | None = None

class FrontierRequest(BaseModel):
    expected_returns: dict[str, float]
    covariance: list[list[float]]
    risk_free_rate: float = 0.0
    num_points: int = 50
    constraints: PortfolioConstraints | None = None

class BLRequest(BaseModel):
    covariance: list[list[float]]
    market_caps: dict[str, float]
    views: list[dict] = Field(default_factory=list)
    objective: OptimisationObjective = OptimisationObjective.MAX_SHARPE
    risk_aversion: float = 2.5
    tau: float = 0.05
    risk_free_rate: float = 0.0
    constraints: PortfolioConstraints | None = None

class FromReturnsRequest(BaseModel):
    returns: dict[str, list[float]]
    objective: OptimisationObjective = OptimisationObjective.MAX_SHARPE
    risk_free_rate: float = 0.0
    constraints: PortfolioConstraints | None = None

@router.post("/solve")
async def optimise(req: OptimiseRequest):
    try:
        return PortfolioOptimisationEngine.optimise(
            req.expected_returns, req.covariance, req.objective,
            req.constraints, req.risk_free_rate, req.target_return, req.target_risk,
        ).model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/frontier")
async def frontier(req: FrontierRequest):
    try:
        return PortfolioOptimisationEngine.efficient_frontier(
            req.expected_returns, req.covariance, req.constraints,
            req.risk_free_rate, req.num_points,
        ).model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/black-litterman")
async def black_litterman(req: BLRequest):
    try:
        return PortfolioOptimisationEngine.black_litterman_optimise(
            req.covariance, req.market_caps, req.views,
            req.objective, req.constraints, req.risk_aversion,
            req.tau, req.risk_free_rate,
        ).model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/from-returns")
async def from_returns(req: FromReturnsRequest):
    try:
        return PortfolioOptimisationEngine.from_returns_data(
            req.returns, req.objective, req.constraints, req.risk_free_rate,
        ).model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))
