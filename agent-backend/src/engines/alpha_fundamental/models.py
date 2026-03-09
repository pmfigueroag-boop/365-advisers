"""
src/engines/alpha_fundamental/models.py
──────────────────────────────────────────────────────────────────────────────
Data contracts for the Alpha Fundamental Engine.
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class FundamentalGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class GrowthScore(BaseModel):
    """Revenue & earnings growth assessment."""
    score: float = Field(0.0, ge=0, le=100)
    revenue_growth_yoy: float | None = None
    earnings_growth_yoy: float | None = None
    fcf_growth_yoy: float | None = None
    revenue_acceleration: bool = False
    signals: list[str] = Field(default_factory=list)


class ProfitabilityScore(BaseModel):
    """Margin and return-on-capital assessment."""
    score: float = Field(0.0, ge=0, le=100)
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    roic: float | None = None
    roe: float | None = None
    margin_expanding: bool = False
    signals: list[str] = Field(default_factory=list)


class BalanceSheetScore(BaseModel):
    """Financial strength and leverage assessment."""
    score: float = Field(0.0, ge=0, le=100)
    current_ratio: float | None = None
    debt_to_equity: float | None = None
    interest_coverage: float | None = None
    net_debt_to_ebitda: float | None = None
    cash_rich: bool = False
    signals: list[str] = Field(default_factory=list)


class ValuationScore(BaseModel):
    """Relative valuation assessment."""
    score: float = Field(0.0, ge=0, le=100)
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    ev_to_ebitda: float | None = None
    price_to_fcf: float | None = None
    peg_ratio: float | None = None
    undervalued: bool = False
    signals: list[str] = Field(default_factory=list)


class FundamentalScore(BaseModel):
    """Complete fundamental assessment for a ticker."""
    ticker: str
    composite_score: float = Field(0.0, ge=0, le=100)
    grade: FundamentalGrade = FundamentalGrade.C
    growth: GrowthScore = Field(default_factory=GrowthScore)
    profitability: ProfitabilityScore = Field(default_factory=ProfitabilityScore)
    balance_sheet: BalanceSheetScore = Field(default_factory=BalanceSheetScore)
    valuation: ValuationScore = Field(default_factory=ValuationScore)
    top_signals: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FundamentalRanking(BaseModel):
    """Ranked list of tickers by fundamental score."""
    rankings: list[FundamentalScore] = Field(default_factory=list)
    top_opportunities: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_analyzed: int = 0
