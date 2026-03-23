"""
src/routes/strategy.py
─────────────────────────────────────────────────────────────────────────────
REST API for the Strategy Layer.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.engines.strategy.definition import StrategyCreate, StrategyConfig, StrategyDefinition
from src.engines.strategy.evaluator import StrategyEvaluator

logger = logging.getLogger("365advisers.routes.strategy")
from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/strategies", tags=["strategies"], dependencies=[Depends(get_current_user)])

_defs = StrategyDefinition()
_evaluator = StrategyEvaluator()


@router.post("/", status_code=201)
def create_strategy(payload: StrategyCreate):
    sid = _defs.create(payload)
    return {"strategy_id": sid, "status": "created"}


@router.get("/")
def list_strategies(active_only: bool = True):
    items = _defs.list_strategies(active_only)
    return {"strategies": [s.model_dump() for s in items], "count": len(items)}


@router.get("/{strategy_id}")
def get_strategy(strategy_id: str):
    s = _defs.get(strategy_id)
    if not s:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return s.model_dump()


@router.put("/{strategy_id}")
def update_strategy(strategy_id: str, config: StrategyConfig):
    ok = _defs.update(strategy_id, config)
    if not ok:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"status": "updated"}


@router.delete("/{strategy_id}")
def deactivate_strategy(strategy_id: str):
    ok = _defs.deactivate(strategy_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"status": "deactivated"}


@router.post("/{strategy_id}/evaluate")
def evaluate_strategy(strategy_id: str, opportunities: list[dict]):
    return _evaluator.evaluate_strategy(strategy_id, opportunities)
