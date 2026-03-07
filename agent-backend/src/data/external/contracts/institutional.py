"""
src/data/external/contracts/institutional.py
──────────────────────────────────────────────────────────────────────────────
Normalized contracts for institutional flow data.

Captures insider transactions, 13F ownership changes, and derived
accumulation signals for the Crowding Engine and Scoring Engine.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from datetime import datetime


class InsiderTransaction(BaseModel):
    """Single insider buy/sell/exercise event."""
    ticker: str
    insider_name: str
    title: str
    transaction_type: str       # BUY / SELL / EXERCISE
    shares: int
    price: float
    date: str
    total_value: float


class OwnershipChange(BaseModel):
    """Quarterly 13F ownership change for a single institution."""
    ticker: str
    institution_name: str
    shares_held: int
    shares_change: int
    pct_portfolio: float | None = None
    filing_date: str


class CongressionalTrade(BaseModel):
    """Single congressional trading disclosure (Quiver Quantitative)."""
    congress_member: str
    ticker: str
    tx_type: str                    # BUY / SELL
    amount_range: str               # "$15,001 - $50,000"
    date: str
    party: str                      # R / D / I
    chamber: str = ""               # House / Senate


class InstitutionalFlowData(BaseModel):
    """
    Institutional flow snapshot for a ticker.

    Consumed by:
      - CrowdingEngine (inst_ownership_change → IOH indicator)
      - ScoringEngine (institutional_flow factor)
      - Alpha Signals (flow category)
    """
    ticker: str
    insider_transactions_90d: list[InsiderTransaction] = Field(default_factory=list)
    ownership_changes_q: list[OwnershipChange] = Field(default_factory=list)
    net_insider_buy_ratio: float | None = None
    inst_ownership_pct: float | None = None
    inst_ownership_change_qoq: float | None = None

    # Quiver Quantitative enrichment (optional)
    congressional_trades: list[CongressionalTrade] = Field(default_factory=list)
    lobbying_spend_total: float | None = None
    gov_contract_value: float | None = None
    quiver_smart_money_score: float | None = None   # 0–100 composite

    # Provenance
    source: str = "unknown"
    sources_used: list[str] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @classmethod
    def empty(cls, ticker: str = "") -> InstitutionalFlowData:
        return cls(ticker=ticker, source="null")
