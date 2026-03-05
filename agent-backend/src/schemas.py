"""
src/schemas.py
─────────────────────────────────────────────────────────────────────────────
Pydantic request/response models for API validation.
Fixes audit finding #9 — typed endpoints instead of raw Request.json().
"""

from pydantic import BaseModel, Field
from typing import Optional


# ─── Portfolio Build ──────────────────────────────────────────────────────────

class PositionSizingInput(BaseModel):
    suggested_allocation: float = Field(ge=0, le=100)
    risk_level: str = "NORMAL"
    volatility_atr: Optional[float] = None


class PortfolioPositionInput(BaseModel):
    ticker: str
    sector: str = "Unknown"
    opportunity_score: float = 0.0
    dimensions: dict = {}
    position_sizing: PositionSizingInput = PositionSizingInput(suggested_allocation=0)
    volatility_atr: Optional[float] = None


class BuildPortfolioRequest(BaseModel):
    positions: list[PortfolioPositionInput] = Field(min_length=1)


# ─── Portfolio Save ───────────────────────────────────────────────────────────

class PortfolioPositionSave(BaseModel):
    ticker: str
    target_weight: float
    role: str = "SATELLITE"
    sector: str = "Unknown"
    volatility_atr: Optional[float] = None


class SavePortfolioRequest(BaseModel):
    name: str = "Untitled Portfolio"
    strategy: str = "Custom"
    risk_level: str = "NORMAL"
    total_allocation: float = 0.0
    positions: list[PortfolioPositionSave] = []


# ─── Analysis ─────────────────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    ticker: str
