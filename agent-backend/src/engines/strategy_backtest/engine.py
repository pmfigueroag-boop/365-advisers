"""
src/engines/strategy_backtest/engine.py
─────────────────────────────────────────────────────────────────────────────
StrategyBacktester — run a strategy through historical data and produce
a full equity curve with position-level detail.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from .metrics import StrategyMetrics

logger = logging.getLogger("365advisers.strategy_backtest.engine")


class StrategyBacktester:
    """Core strategy backtesting engine."""

    @staticmethod
    def run(
        strategy_config: dict,
        positions_by_date: dict[str, list[dict]],
        prices: dict[str, dict[str, float]],
        cost_per_trade_bps: float = 5.0,
        initial_capital: float = 1_000_000.0,
        benchmark_prices: dict[str, float] | None = None,
    ) -> dict:
        """Run a full strategy backtest.

        Args:
            strategy_config: Strategy definition dict
            positions_by_date: {date: [{ticker, weight}]} — target positions per date
            prices: {ticker: {date: price}} — price matrix
            cost_per_trade_bps: Flat cost per trade in bps
            initial_capital: Starting capital
            benchmark_prices: {date: price} for benchmark comparison

        Returns:
            Full backtest result with equity curve, trades, and metrics.
        """
        run_id = uuid.uuid4().hex[:12]
        dates = sorted(positions_by_date.keys())

        if not dates:
            return {"error": "No dates provided", "run_id": run_id}

        equity_curve = []
        trades = []
        portfolio_value = initial_capital
        current_holdings: dict[str, float] = {}  # ticker -> weight
        total_cost = 0.0

        for i, date in enumerate(dates):
            target_positions = positions_by_date[date]
            target_weights = {p["ticker"]: p["weight"] for p in target_positions}

            # Calculate returns from previous holdings
            if i > 0 and current_holdings:
                prev_date = dates[i - 1]
                period_return = 0.0
                for ticker, weight in current_holdings.items():
                    p_prev = (prices.get(ticker, {}).get(prev_date, 0) or 0)
                    p_curr = (prices.get(ticker, {}).get(date, 0) or 0)
                    if p_prev > 0:
                        ticker_return = (p_curr - p_prev) / p_prev
                        period_return += weight * ticker_return

                portfolio_value *= (1 + period_return)

            # Calculate rebalancing costs
            turnover = 0.0
            for ticker in set(list(current_holdings.keys()) + list(target_weights.keys())):
                old_w = current_holdings.get(ticker, 0.0)
                new_w = target_weights.get(ticker, 0.0)
                turnover += abs(new_w - old_w)

            trade_cost = portfolio_value * turnover * cost_per_trade_bps / 10_000
            portfolio_value -= trade_cost
            total_cost += trade_cost

            if turnover > 0:
                trades.append({
                    "date": date,
                    "turnover": round(turnover, 4),
                    "cost_usd": round(trade_cost, 2),
                    "positions_before": len(current_holdings),
                    "positions_after": len(target_weights),
                })

            # Update holdings
            current_holdings = target_weights.copy()

            # Record equity curve
            benchmark_val = None
            if benchmark_prices:
                bm_p = benchmark_prices.get(date, 0)
                bm_first = benchmark_prices.get(dates[0], 1)
                benchmark_val = initial_capital * (bm_p / bm_first) if bm_first > 0 else None

            equity_curve.append({
                "date": date,
                "portfolio_value": round(portfolio_value, 2),
                "benchmark_value": round(benchmark_val, 2) if benchmark_val else None,
            })

        # Compute metrics
        pv_series = [e["portfolio_value"] for e in equity_curve]
        bm_series = [e.get("benchmark_value") for e in equity_curve if e.get("benchmark_value") is not None]
        metrics = StrategyMetrics.compute(pv_series, bm_series if bm_series else None)

        return {
            "run_id": run_id,
            "strategy_name": strategy_config.get("name", "unnamed"),
            "period": [dates[0], dates[-1]] if dates else [],
            "initial_capital": initial_capital,
            "final_value": round(portfolio_value, 2),
            "total_return": round((portfolio_value - initial_capital) / initial_capital, 4),
            "total_trades": len(trades),
            "total_cost_usd": round(total_cost, 2),
            "metrics": metrics,
            "equity_curve": equity_curve,
            "trades": trades,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
