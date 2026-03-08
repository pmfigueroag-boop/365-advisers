"""
src/engines/strategy_portfolio/models.py
─────────────────────────────────────────────────────────────────────────────
Strategy Portfolio Lab — data models for multi-strategy portfolio management.
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field
from typing import Any


class PortfolioType(str, Enum):
    RESEARCH = "research"
    STRATEGY = "strategy"
    BENCHMARK = "benchmark"
    MULTI_STRATEGY = "multi_strategy"


class StrategyAllocation(BaseModel):
    """A single strategy's allocation within a portfolio."""
    strategy_id: str | None = None
    strategy_name: str
    strategy_config: dict = Field(default_factory=dict)
    target_weight: float = 0.0
    current_weight: float = 0.0


class PortfolioConstraints(BaseModel):
    """Constraints for the strategy portfolio."""
    max_strategies: int = 10
    max_single_strategy_weight: float = 0.50
    min_strategy_weight: float = 0.05
    max_strategy_correlation: float = 0.85
    max_total_leverage: float = 1.0


class StrategyPortfolio(BaseModel):
    """A portfolio of multiple strategies."""
    portfolio_id: str | None = None
    name: str = "Untitled Portfolio"
    portfolio_type: PortfolioType = PortfolioType.MULTI_STRATEGY
    strategies: list[StrategyAllocation] = Field(default_factory=list)
    allocation_method: str = "equal"  # equal | risk_parity | mean_variance | sharpe_optimal | regime_adaptive | momentum
    constraints: PortfolioConstraints = Field(default_factory=PortfolioConstraints)
    rebalance_frequency: str = "monthly"
    benchmark: str = "SPY"
    created_at: str | None = None
    lifecycle_state: str = "research"


class DiversificationReport(BaseModel):
    """Diversification analysis results."""
    correlation_matrix: dict[str, dict[str, float]] = Field(default_factory=dict)
    diversification_ratio: float = 0.0
    position_overlap: dict[str, float] = Field(default_factory=dict)
    signal_redundancy: dict[str, float] = Field(default_factory=dict)
    concentration_index: float = 0.0  # HHI
    max_correlation: float = 0.0
    verdict: str = "unknown"  # well_diversified | moderately_diversified | concentrated


class ContributionResult(BaseModel):
    """Per-strategy contribution to portfolio returns."""
    strategy_name: str
    weight: float = 0.0
    strategy_return: float = 0.0
    weighted_return: float = 0.0
    contribution_pct: float = 0.0  # % of total portfolio return


class PortfolioMonitorState(BaseModel):
    """Live monitoring state for a strategy portfolio."""
    portfolio_id: str | None = None
    last_updated: str | None = None
    current_composition: list[dict] = Field(default_factory=list)
    performance_vs_benchmark: dict = Field(default_factory=dict)
    regime_alignment: dict = Field(default_factory=dict)
    alerts: list[dict] = Field(default_factory=list)
    rebalance_recommendation: dict | None = None
