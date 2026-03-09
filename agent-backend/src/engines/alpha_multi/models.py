"""
src/engines/alpha_multi/models.py
──────────────────────────────────────────────────────────────────────────────
Data contracts for the Multi-Strategy Alpha Engine.
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class AlphaConviction(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class AssetAlphaProfile(BaseModel):
    """Combined alpha profile for a single asset."""
    ticker: str
    composite_alpha: float = Field(0.0, ge=0, le=100)
    conviction: AlphaConviction = AlphaConviction.NEUTRAL

    # Sub-engine scores (0–100 each, normalized)
    fundamental_score: float = 0.0
    macro_score: float = 0.0
    sentiment_score: float = 0.0     # normalized to 0–100
    volatility_risk: float = 0.0     # inverted: 100=low risk
    event_score: float = 0.0         # normalized to 0–100

    # Convergence
    engines_bullish: int = 0
    engines_bearish: int = 0
    convergence_bonus: float = 0.0

    top_signals: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HeatmapCell(BaseModel):
    """Single cell in the opportunity heatmap."""
    ticker: str
    fundamental: float = 0.0
    macro: float = 0.0
    sentiment: float = 0.0
    volatility: float = 0.0
    event: float = 0.0
    composite: float = 0.0


class MultiAlphaResult(BaseModel):
    """Complete multi-strategy alpha output."""
    rankings: list[AssetAlphaProfile] = Field(default_factory=list)
    heatmap: list[HeatmapCell] = Field(default_factory=list)
    top_opportunities: list[str] = Field(default_factory=list)
    top_risks: list[str] = Field(default_factory=list)
    total_analyzed: int = 0
    market_context: str = ""
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
