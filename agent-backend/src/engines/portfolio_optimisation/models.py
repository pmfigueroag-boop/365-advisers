"""
src/engines/portfolio_optimisation/models.py — MVO data contracts.
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class OptimisationObjective(str, Enum):
    MIN_VARIANCE = "min_variance"
    MAX_SHARPE = "max_sharpe"
    TARGET_RETURN = "target_return"
    TARGET_RISK = "target_risk"
    RISK_PARITY = "risk_parity"


class PortfolioConstraints(BaseModel):
    """Box + group constraints for optimisation."""
    min_weight: float = 0.0          # per-asset floor
    max_weight: float = 1.0          # per-asset cap
    long_only: bool = True           # no shorting
    max_assets: int | None = None    # cardinality constraint
    group_constraints: dict[str, tuple[float, float]] = Field(
        default_factory=dict,
        description="group_name → (min_total, max_total)",
    )
    turnover_limit: float | None = None  # max total turnover vs current
    current_weights: dict[str, float] = Field(default_factory=dict)


class PortfolioPoint(BaseModel):
    """A single point on the efficient frontier."""
    expected_return: float
    volatility: float
    sharpe_ratio: float = 0.0
    weights: dict[str, float] = Field(default_factory=dict)


class EfficientFrontierResult(BaseModel):
    points: list[PortfolioPoint] = Field(default_factory=list)
    min_variance_portfolio: PortfolioPoint | None = None
    max_sharpe_portfolio: PortfolioPoint | None = None
    tickers: list[str] = Field(default_factory=list)
    risk_free_rate: float = 0.0
    num_points: int = 0


class BlackLittermanInputs(BaseModel):
    """Views for Black-Litterman model."""
    market_caps: dict[str, float] = Field(default_factory=dict)
    views: list[dict] = Field(
        default_factory=list,
        description="List of views: {assets: [tickers], returns: [expected], confidence: float}",
    )
    risk_aversion: float = 2.5  # delta
    tau: float = 0.05  # uncertainty scalar


class OptimisationResult(BaseModel):
    objective: OptimisationObjective
    optimal_weights: dict[str, float] = Field(default_factory=dict)
    expected_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    risk_free_rate: float = 0.0
    constraints_applied: list[str] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
