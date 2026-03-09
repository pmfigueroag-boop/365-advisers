"""
src/engines/autonomous_pm/models.py
──────────────────────────────────────────────────────────────────────────────
Data contracts for the Autonomous Portfolio Manager (APM).

Covers: Portfolio objectives, allocation methods, rebalance triggers,
        positions, risk violations, performance snapshots, and the
        master APM dashboard output.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ── Portfolio Objectives ─────────────────────────────────────────────────────

class PortfolioObjective(str, Enum):
    GROWTH = "growth"
    VALUE = "value"
    INCOME = "income"
    BALANCED = "balanced"
    DEFENSIVE = "defensive"
    OPPORTUNISTIC = "opportunistic"


# ── Allocation Methods ───────────────────────────────────────────────────────

class AllocationMethodAPM(str, Enum):
    RISK_PARITY = "risk_parity"
    VOLATILITY_TARGETING = "volatility_targeting"
    FACTOR_DIVERSIFICATION = "factor_diversification"
    EQUAL_RISK_CONTRIBUTION = "equal_risk_contribution"
    MAX_SHARPE = "max_sharpe"
    MIN_VARIANCE = "min_variance"


# ── Rebalance Triggers ───────────────────────────────────────────────────────

class RebalanceTrigger(str, Enum):
    REGIME_CHANGE = "regime_change"
    ALPHA_SHIFT = "alpha_shift"
    RISK_ESCALATION = "risk_escalation"
    WEIGHT_DRIFT = "weight_drift"
    MARKET_EVENT = "market_event"


class RebalanceUrgency(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    IMMEDIATE = "immediate"


# ── Risk Violation Types ─────────────────────────────────────────────────────

class RiskViolationType(str, Enum):
    CONCENTRATION_BREACH = "concentration_breach"
    VOLATILITY_EXCESS = "volatility_excess"
    DRAWDOWN_WARNING = "drawdown_warning"
    CORRELATION_SPIKE = "correlation_spike"
    SECTOR_OVERWEIGHT = "sector_overweight"


class RiskViolationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ── Position ─────────────────────────────────────────────────────────────────

class APMPosition(BaseModel):
    """Single position within a managed portfolio."""
    ticker: str
    weight: float = Field(0.0, ge=0, le=1.0)
    alpha_score: float = 0.0
    justification: str = ""
    factor_exposures: dict[str, float] = Field(default_factory=dict)
    sector: str = ""
    signals_used: list[str] = Field(default_factory=list)


# ── Portfolio ────────────────────────────────────────────────────────────────

class APMPortfolio(BaseModel):
    """A fully constructed, managed portfolio."""
    objective: PortfolioObjective
    positions: list[APMPosition] = Field(default_factory=list)
    allocation_method: AllocationMethodAPM = AllocationMethodAPM.RISK_PARITY
    total_weight: float = 1.0
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    regime_context: str = ""
    rationale: str = ""
    constructed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Rebalancing ──────────────────────────────────────────────────────────────

class RebalanceAction(BaseModel):
    """A specific trade recommendation."""
    ticker: str
    direction: str = "hold"  # buy / sell / hold
    current_weight: float = 0.0
    target_weight: float = 0.0
    weight_change: float = 0.0
    reason: str = ""


class RebalanceRecommendation(BaseModel):
    """Full rebalance recommendation with trigger analysis."""
    triggers_fired: list[RebalanceTrigger] = Field(default_factory=list)
    urgency: RebalanceUrgency = RebalanceUrgency.LOW
    actions: list[RebalanceAction] = Field(default_factory=list)
    summary: str = ""
    should_rebalance: bool = False
    regime_before: str = ""
    regime_after: str = ""
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Risk Management ─────────────────────────────────────────────────────────

class RiskViolation(BaseModel):
    """A single risk policy violation."""
    violation_type: RiskViolationType
    severity: RiskViolationSeverity = RiskViolationSeverity.WARNING
    title: str
    description: str
    affected_tickers: list[str] = Field(default_factory=list)
    current_value: float = 0.0
    threshold: float = 0.0
    remediation: str = ""


class PortfolioRiskReport(BaseModel):
    """Comprehensive risk assessment for a portfolio."""
    portfolio_volatility: float = 0.0
    max_drawdown: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    concentration_hhi: float = 0.0
    sector_exposures: dict[str, float] = Field(default_factory=dict)
    violations: list[RiskViolation] = Field(default_factory=list)
    risk_score: float = Field(0.0, ge=0, le=100)
    within_limits: bool = True


# ── Performance Analysis ─────────────────────────────────────────────────────

class PerformanceSnapshot(BaseModel):
    """Performance metrics for a portfolio at a point in time."""
    total_return: float = 0.0
    annualized_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    alpha_vs_benchmark: float = 0.0
    beta: float = 0.0
    information_ratio: float = 0.0
    tracking_error: float = 0.0
    benchmark_name: str = "S&P 500"
    benchmark_return: float = 0.0
    period_days: int = 0
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Master Dashboard ─────────────────────────────────────────────────────────

class APMDashboard(BaseModel):
    """Complete Autonomous Portfolio Manager output."""
    portfolios: list[APMPortfolio] = Field(default_factory=list)
    rebalance: RebalanceRecommendation | None = None
    risk_report: PortfolioRiskReport | None = None
    performance: PerformanceSnapshot | None = None
    explanations: list[str] = Field(default_factory=list)
    asset_count: int = 0
    active_regime: str = ""
    managed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0.0"
