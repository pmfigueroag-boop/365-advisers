"""
src/data/external/contracts/financial_statement.py
──────────────────────────────────────────────────────────────────────────────
Canonical contracts for financial statements (income, balance, cash flow).

Consumed by:
  - Fundamental Engine (financial health analysis)
  - Alpha Signals (earnings quality, growth signals)
  - Valuation Engine (DCF inputs)
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class StatementLineItem(BaseModel):
    """Single line item from a financial statement."""
    label: str
    value: float | None = None
    formatted: str = ""


class IncomeStatement(BaseModel):
    """Annual or quarterly income statement snapshot."""
    period: str = ""               # "2025-Q4" or "2025-FY"
    fiscal_date: str = ""          # "2025-12-31"
    currency: str = "USD"

    revenue: float | None = None
    cost_of_revenue: float | None = None
    gross_profit: float | None = None
    operating_expenses: float | None = None
    operating_income: float | None = None
    ebitda: float | None = None
    net_income: float | None = None
    eps: float | None = None
    eps_diluted: float | None = None
    shares_outstanding: float | None = None
    shares_diluted: float | None = None

    # Growth (YoY)
    revenue_growth: float | None = None
    net_income_growth: float | None = None
    eps_growth: float | None = None


class BalanceSheet(BaseModel):
    """Annual or quarterly balance sheet snapshot."""
    period: str = ""
    fiscal_date: str = ""
    currency: str = "USD"

    total_assets: float | None = None
    total_liabilities: float | None = None
    total_equity: float | None = None
    cash_and_equivalents: float | None = None
    short_term_investments: float | None = None
    total_debt: float | None = None
    net_debt: float | None = None
    total_current_assets: float | None = None
    total_current_liabilities: float | None = None
    inventory: float | None = None
    goodwill: float | None = None


class CashFlowStatement(BaseModel):
    """Annual or quarterly cash flow statement snapshot."""
    period: str = ""
    fiscal_date: str = ""
    currency: str = "USD"

    operating_cash_flow: float | None = None
    capital_expenditure: float | None = None
    free_cash_flow: float | None = None
    investing_cash_flow: float | None = None
    financing_cash_flow: float | None = None
    dividends_paid: float | None = None
    share_repurchases: float | None = None
    net_change_in_cash: float | None = None


class FinancialStatementData(BaseModel):
    """
    Complete financial statements for a ticker.

    Contains lists of income statements, balance sheets, and cash flow
    statements sorted by most recent first.
    """
    ticker: str
    income_statements: list[IncomeStatement] = Field(default_factory=list)
    balance_sheets: list[BalanceSheet] = Field(default_factory=list)
    cash_flows: list[CashFlowStatement] = Field(default_factory=list)

    # Provenance
    source: str = "unknown"
    sources_used: list[str] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @classmethod
    def empty(cls, ticker: str = "") -> FinancialStatementData:
        return cls(ticker=ticker, source="null")
