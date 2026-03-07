"""
src/engines/portfolio_lab/simulator.py
─────────────────────────────────────────────────────────────────────────────
PortfolioSimulator — run portfolio-level simulations with multiple strategies.

Orchestrates StrategyBacktester across multiple portfolio configurations:
  - Different sizing methods
  - Different signal filter configurations
  - Different rebalance frequencies
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from src.engines.strategy_backtest.engine import StrategyBacktester
from src.engines.strategy_backtest.metrics import StrategyMetrics

logger = logging.getLogger("365advisers.portfolio_lab.simulator")


class PortfolioSimulator:
    """Multi-portfolio simulation engine."""

    @staticmethod
    def simulate_variants(
        base_config: dict,
        variants: list[dict],
        positions_by_date: dict[str, list[dict]],
        prices: dict[str, dict[str, float]],
        initial_capital: float = 1_000_000.0,
        benchmark_prices: dict[str, float] | None = None,
    ) -> dict:
        """Run multiple portfolio variants and compare.

        Args:
            base_config: Base strategy config dict
            variants: [{name, config_overrides}] — each variant overrides base
            positions_by_date: Target positions per date
            prices: Price matrix
            initial_capital: Starting capital
            benchmark_prices: Benchmark price series

        Returns:
            Simulation results with per-variant metrics and rankings.
        """
        sim_id = uuid.uuid4().hex[:12]
        results = []

        for variant in variants:
            # Merge config
            merged = {**base_config}
            overrides = variant.get("config_overrides", {})
            for key, val in overrides.items():
                if isinstance(val, dict) and key in merged:
                    merged[key] = {**merged[key], **val}
                else:
                    merged[key] = val

            merged["name"] = variant.get("name", "variant")

            # Run backtest
            cost_bps = overrides.get("cost_per_trade_bps", 5.0)
            result = StrategyBacktester.run(
                strategy_config=merged,
                positions_by_date=positions_by_date,
                prices=prices,
                cost_per_trade_bps=cost_bps,
                initial_capital=initial_capital,
                benchmark_prices=benchmark_prices,
            )
            results.append(result)

        # Rank by Sharpe
        ranked = sorted(results, key=lambda r: r.get("metrics", {}).get("sharpe_ratio", 0), reverse=True)

        return {
            "simulation_id": sim_id,
            "variant_count": len(results),
            "results": ranked,
            "best_variant": ranked[0].get("strategy_name") if ranked else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def generate_sizing_variants(base_config: dict) -> list[dict]:
        """Generate standard sizing method variants."""
        return [
            {"name": "Equal Weight", "config_overrides": {"portfolio_rules": {"sizing_method": "equal"}}},
            {"name": "Rank Weighted", "config_overrides": {"portfolio_rules": {"sizing_method": "rank_weighted"}}},
            {"name": "Vol Parity", "config_overrides": {"portfolio_rules": {"sizing_method": "vol_parity"}}},
        ]

    @staticmethod
    def generate_position_count_variants(base_config: dict) -> list[dict]:
        """Generate variants with different max position counts."""
        return [
            {"name": f"{n} Positions", "config_overrides": {"portfolio_rules": {"max_positions": n}}}
            for n in [5, 10, 15, 20, 30]
        ]
