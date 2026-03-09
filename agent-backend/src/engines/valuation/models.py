"""
src/engines/valuation/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Intrinsic Valuation Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ── Enumerations ─────────────────────────────────────────────────────────────

class ValuationVerdict(str, Enum):
    """Fair value assessment."""
    UNDERVALUED = "undervalued"
    FAIR_VALUE = "fair_value"
    OVERVALUED = "overvalued"


# ── DCF Models ───────────────────────────────────────────────────────────────

class DCFInput(BaseModel):
    """Inputs for a Discounted Cash Flow valuation."""
    ticker: str = ""
    current_fcf: float = Field(description="Latest annual free cash flow ($M)")
    growth_rate_stage1: float = Field(
        0.15, ge=-0.50, le=1.0,
        description="High-growth rate for Stage 1 (e.g., 0.15 = 15%)",
    )
    growth_rate_stage2: float = Field(
        0.08, ge=-0.20, le=0.50,
        description="Fade-to-terminal rate for Stage 2",
    )
    terminal_growth_rate: float = Field(
        0.025, ge=0.0, le=0.05,
        description="Perpetuity growth rate (should be ≤ GDP growth)",
    )
    wacc: float = Field(
        0.10, gt=0.01, le=0.30,
        description="Weighted average cost of capital",
    )
    stage1_years: int = Field(5, ge=1, le=10)
    stage2_years: int = Field(3, ge=0, le=10)
    shares_outstanding: float = Field(gt=0, description="Shares outstanding (millions)")
    net_debt: float = Field(0.0, description="Net debt (cash - debt) in $M; positive = debt")


class CashFlowProjection(BaseModel):
    """Single year cash flow projection."""
    year: int
    stage: str  # "stage1", "stage2", "terminal"
    growth_rate: float
    fcf: float
    discount_factor: float
    present_value: float


class SensitivityCell(BaseModel):
    """Cell in a DCF sensitivity table."""
    wacc: float
    terminal_growth: float
    fair_value: float


class DCFResult(BaseModel):
    """Complete DCF valuation output."""
    ticker: str = ""
    projections: list[CashFlowProjection] = Field(default_factory=list)
    sum_pv_fcf: float = Field(0.0, description="Sum of PV of projected FCFs")
    terminal_value: float = Field(0.0, description="Terminal value (perpetuity)")
    pv_terminal_value: float = Field(0.0, description="PV of terminal value")
    enterprise_value: float = Field(0.0, description="EV = sum_pv + pv_tv")
    equity_value: float = Field(0.0, description="EV - net_debt")
    fair_value_per_share: float = Field(0.0, description="Equity / shares")
    irr: float | None = Field(None, description="Implied IRR if available")
    sensitivity: list[SensitivityCell] = Field(default_factory=list)
    inputs_used: DCFInput | None = None


# ── Comparable Models ────────────────────────────────────────────────────────

class PeerMultiple(BaseModel):
    """A single peer's valuation multiple."""
    ticker: str
    pe_ratio: float | None = None
    ev_ebitda: float | None = None
    p_fcf: float | None = None
    pb_ratio: float | None = None


class ComparableInput(BaseModel):
    """Inputs for comparable company analysis."""
    target_ticker: str
    target_eps: float = Field(0.0, description="EPS for PE-based valuation")
    target_ebitda: float = Field(0.0, description="EBITDA for EV/EBITDA")
    target_fcf_per_share: float = Field(0.0, description="FCF/share for P/FCF")
    target_book_value: float = Field(0.0, description="Book value per share for PB")
    target_net_debt_per_share: float = Field(0.0)
    peers: list[PeerMultiple] = Field(default_factory=list)


class ComparableResult(BaseModel):
    """Output of comparable company analysis."""
    target_ticker: str = ""
    peer_count: int = 0
    median_pe: float | None = None
    median_ev_ebitda: float | None = None
    median_p_fcf: float | None = None
    median_pb: float | None = None
    implied_value_pe: float | None = Field(None, description="Median PE × EPS")
    implied_value_ev_ebitda: float | None = None
    implied_value_p_fcf: float | None = None
    implied_value_pb: float | None = None
    consensus_fair_value: float = Field(0.0, description="Weighted average of implied values")
    weights_used: dict[str, float] = Field(default_factory=dict)


# ── Margin of Safety ─────────────────────────────────────────────────────────

class MarginOfSafety(BaseModel):
    """Margin of safety assessment."""
    ticker: str = ""
    fair_value: float = 0.0
    current_price: float = 0.0
    margin_pct: float = Field(0.0, description="(fair_value - price) / fair_value × 100")
    verdict: ValuationVerdict = ValuationVerdict.FAIR_VALUE
    graham_number: float | None = Field(None, description="√(22.5 × EPS × BV)")


# ── Full Report ──────────────────────────────────────────────────────────────

class ValuationReport(BaseModel):
    """Complete valuation report combining all methods."""
    ticker: str = ""
    dcf: DCFResult | None = None
    comparable: ComparableResult | None = None
    margin_of_safety: MarginOfSafety | None = None
    consensus_fair_value: float = Field(0.0, description="Blended fair value (DCF 50% + Comps 50%)")
    current_price: float = 0.0
    upside_pct: float = Field(0.0, description="(fair_value - price) / price × 100")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
