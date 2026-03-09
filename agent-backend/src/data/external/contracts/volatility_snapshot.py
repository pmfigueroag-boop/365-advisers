"""
src/data/external/contracts/volatility_snapshot.py
──────────────────────────────────────────────────────────────────────────────
Canonical contracts for volatility intelligence.

Captures VIX, term structure, historical vs implied vol, skew, and
regime-level volatility context.

Consumed by:
  - Options Pricing Engine
  - Risk Engine (VaR/CVaR context)
  - Alpha Signals (volatility category)
  - Regime Weights Engine
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class VIXSnapshot(BaseModel):
    """Point-in-time VIX and related vol index readings."""
    vix_current: float | None = None
    vix_open: float | None = None
    vix_high: float | None = None
    vix_low: float | None = None
    vix_close: float | None = None
    vix_change: float | None = None
    vix_change_pct: float | None = None

    # Related indices
    vix9d: float | None = None             # 9-day VIX
    vix3m: float | None = None             # 3-month VIX
    vix6m: float | None = None             # 6-month VIX
    vix1y: float | None = None             # 1-year VIX

    # Term structure
    term_structure_slope: float | None = None  # VIX9D vs VIX — contango/backwardation
    term_structure_regime: str = "normal"       # contango / backwardation / flat


class HistoricalVolPoint(BaseModel):
    """Single observation of historical volatility."""
    date: str
    hv_10d: float | None = None
    hv_20d: float | None = None
    hv_30d: float | None = None
    hv_60d: float | None = None
    hv_90d: float | None = None


class VolatilitySnapshot(BaseModel):
    """
    Complete volatility intelligence snapshot.

    Combines VIX market data, historical volatility, implied/realized
    spread, and regime classification.
    """
    ticker: str = "^VIX"                   # ^VIX for market, or ticker-specific

    vix: VIXSnapshot | None = None
    historical_vol: list[HistoricalVolPoint] = Field(default_factory=list)

    # Current ticker-specific vol (if not VIX)
    iv_30d: float | None = None
    iv_60d: float | None = None
    rv_30d: float | None = None            # realized vol
    iv_rv_spread: float | None = None      # implied - realized
    iv_rank_1y: float | None = None        # 0–100 percentile
    iv_percentile_1y: float | None = None

    # Skew
    skew_25d: float | None = None          # 25-delta put-call skew
    skew_10d: float | None = None

    # Regime
    vol_regime: str = "normal"             # low / normal / elevated / extreme

    # Provenance
    source: str = "unknown"
    sources_used: list[str] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @classmethod
    def empty(cls, ticker: str = "^VIX") -> VolatilitySnapshot:
        return cls(ticker=ticker, source="null")
