"""
src/routes/shadow.py
─────────────────────────────────────────────────────────────────────────────
REST API for the Shadow Portfolio Framework.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from src.engines.shadow import (
    ShadowPerformanceCalc,
    ShadowPortfolioManager,
    ShadowRebalancer,
)
from src.engines.shadow.models import ShadowPortfolioCreate, ShadowPortfolioType

logger = logging.getLogger("365advisers.routes.shadow")
router = APIRouter(prefix="/shadow", tags=["shadow"])

_manager = ShadowPortfolioManager()
_rebalancer = ShadowRebalancer()
_performance = ShadowPerformanceCalc()


@router.post("/portfolios", status_code=201)
def create_shadow_portfolio(payload: ShadowPortfolioCreate):
    pid = _manager.create(payload)
    return {"portfolio_id": pid, "status": "created"}


@router.get("/portfolios")
def list_shadow_portfolios(
    portfolio_type: ShadowPortfolioType | None = None,
    active_only: bool = True,
):
    items = _manager.list_portfolios(portfolio_type, active_only)
    return {"portfolios": [p.model_dump() for p in items if p], "count": len(items)}


@router.get("/portfolios/{portfolio_id}")
def get_shadow_portfolio(portfolio_id: str):
    p = _manager.get(portfolio_id)
    if not p:
        raise HTTPException(status_code=404, detail="Shadow portfolio not found")
    return p.model_dump()


@router.delete("/portfolios/{portfolio_id}")
def deactivate_shadow_portfolio(portfolio_id: str):
    ok = _manager.deactivate(portfolio_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Shadow portfolio not found")
    return {"status": "deactivated"}


@router.post("/portfolios/{portfolio_id}/positions")
def add_position(portfolio_id: str, ticker: str, weight: float, entry_price: float):
    pos_id = _manager.add_position(portfolio_id, ticker, weight, entry_price)
    return {"position_id": pos_id}


@router.delete("/portfolios/{portfolio_id}/positions/{ticker}")
def close_position(portfolio_id: str, ticker: str, exit_price: float):
    ok = _manager.close_position(portfolio_id, ticker, exit_price)
    if not ok:
        raise HTTPException(status_code=404, detail="Active position not found")
    return {"status": "closed"}


@router.post("/portfolios/{portfolio_id}/rebalance")
def rebalance_portfolio(portfolio_id: str, prices: dict[str, float]):
    changes = _rebalancer.rebalance_research_portfolio(portfolio_id, prices)
    return changes


@router.get("/portfolios/{portfolio_id}/performance")
def get_performance(portfolio_id: str):
    return _performance.compute_performance(portfolio_id)


@router.get("/portfolios/{portfolio_id}/nav")
def get_nav_series(portfolio_id: str, limit: int = Query(default=252, le=1000)):
    series = _performance.get_nav_series(portfolio_id, limit)
    return {"portfolio_id": portfolio_id, "series": series, "count": len(series)}


@router.post("/compare")
def compare_portfolios(portfolio_ids: list[str]):
    return _performance.compare_portfolios(portfolio_ids)
