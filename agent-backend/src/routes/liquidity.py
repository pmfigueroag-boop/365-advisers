"""
src/routes/liquidity.py
─────────────────────────────────────────────────────────────────────────────
REST API for Liquidity, Capacity, and Execution Simulation.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.engines.liquidity import LiquidityEstimator, MarketImpactModel, CapacityCalculator
from src.engines.execution import ExecutionSimulator, FillModel

logger = logging.getLogger("365advisers.routes.liquidity")
from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/liquidity", tags=["liquidity"], dependencies=[Depends(get_current_user)])

_estimator = LiquidityEstimator()
_impact = MarketImpactModel()
_capacity = CapacityCalculator()
_exec_sim = ExecutionSimulator()
_fill = FillModel()


# ── Liquidity Profiles ────────────────────────────────────────────────────────

@router.post("/profiles")
def estimate_liquidity(ticker: str, market_data: dict):
    return _estimator.estimate(ticker, market_data)


@router.get("/profiles/{ticker}")
def get_liquidity_profile(ticker: str):
    p = _estimator.get_profile(ticker)
    if not p:
        raise HTTPException(status_code=404, detail="No liquidity profile")
    return p


@router.get("/profiles")
def list_liquidity_profiles():
    return {"profiles": _estimator.get_all_profiles()}


# ── Market Impact ─────────────────────────────────────────────────────────────

@router.post("/impact")
def estimate_market_impact(
    order_shares: int,
    adv: float,
    daily_volatility: float,
    price: float,
    execution_days: float = 1.0,
):
    return _impact.estimate_impact(
        order_shares, adv, daily_volatility, price, execution_days
    )


# ── Capacity ──────────────────────────────────────────────────────────────────

@router.post("/capacity/portfolio")
def compute_portfolio_capacity(positions: list[dict]):
    return _capacity.compute_portfolio_capacity(positions)


@router.get("/capacity/{ticker}")
def compute_ticker_capacity(ticker: str):
    return _capacity.compute_ticker_capacity(ticker)


# ── Execution Simulation ─────────────────────────────────────────────────────

@router.post("/execution/simulate")
def simulate_execution(
    order_value_usd: float,
    price: float,
    adv: float,
    daily_volatility: float = 0.02,
    spread_bps: float | None = None,
):
    return _exec_sim.simulate_execution(
        order_value_usd, price, adv, daily_volatility, spread_bps
    )


@router.post("/execution/portfolio")
def simulate_portfolio_execution(positions: list[dict]):
    return _exec_sim.simulate_portfolio_execution(positions)


@router.post("/execution/fill")
def estimate_fill(order_shares: int, adv: float, urgency: str = "normal"):
    return _fill.estimate_fill(order_shares, adv, urgency)
