"""
src/engines/backtesting/cross_sectional_models.py
--------------------------------------------------------------------------
Pydantic data contracts for cross-sectional ranking (quintile) analysis.
"""

from __future__ import annotations

from datetime import date
from pydantic import BaseModel, Field


class CrossSectionalConfig(BaseModel):
    """Configuration for a cross-sectional ranking test."""
    universe: list[str] = Field(
        ..., min_length=10, description="At least 10 tickers for meaningful quintiles",
    )
    start_date: date
    end_date: date = Field(default_factory=date.today)
    rebalance_frequency_days: int = Field(
        21, description="Rebalance every N trading days (21 ~ monthly)",
    )
    forward_windows: list[int] = Field(
        default=[20, 60], description="T+N days for forward return measurement",
    )
    benchmark_ticker: str = "SPY"
    include_fundamentals: bool = False


class QuintileResult(BaseModel):
    """Performance of a single quintile over one rebalance period."""
    quintile: int = Field(..., ge=1, le=5, description="1=top, 5=bottom")
    n_tickers: int = 0
    avg_score: float = 0.0
    avg_return: dict[int, float] = Field(default_factory=dict)
    avg_excess_return: dict[int, float] = Field(default_factory=dict)
    tickers: list[str] = Field(default_factory=list)


class RebalancePeriod(BaseModel):
    """Results from a single rebalance date."""
    rebalance_date: date
    scored_tickers: int = 0
    quintiles: list[QuintileResult] = Field(default_factory=list)
    q1_q5_spread: dict[int, float] = Field(
        default_factory=dict, description="Q1 return - Q5 return per window",
    )


class CrossSectionalReport(BaseModel):
    """Top-level cross-sectional ranking report."""
    config: CrossSectionalConfig
    total_periods: int = 0
    periods: list[RebalancePeriod] = Field(default_factory=list)

    # Aggregate metrics
    avg_q1_return: dict[int, float] = Field(default_factory=dict)
    avg_q5_return: dict[int, float] = Field(default_factory=dict)
    avg_spread: dict[int, float] = Field(
        default_factory=dict, description="Average Q1-Q5 spread per window",
    )
    spread_t_stat: dict[int, float] = Field(
        default_factory=dict, description="T-statistic of Q1-Q5 spread",
    )
    spread_p_value: dict[int, float] = Field(
        default_factory=dict, description="P-value of Q1-Q5 spread",
    )
    is_monotonic: dict[int, float] = Field(
        default_factory=dict,
        description="Spearman correlation quintile_rank vs return (1.0 = perfect monotonicity)",
    )
    avg_turnover: float = 0.0
    execution_time_seconds: float = 0.0
