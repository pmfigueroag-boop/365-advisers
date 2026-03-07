"""
src/data/external/contracts/filing_event.py
──────────────────────────────────────────────────────────────────────────────
Normalized contracts for SEC EDGAR filing events.

Captures 10-K, 10-Q, 8-K, proxy, and ownership filings.  Provides
material event detection flags and filing urgency classification.

Consumed by:
  - Idea Generation (filing event detector)
  - Alpha Signals (filing category)
  - Decision Engine (CIO Memo context)
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class FilingEvent(BaseModel):
    """Single SEC filing record."""
    filing_type: str                       # 10-K, 10-Q, 8-K, DEF14A, SC13D, SC13G
    filed_date: str
    period_of_report: str | None = None
    accession_number: str = ""
    primary_document_url: str | None = None
    description: str | None = None
    urgency: str = "routine"               # routine / material / critical
    items: list[str] = Field(default_factory=list)  # 8-K item codes, e.g. ["1.01", "2.01"]


class OwnershipFiling(BaseModel):
    """SC 13D/G ownership filing summary."""
    filer_name: str
    filing_type: str                       # SC 13D / SC 13G / SC 13D/A
    filed_date: str
    shares_reported: int | None = None
    pct_of_class: float | None = None
    purpose: str = ""


class ProxyFiling(BaseModel):
    """DEF 14A / DEFA14A proxy filing summary."""
    filing_type: str                       # DEF14A, DEFA14A
    filed_date: str
    meeting_date: str | None = None
    proposals_count: int | None = None
    contested: bool = False


class FilingEventData(BaseModel):
    """
    Complete SEC filing event data for a ticker.

    Consumed by:
      - Idea Generation Engine (filing event detector)
      - Alpha Signals (filing category signals)
      - Decision Engine (CIO Memo context for material events)
    """
    ticker: str
    filings: list[FilingEvent] = Field(default_factory=list)
    has_material_event: bool = False        # any 8-K in last 7 days
    latest_annual_filing: str | None = None   # "10-K" filed date
    latest_quarterly_filing: str | None = None  # "10-Q" filed date

    # Ownership & proxy sub-collections (optional)
    ownership_filings: list[OwnershipFiling] = Field(default_factory=list)
    proxy_filings: list[ProxyFiling] = Field(default_factory=list)

    # Provenance
    source: str = "unknown"
    sources_used: list[str] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @classmethod
    def empty(cls, ticker: str = "") -> FilingEventData:
        """Null-but-valid skeleton — engines skip filing signals."""
        return cls(ticker=ticker, source="null")
