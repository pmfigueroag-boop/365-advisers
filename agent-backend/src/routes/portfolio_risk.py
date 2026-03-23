"""
src/routes/portfolio_risk.py
─────────────────────────────────────────────────────────────────────────────
REST Endpoint for Portfolio Risk Analysis using Monte Carlo VaR & CVaR.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict

from src.engines.risk.risk_engine import StochasticRiskEngine
import logging

logger = logging.getLogger("365advisers.routes.risk")
from src.auth.dependencies import get_current_user

router = APIRouter(tags=["Portfolio Risk"], dependencies=[Depends(get_current_user)])

class RiskRequest(BaseModel):
    portfolio: Dict[str, float]  # e.g., {"AAPL": 0.5, "MSFT": 0.5}
    horizon_days: int = 21
    confidence_level: float = 0.95
    mc_simulations: int = 10000

@router.post("/api/portfolio/risk")
async def calculate_portfolio_risk(req: RiskRequest):
    """
    Calculates Parametric, Historical, and Monte Carlo VaR/CVaR 
    for a weighted portfolio of assets over a given horizon.
    """
    if not req.portfolio:
        raise HTTPException(status_code=400, detail="Portfolio cannot be empty.")
        
    weights_sum = sum(req.portfolio.values())
    if abs(weights_sum - 1.0) > 0.01:
        # Normalize weights if they don't sum to exactly 1.0
        req.portfolio = {k: v / weights_sum for k, v in req.portfolio.items()}
        
    try:
        from collections import defaultdict
        
        # We use a thread since yfinance blocks while downloading
        import asyncio
        engine = StochasticRiskEngine()
        
        result = await asyncio.to_thread(
            engine.calculate_risk_metrics,
            portfolio=req.portfolio,
            horizon_days=req.horizon_days,
            confidence_level=req.confidence_level,
            mc_simulations=req.mc_simulations
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
            
        return result
        
    except Exception as e:
        logger.error(f"Risk calculation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
