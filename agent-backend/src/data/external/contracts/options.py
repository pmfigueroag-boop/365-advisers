"""
src/data/external/contracts/options.py
──────────────────────────────────────────────────────────────────────────────
Normalized contracts for options market intelligence.

Captures implied volatility surface, skew, unusual activity, and gamma
context for the Crowding Engine, Alpha Signals, and Technical Analysis.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class OptionsSnapshot(BaseModel):
    """Point-in-time options intelligence for a ticker."""
    ticker: str
    implied_vol_30d: float | None = None
    implied_vol_60d: float | None = None
    iv_rank_1y: float | None = None            # 0–100 percentile
    iv_percentile_1y: float | None = None
    put_call_ratio: float | None = None
    skew_25d: float | None = None              # 25-delta put-call skew
    term_structure_slope: float | None = None
    gamma_exposure_net: float | None = None     # aggregate dealer gamma

    @classmethod
    def empty(cls, ticker: str = "") -> OptionsSnapshot:
        return cls(ticker=ticker)


class UnusualActivity(BaseModel):
    """Single unusual options activity observation."""
    ticker: str
    timestamp: datetime
    option_type: str              # CALL / PUT
    strike: float
    expiry: str
    volume: int
    open_interest: int
    vol_oi_ratio: float
    premium_usd: float
    sentiment: str = "neutral"    # bullish / bearish / neutral


class OptionsIntelligence(BaseModel):
    """
    Complete options intelligence output.

    Consumed by:
      - CrowdingEngine (implied_vol_30d → VC indicator)
      - Alpha Signals (volatility category)
      - Technical Engine (vol context)
    """
    ticker: str
    snapshot: OptionsSnapshot | None = None
    unusual_activity: list[UnusualActivity] = Field(default_factory=list)
    source: str = "unknown"
    fetched_at: datetime | None = None

    @classmethod
    def empty(cls, ticker: str = "") -> OptionsIntelligence:
        return cls(ticker=ticker, source="null")
