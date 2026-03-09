"""src/engines/risk/models.py — Risk engine data contracts."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field

class VaRMethod(str, Enum):
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    MONTE_CARLO = "monte_carlo"

class VaRResult(BaseModel):
    method: VaRMethod
    confidence_level: float = 0.95
    horizon_days: int = 1
    var_amount: float = Field(0.0, description="VaR in currency units")
    var_pct: float = Field(0.0, description="VaR as % of portfolio")
    portfolio_value: float = 0.0

class CVaRResult(BaseModel):
    method: VaRMethod
    confidence_level: float = 0.95
    cvar_amount: float = 0.0
    cvar_pct: float = 0.0
    var_amount: float = 0.0

class StressScenario(BaseModel):
    name: str
    description: str = ""
    shocks: dict[str, float] = Field(default_factory=dict, description="ticker → return shock")

class StressResult(BaseModel):
    scenario_name: str
    portfolio_impact_pct: float = 0.0
    portfolio_impact_amount: float = 0.0
    worst_position: str = ""
    worst_position_impact: float = 0.0

class RiskReport(BaseModel):
    portfolio_value: float = 0.0
    var: VaRResult | None = None
    cvar: CVaRResult | None = None
    stress_results: list[StressResult] = Field(default_factory=list)
    risk_summary: dict[str, float] = Field(default_factory=dict)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
