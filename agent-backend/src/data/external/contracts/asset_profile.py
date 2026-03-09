"""
src/data/external/contracts/asset_profile.py
──────────────────────────────────────────────────────────────────────────────
Canonical contract for company / asset profile data.

Consumed by:
  - Fundamental Engine (company context)
  - Idea Generation (sector/industry filtering)
  - Decision Engine (CIO Memo company overview)
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class AssetProfile(BaseModel):
    """Unified company / asset profile across providers."""
    ticker: str
    name: str = ""
    exchange: str = ""
    currency: str = "USD"
    country: str = ""
    sector: str = ""
    industry: str = ""
    description: str = ""
    website: str = ""
    logo_url: str | None = None

    # Size & structure
    market_cap: float | None = None
    enterprise_value: float | None = None
    shares_outstanding: float | None = None
    float_shares: float | None = None
    employees: int | None = None

    # Classification
    asset_type: str = "equity"          # equity, etf, adr, crypto, forex
    is_actively_traded: bool = True
    ipo_date: str | None = None
    fiscal_year_end: str | None = None  # e.g. "December"

    # Provenance
    source: str = "unknown"
    sources_used: list[str] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @classmethod
    def empty(cls, ticker: str = "") -> AssetProfile:
        return cls(ticker=ticker, source="null")
