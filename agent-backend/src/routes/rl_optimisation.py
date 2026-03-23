"""src/routes/rl_optimisation.py — RL Portfolio Optimisation API."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from src.engines.rl_optimisation.models import RLConfig
from src.engines.rl_optimisation.engine import RLOptimisationEngine

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/alpha/rl-optimise", tags=["Alpha: RL Optimisation"], dependencies=[Depends(get_current_user)])

class RLOptimiseRequest(BaseModel):
    returns: dict[str, list[float]]
    episodes: int = 200
    gamma: float = 0.99
    learning_rate: float = 0.01
    risk_penalty: float = 0.5
    transaction_cost: float = 0.001
    hidden_size: int = 32
    lookback: int = 20

@router.post("/optimise")
async def optimise(req: RLOptimiseRequest):
    try:
        config = RLConfig(
            episodes=req.episodes, gamma=req.gamma, learning_rate=req.learning_rate,
            risk_penalty=req.risk_penalty, transaction_cost=req.transaction_cost,
            hidden_size=req.hidden_size, lookback=req.lookback,
        )
        result = RLOptimisationEngine.optimise(req.returns, config)
        return result.model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))
