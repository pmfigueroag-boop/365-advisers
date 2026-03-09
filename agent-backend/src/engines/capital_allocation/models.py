"""src/engines/capital_allocation/models.py — Capital allocation data contracts."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field

class AllocationMethod(str, Enum):
    EQUAL = "equal"
    RISK_PARITY = "risk_parity"
    RISK_BUDGET = "risk_budget"
    MOMENTUM_TILT = "momentum_tilt"
    INVERSE_VOL = "inverse_vol"

class StrategyBudget(BaseModel):
    strategy_id: str
    strategy_name: str = ""
    current_allocation: float = 0.0  # current weight
    target_allocation: float = 0.0   # target weight
    volatility: float = 0.10         # annualised vol
    sharpe_ratio: float = 0.0
    recent_return: float = 0.0       # trailing period return
    max_allocation: float = 1.0      # upper bound

class AllocationResult(BaseModel):
    method: AllocationMethod = AllocationMethod.EQUAL
    allocations: dict[str, float] = Field(default_factory=dict, description="strategy_id → weight")
    total_capital: float = 0.0
    analytics: dict[str, float] = Field(default_factory=dict)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DriftEntry(BaseModel):
    strategy_id: str
    current_weight: float = 0.0
    target_weight: float = 0.0
    drift_pct: float = 0.0
    needs_rebalance: bool = False

class DriftReport(BaseModel):
    entries: list[DriftEntry] = Field(default_factory=list)
    max_drift: float = 0.0
    rebalance_needed: bool = False
    threshold: float = 0.05

class RebalanceTrade(BaseModel):
    strategy_id: str
    direction: str  # "increase" or "decrease"
    amount_pct: float = 0.0
