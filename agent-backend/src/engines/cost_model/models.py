"""
src/engines/cost_model/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Transaction Cost & Slippage Model.

Defines configuration, per-trade cost breakdowns, aggregated signal
cost profiles, and the complete analysis report.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ─── Enumerations ────────────────────────────────────────────────────────────

class SpreadMethod(str, Enum):
    """How to estimate bid-ask spread."""
    AUTO = "auto"        # Corwin-Schultz from OHLCV
    FIXED = "fixed"      # User-provided fixed bps


class CostResilience(str, Enum):
    """Signal alpha resilience to transaction costs."""
    RESILIENT = "resilient"   # ≥ 0.70
    MODERATE = "moderate"     # 0.40–0.69
    FRAGILE = "fragile"       # < 0.40


# ─── Configuration ───────────────────────────────────────────────────────────

class CostModelConfig(BaseModel):
    """Parameters for the transaction cost model."""
    eta: float = Field(
        0.1, ge=0.0, le=1.0,
        description="Market impact coefficient (Almgren-Chriss η)",
    )
    assumed_trade_usd: float = Field(
        100_000, ge=1_000,
        description="Assumed notional trade size (USD)",
    )
    slippage_bps: float = Field(
        5.0, ge=0.0,
        description="Fixed execution slippage (basis points per side)",
    )
    commission_bps: float = Field(
        5.0, ge=0.0,
        description="Broker commission (basis points per side)",
    )
    spread_method: SpreadMethod = Field(
        SpreadMethod.AUTO,
        description="'auto' (Corwin-Schultz) or 'fixed'",
    )
    fixed_spread_bps: float = Field(
        10.0, ge=0.0,
        description="Used only when spread_method='fixed'",
    )
    round_trip: bool = Field(
        True,
        description="Apply costs for both entry and exit",
    )


# ─── Per-Trade Cost Breakdown ────────────────────────────────────────────────

class TradeCostBreakdown(BaseModel):
    """Cost decomposition for a single signal firing event."""
    signal_id: str
    ticker: str
    fired_date: date
    # Input data
    price_at_fire: float = 0.0
    daily_volume: float = 0.0
    daily_volatility: float = 0.0
    # Cost components (as fraction of notional)
    spread_cost: float = 0.0
    impact_cost: float = 0.0
    slippage_cost: float = 0.0
    commission_cost: float = 0.0
    total_cost: float = 0.0
    # Per-window adjustments
    raw_returns: dict[int, float] = Field(default_factory=dict)
    adjusted_returns: dict[int, float] = Field(default_factory=dict)
    cost_drag: dict[int, float] = Field(
        default_factory=dict,
        description="{window: raw_return − adjusted_return}",
    )


# ─── Aggregated Signal Cost Profile ──────────────────────────────────────────

class SignalCostProfile(BaseModel):
    """Aggregated cost impact for a signal across all its events."""
    signal_id: str
    signal_name: str = ""
    total_events: int = 0
    # Raw vs Adjusted comparison
    raw_sharpe: dict[int, float] = Field(default_factory=dict)
    adjusted_sharpe: dict[int, float] = Field(default_factory=dict)
    raw_hit_rate: dict[int, float] = Field(default_factory=dict)
    adjusted_hit_rate: dict[int, float] = Field(default_factory=dict)
    raw_alpha: dict[int, float] = Field(default_factory=dict)
    net_alpha: dict[int, float] = Field(default_factory=dict)
    # Cost statistics
    avg_total_cost: float = 0.0
    avg_spread_cost: float = 0.0
    avg_impact_cost: float = 0.0
    avg_slippage_cost: float = 0.0
    avg_commission_cost: float = 0.0
    total_cost_drag_bps: float = 0.0
    cost_adjusted_tier: str = "D"
    # Sensitivity
    breakeven_cost_bps: float = 0.0
    cost_resilience_score: float = 0.0
    cost_resilience_class: CostResilience = CostResilience.FRAGILE


# ─── Complete Report ─────────────────────────────────────────────────────────

class CostModelReport(BaseModel):
    """Full output of a cost-model analysis."""
    config: CostModelConfig
    signal_profiles: list[SignalCostProfile] = Field(default_factory=list)
    cost_resilient_signals: list[str] = Field(
        default_factory=list,
        description="Signal IDs with resilience ≥ RESILIENT",
    )
    cost_fragile_signals: list[str] = Field(
        default_factory=list,
        description="Signal IDs classified as FRAGILE",
    )
    avg_cost_drag_bps: float = 0.0
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
