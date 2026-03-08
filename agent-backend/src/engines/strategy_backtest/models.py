"""
src/engines/strategy_backtest/models.py
─────────────────────────────────────────────────────────────────────────────
BacktestDataBundle & BacktestResult — structured data models for the
Strategy Backtesting Framework.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


class BacktestDataBundle(BaseModel):
    """All data required by the backtest engine.

    The engine does NOT fetch data internally — the caller provides
    this bundle, enabling unit testing with synthetic data and
    decoupling from specific data providers.
    """
    # Price matrix: {ticker: {date_str: adjusted_close_price}}
    prices: dict[str, dict[str, float]] = Field(default_factory=dict)

    # Signals active on each date: {date: [{signal_id, ticker, category, strength, confidence, ...}]}
    signals_by_date: dict[str, list[dict]] = Field(default_factory=dict)

    # Scores on each date: {date: {ticker: {case_score, uos, business_quality, opportunity_score}}}
    scores_by_date: dict[str, dict[str, dict[str, float]]] = Field(default_factory=dict)

    # Regime label on each date: {date: "bull"|"bear"|"range"|"high_vol"|"low_vol"}
    regimes_by_date: dict[str, str] = Field(default_factory=dict)

    # Benchmark price series: {date: price}
    benchmark_prices: dict[str, float] = Field(default_factory=dict)

    # Average daily volume per ticker (for cost model): {ticker: adv_usd}
    liquidity: dict[str, float] = Field(default_factory=dict)


class TradeRecord(BaseModel):
    """A single buy or sell trade."""
    date: str
    ticker: str
    action: str              # "buy" | "sell"
    weight: float
    cost_bps: float = 0.0
    cost_usd: float = 0.0
    reason: str = ""         # "entry_rule" | "exit_rule" | "regime" | "rebalance"


class PositionSnapshot(BaseModel):
    """Portfolio state at a point in time."""
    date: str
    positions: list[dict[str, Any]] = Field(default_factory=list)  # [{ticker, weight}]
    turnover: float = 0.0
    positions_count: int = 0


class EquityCurvePoint(BaseModel):
    """Single point on the equity curve."""
    date: str
    portfolio_value: float
    benchmark_value: float | None = None
    drawdown: float = 0.0
    regime: str = "unknown"
    positions_count: int = 0


class CostBreakdown(BaseModel):
    """Aggregate cost analysis."""
    total_cost_usd: float = 0.0
    total_cost_bps: float = 0.0
    avg_cost_per_trade_bps: float = 0.0
    commission_total: float = 0.0
    spread_total: float = 0.0
    slippage_total: float = 0.0
    impact_total: float = 0.0
