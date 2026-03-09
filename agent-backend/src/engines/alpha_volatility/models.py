"""
src/engines/alpha_volatility/models.py
──────────────────────────────────────────────────────────────────────────────
Data contracts for the Alpha Volatility Engine.
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class VolRegime(str, Enum):
    LOW = "low"            # VIX < 15
    NORMAL = "normal"      # VIX 15–20
    ELEVATED = "elevated"  # VIX 20–30
    EXTREME = "extreme"    # VIX > 30


class VolScore(BaseModel):
    """Composite volatility risk assessment."""
    composite_risk: float = Field(50.0, ge=0, le=100)  # 0=ultra calm, 100=crisis
    regime: VolRegime = VolRegime.NORMAL
    vix_level: float | None = None
    vix_percentile: float | None = None    # Rank vs 1yr history
    iv_rank: float | None = None           # 0–100
    iv_rv_spread: float | None = None      # IV minus RV
    term_structure: str = "normal"         # contango / flat / backwardation
    skew_z: float | None = None            # Put-call skew z-score
    signals: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VolSignal(BaseModel):
    """Actionable volatility signal."""
    signal_type: str       # regime_shift, iv_spike, skew_warning, uoa
    ticker: str = "^VIX"
    description: str = ""
    severity: str = "moderate"
    actionable: bool = True


class VolDashboard(BaseModel):
    """Complete volatility intelligence output."""
    score: VolScore
    signals: list[VolSignal] = Field(default_factory=list)
    risk_indicators: dict[str, float] = Field(default_factory=dict)
    regime_history: list[dict] = Field(default_factory=list)
