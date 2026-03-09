"""
src/engines/long_short/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Long/Short Equity subsystem.

Defines position side classification, short-position tracking,
L/S portfolio structure, exposure metrics, and borrow-cost estimates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ── Enumerations ─────────────────────────────────────────────────────────────

class PositionSide(str, Enum):
    """Position direction."""
    LONG = "long"
    SHORT = "short"


class BorrowTier(str, Enum):
    """Short-sale borrow difficulty tiers."""
    GENERAL_COLLATERAL = "general_collateral"   # ≤ 0.30% annualized
    EASY_TO_BORROW = "easy_to_borrow"           # 0.30% – 1.0%
    HARD_TO_BORROW = "hard_to_borrow"           # 1.0%  – 5.0%
    SPECIAL = "special"                         # > 5.0%


# ── Position Models ──────────────────────────────────────────────────────────

class LongShortPosition(BaseModel):
    """A single position in a Long/Short portfolio."""
    ticker: str
    side: PositionSide
    weight: float = Field(ge=0.0, le=1.0, description="Absolute weight (0.0–1.0)")
    entry_price: float | None = None
    current_price: float | None = None
    beta: float = Field(1.0, description="Asset beta relative to benchmark")
    sector: str = "Unknown"
    volatility_atr: float = Field(2.0, ge=0.0, description="ATR for volatility parity")
    borrow_rate: float = Field(0.0, ge=0.0, description="Annual borrow rate (short only)")
    days_held: int = Field(0, ge=0)

    @property
    def unrealized_pnl_pct(self) -> float | None:
        """Unrealized P&L as a percentage, accounting for position side."""
        if self.entry_price is None or self.current_price is None or self.entry_price == 0:
            return None
        raw = (self.current_price - self.entry_price) / self.entry_price
        return raw if self.side == PositionSide.LONG else -raw

    @property
    def daily_borrow_cost(self) -> float:
        """Daily borrow cost for short positions (annualized rate / 252)."""
        if self.side == PositionSide.SHORT:
            return self.borrow_rate / 252.0
        return 0.0


# ── Exposure Metrics ─────────────────────────────────────────────────────────

class ExposureMetrics(BaseModel):
    """Aggregate exposure metrics for a Long/Short portfolio."""
    gross_exposure: float = Field(
        0.0, ge=0.0,
        description="Sum of absolute weights (long + short). 1.0 = 100%.",
    )
    net_exposure: float = Field(
        0.0,
        description="Long weight minus short weight. Positive = net long.",
    )
    long_exposure: float = Field(0.0, ge=0.0)
    short_exposure: float = Field(0.0, ge=0.0)
    beta_exposure: float = Field(
        0.0,
        description="Weighted sum of betas. Near 0 = market neutral.",
    )
    leverage_ratio: float = Field(
        0.0, ge=0.0,
        description="Gross exposure as a multiple of capital (≥ 1.0 implies leverage).",
    )
    long_count: int = 0
    short_count: int = 0


# ── Borrow Cost ──────────────────────────────────────────────────────────────

class BorrowCostEstimate(BaseModel):
    """Estimated borrow cost for a short position."""
    ticker: str
    annual_rate: float = Field(ge=0.0, description="Annualized borrow rate (e.g. 0.003 = 0.3%)")
    tier: BorrowTier = BorrowTier.GENERAL_COLLATERAL
    estimated_daily_cost_bps: float = Field(
        0.0, ge=0.0,
        description="Daily cost in basis points per unit of position.",
    )
    availability_note: str = ""


# ── Portfolio Aggregate ──────────────────────────────────────────────────────

class LongShortPortfolio(BaseModel):
    """Complete Long/Short portfolio with both legs."""
    long_positions: list[LongShortPosition] = Field(default_factory=list)
    short_positions: list[LongShortPosition] = Field(default_factory=list)
    exposure: ExposureMetrics = Field(default_factory=ExposureMetrics)
    total_borrow_cost_annual_bps: float = Field(
        0.0, ge=0.0,
        description="Aggregate annual borrow cost across all short positions (bps).",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Engine Result ────────────────────────────────────────────────────────────

class LongShortResult(BaseModel):
    """Full output of the LongShortEngine.construct() call."""
    portfolio: LongShortPortfolio = Field(default_factory=LongShortPortfolio)
    exposure: ExposureMetrics = Field(default_factory=ExposureMetrics)
    constraints_applied: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)
