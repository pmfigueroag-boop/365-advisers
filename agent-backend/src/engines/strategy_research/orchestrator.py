"""
src/engines/strategy_research/orchestrator.py
─────────────────────────────────────────────────────────────────────────────
StrategyOrchestrator — unified pipeline that connects all strategy lifecycle
stages: define → filter → compose → evaluate → backtest → report.

This is the main entry point for the Strategy Research Lab.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.engines.strategy.definition import StrategyDefinition, StrategyConfig
from src.engines.strategy.filter import StrategyFilter
from src.engines.strategy.composer import StrategyComposer
from src.engines.strategy_backtest.engine import StrategyBacktester
from src.engines.strategy_backtest.metrics import StrategyMetrics
from src.engines.strategy_backtest.report import BacktestReport
from src.engines.portfolio_lab.comparison import PortfolioComparison
from .rules import RuleEngine

logger = logging.getLogger("365advisers.strategy_research.orchestrator")


class StrategyOrchestrator:
    """Unified strategy research pipeline.

    Connects existing engines into a coherent workflow:
    1. Load strategy definition
    2. Filter opportunities through signal + score filters
    3. Apply entry rules (RuleEngine)
    4. Apply regime rules
    5. Compose portfolio positions
    6. Run backtest (optional)
    7. Generate report
    """

    def __init__(self):
        self._definitions = StrategyDefinition()
        self._filter = StrategyFilter()

    def research(
        self,
        strategy_id: str | None = None,
        strategy_config: dict | None = None,
        opportunities: list[dict] | None = None,
        prices: dict[str, dict[str, float]] | None = None,
        positions_by_date: dict[str, list[dict]] | None = None,
        benchmark_prices: dict[str, float] | None = None,
        current_regime: str = "unknown",
        run_backtest: bool = False,
        initial_capital: float = 1_000_000.0,
    ) -> dict:
        """Execute a full strategy research pipeline.

        Args:
            strategy_id: Load strategy from registry (OR provide config)
            strategy_config: Inline strategy config dict
            opportunities: Current opportunity set for filtering
            prices: Price matrix for backtesting
            positions_by_date: Historical position targets
            benchmark_prices: Benchmark price series
            current_regime: Current market regime label
            run_backtest: Whether to run full backtest
            initial_capital: Starting capital for backtest

        Returns:
            Full research result with filtering, rules, composition, and optionally backtest.
        """
        research_id = uuid.uuid4().hex[:12]
        started_at = datetime.now(timezone.utc)

        # Step 1: Load strategy
        config = self._resolve_config(strategy_id, strategy_config)
        if not config:
            return {"error": "Strategy not found", "research_id": research_id}

        strategy_name = config.get("_name", "unnamed")
        result: dict[str, Any] = {
            "research_id": research_id,
            "strategy_name": strategy_name,
            "started_at": started_at.isoformat(),
        }

        # Step 2: Regime evaluation
        regime_rules = config.get("regime_rules", [])
        regime_action = RuleEngine.evaluate_regime(current_regime, regime_rules)
        result["regime"] = {
            "current": current_regime,
            "action": regime_action["action"],
            "sizing_override": regime_action["sizing_override"],
        }

        # Early exit if regime says exit_all
        if regime_action["action"] == "exit_all":
            result["status"] = "blocked_by_regime"
            result["positions"] = []
            return result

        # Step 3: Filter opportunities
        if opportunities:
            # Apply signal + score filters (existing StrategyFilter)
            filtered = self._filter.apply(opportunities, config)

            # Apply additional entry rules (new RuleEngine)
            entry_rules = config.get("entry_rules", [])
            if entry_rules:
                entry_rules_dicts = [
                    r if isinstance(r, dict) else r.model_dump()
                    for r in entry_rules
                ]
                passed, rejected = RuleEngine.filter_opportunities(filtered, entry_rules_dicts)
            else:
                passed = filtered
                rejected = []

            result["filtering"] = {
                "total_opportunities": len(opportunities),
                "after_signal_filter": len(filtered),
                "after_entry_rules": len(passed),
                "rejected_by_rules": len(rejected),
            }
        else:
            passed = []
            result["filtering"] = {"note": "No opportunities provided"}

        # Step 4: Compose positions
        if passed:
            # Apply regime sizing override
            effective_config = config.copy()
            if regime_action["sizing_override"] is not None:
                rules = effective_config.get("portfolio_rules", {}).copy()
                rules["max_single_position"] = regime_action["sizing_override"]
                effective_config["portfolio_rules"] = rules

            if regime_action["action"] == "reduce_50":
                rules = effective_config.get("portfolio_rules", {}).copy()
                current_max = rules.get("max_single_position", 0.10)
                rules["max_single_position"] = current_max * 0.5
                effective_config["portfolio_rules"] = rules

            if regime_action["action"] == "no_new_entries":
                result["composition"] = {"note": "No new entries in current regime"}
            else:
                composition = StrategyComposer.compose(
                    strategy_config=effective_config,
                    available_signals=_extract_signals(passed),
                    ticker_scores={o.get("ticker", ""): o.get("uos", 0) for o in passed},
                )
                result["composition"] = composition
        else:
            result["composition"] = {"note": "No opportunities passed filters"}

        # Step 5: Backtest (optional)
        if run_backtest and positions_by_date and prices:
            backtest = StrategyBacktester.run(
                strategy_config={"name": strategy_name, **config},
                positions_by_date=positions_by_date,
                prices=prices,
                initial_capital=initial_capital,
                benchmark_prices=benchmark_prices,
            )
            result["backtest"] = backtest

            # Generate structured report
            result["report"] = BacktestReport.generate(backtest)

        result["completed_at"] = datetime.now(timezone.utc).isoformat()
        result["status"] = "completed"

        return result

    def compare_strategies(
        self,
        strategy_configs: list[dict],
        opportunities: list[dict],
        current_regime: str = "unknown",
    ) -> dict:
        """Run research pipeline for multiple strategies and compare.

        Args:
            strategy_configs: List of strategy config dicts
            opportunities: Shared opportunity set
            current_regime: Current market regime

        Returns:
            Comparison result with per-strategy results and rankings.
        """
        results = []
        for config in strategy_configs:
            r = self.research(
                strategy_config=config,
                opportunities=opportunities,
                current_regime=current_regime,
            )
            results.append(r)

        # Rank by composition quality
        ranked = sorted(
            results,
            key=lambda r: r.get("composition", {}).get("selected_positions", 0),
            reverse=True,
        )

        return {
            "strategies_evaluated": len(results),
            "results": ranked,
            "best_strategy": ranked[0].get("strategy_name") if ranked else None,
        }

    def _resolve_config(self, strategy_id: str | None, inline_config: dict | None) -> dict | None:
        """Load strategy config from registry or use inline."""
        if inline_config:
            return inline_config

        if strategy_id:
            summary = self._definitions.get(strategy_id)
            if summary:
                config = summary.config.copy()
                config["_name"] = summary.name
                config["_strategy_id"] = summary.strategy_id
                return config

        return None


def _extract_signals(opportunities: list[dict]) -> list[dict]:
    """Extract signal-like dicts from opportunities for StrategyComposer."""
    signals = []
    for opp in opportunities:
        signals.append({
            "signal_id": f"opp_{opp.get('ticker', 'UNK')}",
            "ticker": opp.get("ticker", ""),
            "strength": opp.get("signal_strength_label", opp.get("strength", "moderate")),
            "confidence": opp.get("confidence_score", opp.get("confidence", 0.5)),
            "category": opp.get("primary_category", opp.get("category", "general")),
        })
    return signals
