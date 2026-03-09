"""
src/engines/options_pricing/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Options Pricing Engine.
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class OptionType(str, Enum):
    CALL = "call"
    PUT = "put"

class ExerciseStyle(str, Enum):
    EUROPEAN = "european"
    AMERICAN = "american"

class Moneyness(str, Enum):
    ITM = "itm"
    ATM = "atm"
    OTM = "otm"


class OptionContract(BaseModel):
    """Input parameters for option pricing."""
    underlying_price: float = Field(gt=0, description="Current underlying price (S)")
    strike: float = Field(gt=0, description="Strike price (K)")
    time_to_expiry: float = Field(gt=0, description="Time to expiry in years (T)")
    volatility: float = Field(gt=0, le=5.0, description="Annualised volatility (σ)")
    risk_free_rate: float = Field(0.05, ge=0, le=0.50, description="Risk-free rate (r)")
    dividend_yield: float = Field(0.0, ge=0, le=0.20, description="Continuous dividend yield (q)")
    option_type: OptionType = OptionType.CALL
    exercise_style: ExerciseStyle = ExerciseStyle.EUROPEAN


class Greeks(BaseModel):
    """Option sensitivity measures."""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0     # per day
    vega: float = 0.0      # per 1% vol move
    rho: float = 0.0       # per 1% rate move


class PricingResult(BaseModel):
    """Complete option pricing output."""
    theoretical_price: float = 0.0
    greeks: Greeks = Field(default_factory=Greeks)
    implied_vol: float | None = None
    intrinsic_value: float = 0.0
    time_value: float = 0.0
    moneyness: str = Moneyness.ATM.value
    contract: OptionContract | None = None


class VolSurfacePoint(BaseModel):
    """Single point on a volatility surface."""
    strike: float
    time_to_expiry: float
    implied_vol: float
    moneyness: float = 0.0  # strike / underlying


class PutCallParityResult(BaseModel):
    """Put-call parity verification."""
    call_price: float
    put_price: float
    synthetic_call: float  # put + S*e^{-qT} - K*e^{-rT}
    synthetic_put: float   # call - S*e^{-qT} + K*e^{-rT}
    parity_violation: float  # should be ~0
    parity_holds: bool = True
