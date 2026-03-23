"""src/routes/capital_allocation.py — Capital Allocation API."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from src.engines.capital_allocation.models import AllocationMethod, StrategyBudget
from src.engines.capital_allocation.engine import CapitalAllocationEngine

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/alpha/capital", tags=["Alpha: Capital Allocation"], dependencies=[Depends(get_current_user)])

class AllocateRequest(BaseModel):
    strategies: list[StrategyBudget]
    method: AllocationMethod = AllocationMethod.EQUAL
    total_capital: float = 1_000_000.0

class DriftRequest(BaseModel):
    strategies: list[StrategyBudget]
    threshold: float = 0.05

@router.post("/allocate")
async def allocate(req: AllocateRequest):
    try:
        return CapitalAllocationEngine.allocate(req.strategies, req.method, req.total_capital).model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/drift")
async def check_drift(req: DriftRequest):
    try:
        return CapitalAllocationEngine.check_drift(req.strategies, req.threshold).model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/rebalance")
async def rebalance(req: DriftRequest):
    try:
        return CapitalAllocationEngine.rebalance(req.strategies)
    except Exception as e:
        raise HTTPException(500, str(e))
