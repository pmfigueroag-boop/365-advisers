"""
src/engines/crowding/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Signal Crowding Detection Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ─── Enumerations ───────────────────────────────────────────────────────────

class CrowdingSeverity(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


# ─── Configuration ──────────────────────────────────────────────────────────

class CrowdingConfig(BaseModel):
    """Tunable parameters for crowding detection."""
    w_volume: float = Field(0.35, description="Weight for Volume Anomaly")
    w_etf_flow: float = Field(0.25, description="Weight for ETF Flow Concentration")
    w_institutional: float = Field(0.25, description="Weight for Institutional Herding")
    w_volatility: float = Field(0.15, description="Weight for Volatility Compression")
    max_penalty: float = Field(0.40, description="Max CASE penalty at CRS=1.0")
    volume_short_window: int = Field(20, description="Short volume MA window (days)")
    volume_long_window: int = Field(60, description="Long volume MA window (days)")
    flow_lookback: int = Field(60, description="ETF flow lookback (days)")


# ─── Indicator Breakdown ────────────────────────────────────────────────────

class CrowdingIndicators(BaseModel):
    """Individual crowding indicator scores, each in [0, 1]."""
    volume_anomaly: float = Field(0.0, ge=0.0, le=1.0, description="VAS")
    etf_flow_conc: float = Field(0.0, ge=0.0, le=1.0, description="EFC")
    inst_herding: float = Field(0.0, ge=0.0, le=1.0, description="IOH")
    vol_compression: float = Field(0.0, ge=0.0, le=1.0, description="VC")


# ─── Result ─────────────────────────────────────────────────────────────────

class CrowdingResult(BaseModel):
    """Complete crowding assessment for a single ticker."""
    ticker: str
    crowding_risk_score: float = Field(0.0, ge=0.0, le=1.0)
    severity: CrowdingSeverity = CrowdingSeverity.NONE
    indicators: CrowdingIndicators = Field(default_factory=CrowdingIndicators)
    penalty_factor: float = Field(1.0, ge=0.0, le=1.0)
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    data_available: dict[str, bool] = Field(
        default_factory=lambda: {
            "volume": False,
            "etf_flow": False,
            "institutional": False,
            "volatility": False,
        },
        description="Which data sources were available for computation",
    )
