"""
src/engines/portfolio/transaction_costs.py
--------------------------------------------------------------------------
Transaction Cost Model — estimates trading costs for portfolio construction.

Components
~~~~~~~~~~
- Spread cost: half the bid-ask spread
- Market impact: f(trade_size, avg_daily_volume)
- Commission: per-share + per-trade
- Turnover penalty: annual cost drag from rebalancing frequency

Used by the SignalPortfolioBridge to compute net-of-cost expected returns
and annual cost drag.
"""

from __future__ import annotations

import logging
import math

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.portfolio.costs")


class CostModelConfig(BaseModel):
    """Configuration for transaction cost estimation."""
    # Spread cost
    half_spread_bps: float = Field(
        5.0, ge=0.0,
        description="Half bid-ask spread in basis points (default 5bps for liquid US equities)",
    )

    # Market impact (square-root model)
    impact_coefficient: float = Field(
        0.1, ge=0.0,
        description="Market impact coefficient (Almgren-Chriss simplified)",
    )

    # Commission
    commission_per_share: float = Field(
        0.005, ge=0.0,
        description="Commission per share ($)",
    )
    commission_per_trade: float = Field(
        1.0, ge=0.0,
        description="Fixed commission per trade ($)",
    )
    avg_share_price: float = Field(
        100.0, gt=0.0,
        description="Assumed average share price for commission calculation",
    )

    # Turnover
    avg_turnover_pct: float = Field(
        0.10, ge=0.0,
        description="Assumed average per-rebalance turnover (10% = replacing 10% of portfolio)",
    )


class TradeCostEstimate(BaseModel):
    """Cost breakdown for a single trade."""
    ticker: str = ""
    trade_value: float = 0.0
    spread_cost: float = 0.0
    impact_cost: float = 0.0
    commission_cost: float = 0.0
    total_cost: float = 0.0
    cost_bps: float = 0.0


class TransactionCostModel:
    """
    Estimates round-trip and per-trade transaction costs.

    Usage::

        model = TransactionCostModel()
        cost = model.estimate_trade("AAPL", trade_value=10_000)
        drag = model.annual_cost_drag(weights, rebalance_freq=12)
    """

    def __init__(self, config: CostModelConfig | None = None) -> None:
        self.config = config or CostModelConfig()

    def estimate_trade(
        self,
        ticker: str = "",
        trade_value: float = 10_000.0,
        avg_daily_volume_usd: float = 1_000_000.0,
    ) -> TradeCostEstimate:
        """
        Estimate one-way transaction cost for a trade.

        Parameters
        ----------
        ticker : str
            Ticker symbol (for labeling).
        trade_value : float
            Dollar value of the trade.
        avg_daily_volume_usd : float
            Average daily trading volume in USD.
        """
        if trade_value <= 0:
            return TradeCostEstimate(ticker=ticker)

        # 1. Spread cost
        spread_cost = trade_value * (self.config.half_spread_bps / 10_000)

        # 2. Market impact (square-root model)
        # impact = η × σ × √(trade_value / ADV)
        # Simplified: impact = coefficient × √(participation_rate)
        participation = trade_value / max(avg_daily_volume_usd, 1.0)
        impact_cost = (
            trade_value
            * self.config.impact_coefficient
            * math.sqrt(min(participation, 1.0))
        )

        # 3. Commission
        n_shares = trade_value / self.config.avg_share_price
        commission_cost = (
            n_shares * self.config.commission_per_share
            + self.config.commission_per_trade
        )

        total = spread_cost + impact_cost + commission_cost
        cost_bps = (total / trade_value) * 10_000 if trade_value > 0 else 0.0

        return TradeCostEstimate(
            ticker=ticker,
            trade_value=round(trade_value, 2),
            spread_cost=round(spread_cost, 4),
            impact_cost=round(impact_cost, 4),
            commission_cost=round(commission_cost, 4),
            total_cost=round(total, 4),
            cost_bps=round(cost_bps, 2),
        )

    def annual_cost_drag(
        self,
        weights: dict[str, float],
        rebalance_freq: int = 12,
        portfolio_value: float = 1_000_000.0,
    ) -> float:
        """
        Estimate annualized transaction cost drag.

        Parameters
        ----------
        weights : dict[str, float]
            Optimal portfolio weights {ticker: weight}.
        rebalance_freq : int
            Number of rebalances per year (12 = monthly).
        portfolio_value : float
            Total portfolio value in USD.

        Returns
        -------
        float
            Annual cost drag as a fraction (e.g., 0.0050 = 50bps).
        """
        n_positions = sum(1 for w in weights.values() if w > 0.001)
        if n_positions == 0:
            return 0.0

        # Estimated turnover per rebalance
        turnover_value = portfolio_value * self.config.avg_turnover_pct

        # Cost per rebalance: sum of costs for turnover trades
        # Distribute turnover evenly across positions
        per_position_trade = turnover_value / max(n_positions, 1)

        total_rebal_cost = 0.0
        for ticker, w in weights.items():
            if w <= 0.001:
                continue
            cost = self.estimate_trade(ticker, per_position_trade)
            total_rebal_cost += cost.total_cost

        # Annual drag
        annual_cost = total_rebal_cost * rebalance_freq
        annual_drag = annual_cost / portfolio_value

        return annual_drag
