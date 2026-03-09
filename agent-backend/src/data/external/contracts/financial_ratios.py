"""
src/data/external/contracts/financial_ratios.py
──────────────────────────────────────────────────────────────────────────────
Canonical contracts for financial ratios and valuation metrics.

Consumed by:
  - Fundamental Engine (ratio-based quality scoring)
  - Alpha Signals (value, quality, growth factors)
  - Valuation Engine (relative valuation)
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class FinancialRatios(BaseModel):
    """
    Unified financial ratios snapshot for a ticker.

    Covers valuation, profitability, liquidity, leverage, efficiency, and growth.
    """
    ticker: str
    period: str = "TTM"             # TTM, 2025-FY, 2025-Q4

    # Valuation
    pe_ratio: float | None = None
    forward_pe: float | None = None
    pb_ratio: float | None = None
    ps_ratio: float | None = None
    ev_to_ebitda: float | None = None
    ev_to_revenue: float | None = None
    peg_ratio: float | None = None
    price_to_fcf: float | None = None

    # Profitability
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    roe: float | None = None               # Return on Equity
    roa: float | None = None               # Return on Assets
    roic: float | None = None              # Return on Invested Capital
    roce: float | None = None              # Return on Capital Employed

    # Liquidity
    current_ratio: float | None = None
    quick_ratio: float | None = None
    cash_ratio: float | None = None

    # Leverage
    debt_to_equity: float | None = None
    debt_to_assets: float | None = None
    interest_coverage: float | None = None
    net_debt_to_ebitda: float | None = None

    # Efficiency
    asset_turnover: float | None = None
    inventory_turnover: float | None = None
    receivables_turnover: float | None = None

    # Growth (YoY)
    revenue_growth_yoy: float | None = None
    earnings_growth_yoy: float | None = None
    fcf_growth_yoy: float | None = None
    dividend_growth_yoy: float | None = None

    # Dividend
    dividend_yield: float | None = None
    payout_ratio: float | None = None

    # Provenance
    source: str = "unknown"
    sources_used: list[str] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @classmethod
    def empty(cls, ticker: str = "") -> FinancialRatios:
        return cls(ticker=ticker, source="null")
