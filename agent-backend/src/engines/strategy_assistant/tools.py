"""
src/engines/strategy_assistant/tools.py
─────────────────────────────────────────────────────────────────────────────
Research tools for the Strategy AI Assistant.

10 structured tools backed by existing research engines.
Each tool has a clear schema and delegates to an existing engine.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("365advisers.strategy_assistant.tools")


# ── Tool 1: List Signals ─────────────────────────────────────────────────────

def list_signals(category: str = "", enabled_only: bool = True) -> list[dict]:
    """List available alpha signals from the Signal Registry.

    Use when the user asks about available signals, signal categories,
    or wants to know what signals exist for a specific category.
    """
    try:
        from src.engines.alpha_signals.registry import registry
        if category:
            from src.engines.alpha_signals.models import SignalCategory
            try:
                cat = SignalCategory(category)
                signals = registry.get_enabled_by_category(cat) if enabled_only else registry.get_by_category(cat)
            except ValueError:
                signals = registry.get_enabled() if enabled_only else registry.get_all()
        else:
            signals = registry.get_enabled() if enabled_only else registry.get_all()

        return [{"id": s.id, "name": s.name, "category": s.category.value, "enabled": s.enabled} for s in signals]
    except Exception as e:
        logger.warning("list_signals fallback: %s", e)
        return [{"info": "Signal registry not available", "error": str(e)}]


# ── Tool 2: Get Strategy ─────────────────────────────────────────────────────

def get_strategy(strategy_id: str) -> dict:
    """Get a strategy definition from the Strategy Registry.

    Use when the user asks about a specific strategy's configuration,
    signals used, parameters, or lifecycle state.
    """
    try:
        from src.engines.strategy.registry import StrategyRegistry
        reg = StrategyRegistry()
        result = reg.get_strategy(strategy_id)
        return result if result else {"error": "Strategy not found"}
    except Exception as e:
        return {"error": str(e)}


# ── Tool 3: Search Strategies ─────────────────────────────────────────────────

def search_strategies(
    search: str = "",
    strategy_type: str = "",
    risk_level: str = "",
    min_sharpe: float = 0,
    regime: str = "",
) -> list[dict]:
    """Search the Strategy Marketplace for published strategies.

    Use when the user asks about available strategies, wants to find strategies
    by type, performance, or regime compatibility.
    """
    try:
        from src.engines.strategy_marketplace import StrategyMarketplace, MarketplaceSearchParams
        params = MarketplaceSearchParams(
            search=search or None,
            strategy_type=strategy_type or None,
            risk_level=risk_level or None,
            min_sharpe=min_sharpe or None,
            regime=regime or None,
        )
        results = StrategyMarketplace.search(params)
        return [r.model_dump() for r in results[:10]]
    except Exception as e:
        return [{"error": str(e)}]


# ── Tool 4: Run Research Pipeline ─────────────────────────────────────────────

def run_research(strategy_config: dict, opportunities: list[dict] | None = None) -> dict:
    """Execute a full strategy research pipeline.

    Use when the user wants to evaluate a strategy, run a backtest,
    or see comprehensive research results.
    """
    try:
        from src.engines.strategy_research.orchestrator import StrategyOrchestrator
        orch = StrategyOrchestrator()
        return orch.research(strategy_config=strategy_config, opportunities=opportunities or [])
    except Exception as e:
        return {"error": str(e), "note": "Research pipeline unavailable"}


# ── Tool 5: Get Scorecard ────────────────────────────────────────────────────

def get_scorecard(backtest_result: dict | None = None, signal_report: dict | None = None) -> dict:
    """Compute a strategy quality scorecard (0-100, 5 dimensions).

    Use when the user asks about strategy quality, wants to know
    a strategy's strengths and weaknesses, or needs quality grades.
    """
    try:
        from src.engines.strategy_research.scorecard import StrategyScorecard
        return StrategyScorecard.compute(backtest_result=backtest_result, signal_lab_report=signal_report)
    except Exception as e:
        return {"error": str(e)}


# ── Tool 6: Search Experiments ────────────────────────────────────────────────

def search_experiments(
    experiment_type: str = "",
    tags: list[str] | None = None,
    search: str = "",
    status: str = "",
) -> list[dict]:
    """Search the Experiment Tracking System for experiments.

    Use when the user asks about past experiments, their results,
    or wants to find experiments by type or tags.
    """
    try:
        from src.engines.experiment_tracking import ResearchExperimentTracker
        results = ResearchExperimentTracker.list_experiments(
            experiment_type=experiment_type or None,
            tags=tags,
            search=search or None,
            status=status or None,
        )
        return [r.model_dump() for r in results[:10]]
    except Exception as e:
        return [{"error": str(e)}]


# ── Tool 7: Query Knowledge Graph ────────────────────────────────────────────

def query_graph(node_id: str, query_type: str = "neighbors") -> dict:
    """Query the Research Knowledge Graph.

    Use when the user asks about relationships between signals, strategies,
    portfolios, experiments — e.g., "what strategies use this signal?"

    query_type: neighbors, ancestors, descendants, impact, subgraph
    """
    try:
        from src.engines.knowledge_graph import ResearchKnowledgeGraph
        graph = ResearchKnowledgeGraph()  # Would use singleton in production
        if query_type == "neighbors":
            return {"neighbors": graph.neighbors(node_id)}
        elif query_type == "ancestors":
            return {"ancestors": graph.ancestors(node_id)}
        elif query_type == "descendants":
            return {"descendants": graph.descendants(node_id)}
        elif query_type == "impact":
            return graph.impact_analysis(node_id)
        elif query_type == "subgraph":
            return graph.subgraph(node_id)
        else:
            return {"error": f"Unknown query type: {query_type}"}
    except Exception as e:
        return {"error": str(e)}


# ── Tool 8: Discover Patterns ─────────────────────────────────────────────────

def discover_patterns() -> dict:
    """Run pattern discovery on the Knowledge Graph.

    Use when the user asks about signal co-usage, hub signals,
    orphan nodes, strategy clusters, or research patterns.
    """
    try:
        from src.engines.knowledge_graph import ResearchKnowledgeGraph, PatternDiscovery
        graph = ResearchKnowledgeGraph()
        return PatternDiscovery.analyze(graph)
    except Exception as e:
        return {"error": str(e)}


# ── Tool 9: Get Rankings ─────────────────────────────────────────────────────

def get_rankings(category: str = "top_performing") -> list[dict]:
    """Get marketplace strategy rankings.

    Use when the user asks about the best strategies, leaderboards,
    or top-performing strategies in a specific category.

    Categories: top_performing, most_stable, most_robust, most_efficient,
    most_validated, rising_stars
    """
    try:
        from src.engines.strategy_marketplace import StrategyMarketplace, MarketplaceRanking
        all_listings = StrategyMarketplace.search()
        return MarketplaceRanking.get_leaderboard(all_listings, category)
    except Exception as e:
        return [{"error": str(e)}]


# ── Tool 10: Compare Strategies ───────────────────────────────────────────────

def compare_strategies(strategy_configs: list[dict]) -> dict:
    """Compare multiple strategies side-by-side.

    Use when the user asks to compare strategies, wants to see
    differences, or needs to choose between options.
    """
    try:
        from src.engines.strategy_research.orchestrator import StrategyOrchestrator
        orch = StrategyOrchestrator()
        return orch.compare_strategies(strategy_configs, opportunities=[])
    except Exception as e:
        return {"error": str(e)}


# ── Tool Registry ────────────────────────────────────────────────────────────

TOOL_REGISTRY = {
    "list_signals": list_signals,
    "get_strategy": get_strategy,
    "search_strategies": search_strategies,
    "run_research": run_research,
    "get_scorecard": get_scorecard,
    "search_experiments": search_experiments,
    "query_graph": query_graph,
    "discover_patterns": discover_patterns,
    "get_rankings": get_rankings,
    "compare_strategies": compare_strategies,
}


def get_tool_descriptions() -> list[dict]:
    """Get tool descriptions for the LLM system prompt."""
    return [
        {"name": name, "description": fn.__doc__ or ""}
        for name, fn in TOOL_REGISTRY.items()
    ]
