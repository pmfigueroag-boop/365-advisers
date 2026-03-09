"""
src/engines/alpha_macro/models.py
──────────────────────────────────────────────────────────────────────────────
Data contracts for the Alpha Macro Engine.
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class MacroRegime(str, Enum):
    EXPANSION = "expansion"
    SLOWDOWN = "slowdown"
    RECESSION = "recession"
    RECOVERY = "recovery"


class MacroIndicatorReading(BaseModel):
    """Single macro indicator with current value and regime signal."""
    name: str
    value: float | None = None
    previous: float | None = None
    change: float | None = None
    z_score: float | None = None
    signal: str = "neutral"  # bullish / bearish / neutral


class MacroScore(BaseModel):
    """Composite macro environment assessment."""
    regime: MacroRegime = MacroRegime.EXPANSION
    regime_confidence: float = Field(0.0, ge=0, le=1.0)
    regime_probabilities: dict[str, float] = Field(default_factory=dict)
    composite_score: float = Field(50.0, ge=0, le=100)  # 0=deep recession, 100=peak expansion
    indicators: list[MacroIndicatorReading] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AssetAllocationSuggestion(BaseModel):
    """Regime-based asset class tilts."""
    regime: MacroRegime
    equities_tilt: float = 0.0   # -1 to +1
    bonds_tilt: float = 0.0
    commodities_tilt: float = 0.0
    cash_tilt: float = 0.0
    rationale: str = ""


class MacroDashboard(BaseModel):
    """Complete macro intelligence output."""
    score: MacroScore
    allocation: AssetAllocationSuggestion
    key_risks: list[str] = Field(default_factory=list)
    regime_history: list[dict] = Field(default_factory=list)
