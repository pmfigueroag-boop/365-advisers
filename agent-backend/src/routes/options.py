"""
src/routes/options.py — API for Options Pricing Engine.
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException
from src.engines.options_pricing.models import OptionContract, OptionType
from src.engines.options_pricing.engine import OptionsPricingEngine
from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.routes.options")
from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/alpha/options", tags=["Alpha: Options"], dependencies=[Depends(get_current_user)])

class IVRequest(BaseModel):
    market_price: float = Field(gt=0)
    underlying_price: float = Field(gt=0)
    strike: float = Field(gt=0)
    time_to_expiry: float = Field(gt=0)
    option_type: OptionType = OptionType.CALL
    risk_free_rate: float = 0.05

class ChainRequest(BaseModel):
    underlying_price: float = Field(gt=0)
    strikes: list[float]
    time_to_expiry: float = Field(gt=0)
    volatility: float = Field(gt=0)
    risk_free_rate: float = 0.05

@router.post("/price")
async def price_option(contract: OptionContract):
    try:
        return OptionsPricingEngine.price_option(contract).model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/greeks")
async def compute_greeks(contract: OptionContract):
    try:
        result = OptionsPricingEngine.price_option(contract)
        return {"greeks": result.greeks.model_dump(), "price": result.theoretical_price}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/implied-vol")
async def implied_vol(req: IVRequest):
    try:
        iv = OptionsPricingEngine.compute_iv(
            req.market_price, req.underlying_price, req.strike,
            req.time_to_expiry, req.option_type, req.risk_free_rate,
        )
        if iv is None:
            raise HTTPException(422, "IV solver did not converge")
        return {"implied_vol": iv}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/chain")
async def option_chain(req: ChainRequest):
    try:
        chain = OptionsPricingEngine.option_chain(
            req.underlying_price, req.strikes, req.time_to_expiry,
            req.volatility, req.risk_free_rate,
        )
        return {"chain": chain, "total": len(chain)}
    except Exception as e:
        raise HTTPException(500, str(e))
