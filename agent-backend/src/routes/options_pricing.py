"""
src/routes/options_pricing.py
─────────────────────────────────────────────────────────────────────────────
REST Endpoint for Options Pricing (Black-Scholes & Greeks).
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import datetime
import yfinance as yf

from src.engines.options.black_scholes import BlackScholesEngine
import logging

logger = logging.getLogger("365advisers.routes.options")
router = APIRouter(tags=["Options Pricing"])

class OptionPricingRequest(BaseModel):
    underlying_price: float
    strike_price: float
    time_to_expiry_years: float
    risk_free_rate: float = 0.05
    implied_volatility: float = 0.20
    option_type: str = "call" # "call" or "put"

class OptionChainRequest(BaseModel):
    ticker: str
    risk_free_rate: float = 0.05
    target_date: Optional[str] = None # YYYY-MM-DD
    
@router.post("/api/options/pricing")
def calculate_option_price(req: OptionPricingRequest):
    """
    Calculates Theoretical Price and Greeks (Delta, Gamma, Theta, Vega, Rho)
    for a single European Call or Put option using Black-Scholes.
    """
    if req.time_to_expiry_years < 0:
        raise HTTPException(status_code=400, detail="Time to expiry cannot be negative.")
    if req.implied_volatility <= 0:
        raise HTTPException(status_code=400, detail="Volatility must be positive.")
        
    try:
        res = BlackScholesEngine.analyze_option(
            S=req.underlying_price,
            K=req.strike_price,
            T=req.time_to_expiry_years,
            r=req.risk_free_rate,
            sigma=req.implied_volatility,
            option_type=req.option_type
        )
        return res
    except Exception as e:
        logger.error(f"Option pricing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
