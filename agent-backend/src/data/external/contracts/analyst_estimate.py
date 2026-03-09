"""
src/data/external/contracts/analyst_estimate.py
──────────────────────────────────────────────────────────────────────────────
Canonical contracts for analyst estimates, recommendations, and targets.

Consumed by:
  - Fundamental Engine (consensus expectations)
  - Alpha Signals (estimate revision signals)
  - Valuation Engine (forward estimates)
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class EarningsEstimate(BaseModel):
    """Consensus EPS estimate for a period."""
    period: str = ""                       # "2025-Q4", "2026-FY"
    consensus_eps: float | None = None
    high_eps: float | None = None
    low_eps: float | None = None
    num_analysts: int | None = None
    actual_eps: float | None = None        # filled after earnings
    surprise_pct: float | None = None      # (actual - consensus) / consensus


class RevenueEstimate(BaseModel):
    """Consensus revenue estimate for a period."""
    period: str = ""
    consensus_revenue: float | None = None
    high_revenue: float | None = None
    low_revenue: float | None = None
    num_analysts: int | None = None
    actual_revenue: float | None = None
    surprise_pct: float | None = None


class PriceTarget(BaseModel):
    """Analyst price target consensus."""
    consensus_target: float | None = None
    high_target: float | None = None
    low_target: float | None = None
    median_target: float | None = None
    num_analysts: int | None = None
    current_price: float | None = None
    upside_pct: float | None = None


class AnalystEstimateData(BaseModel):
    """
    Complete analyst estimates for a ticker.

    Covers EPS, revenue estimates, price targets, and recommendations.
    """
    ticker: str

    # Estimates
    earnings_estimates: list[EarningsEstimate] = Field(default_factory=list)
    revenue_estimates: list[RevenueEstimate] = Field(default_factory=list)
    price_target: PriceTarget | None = None

    # Recommendation
    recommendation: str = ""               # buy, hold, sell, strong_buy, strong_sell
    recommendation_score: float | None = None  # 1.0 (strong buy) → 5.0 (strong sell)
    num_analysts: int | None = None

    # Recent revisions
    eps_revisions_up_30d: int = 0
    eps_revisions_down_30d: int = 0
    revision_trend: str = "flat"           # improving, deteriorating, flat

    # Provenance
    source: str = "unknown"
    sources_used: list[str] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @classmethod
    def empty(cls, ticker: str = "") -> AnalystEstimateData:
        return cls(ticker=ticker, source="null")
