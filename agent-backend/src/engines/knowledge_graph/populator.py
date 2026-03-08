"""
src/engines/knowledge_graph/populator.py
─────────────────────────────────────────────────────────────────────────────
GraphPopulator — hydrates the Knowledge Graph from existing registries.

Scans signals, strategies, experiments, and creates nodes + edges.
"""

from __future__ import annotations

import logging
from typing import Any

from .models import EdgeType, KnowledgeEdge, KnowledgeNode, NodeType
from .graph import ResearchKnowledgeGraph

logger = logging.getLogger("365advisers.knowledge_graph.populator")


class GraphPopulator:
    """Populate the Knowledge Graph from existing system registries."""

    @staticmethod
    def populate_from_signals(graph: ResearchKnowledgeGraph, signals: list[dict]) -> int:
        """Add signal nodes from signal registry data.

        Args:
            signals: List of signal dicts with at least {id, name, category}.

        Returns:
            Count of nodes added.
        """
        count = 0
        for sig in signals:
            node_id = f"signal:{sig.get('id', sig.get('signal_id', ''))}"
            graph.add_node(KnowledgeNode(
                node_id=node_id,
                node_type=NodeType.SIGNAL,
                name=sig.get("name", sig.get("id", "unnamed")),
                metadata={
                    "category": sig.get("category", ""),
                    "enabled": sig.get("enabled", True),
                    "source_module": "alpha_signals/registry",
                },
            ))
            count += 1

        logger.info("Populated %d signal nodes", count)
        return count

    @staticmethod
    def populate_from_strategies(
        graph: ResearchKnowledgeGraph,
        strategies: list[dict],
    ) -> int:
        """Add strategy nodes and signal→strategy edges.

        Args:
            strategies: List of strategy dicts with {id, name, config}.
        """
        count = 0
        for strat in strategies:
            strat_id = f"strategy:{strat.get('id', strat.get('strategy_id', ''))}"
            graph.add_node(KnowledgeNode(
                node_id=strat_id,
                node_type=NodeType.STRATEGY,
                name=strat.get("name", "unnamed"),
                metadata={
                    "lifecycle_state": strat.get("lifecycle_state", "research"),
                    "version": strat.get("version", "1.0.0"),
                    "source_module": "strategy/registry",
                },
            ))
            count += 1

            # Create signal → strategy edges
            config = strat.get("config", {})
            signals_config = config.get("signals", {})
            required_cats = signals_config.get("required_categories", [])
            for cat in required_cats:
                # Link by category — individual signal edges created by hooks
                graph.add_node(KnowledgeNode(
                    node_id=f"feature:{cat}",
                    node_type=NodeType.FEATURE,
                    name=f"{cat} features",
                    metadata={"category": cat},
                ))
                graph.add_edge(KnowledgeEdge(
                    source_id=f"feature:{cat}",
                    target_id=strat_id,
                    edge_type=EdgeType.USED_BY,
                    metadata={"auto": True},
                ))

        logger.info("Populated %d strategy nodes", count)
        return count

    @staticmethod
    def populate_from_experiments(
        graph: ResearchKnowledgeGraph,
        experiments: list[dict],
    ) -> int:
        """Add experiment nodes and strategy→experiment edges."""
        count = 0
        for exp in experiments:
            exp_id = f"experiment:{exp.get('experiment_id', '')}"
            graph.add_node(KnowledgeNode(
                node_id=exp_id,
                node_type=NodeType.EXPERIMENT,
                name=exp.get("name", "unnamed"),
                metadata={
                    "experiment_type": exp.get("experiment_type", ""),
                    "status": exp.get("status", "unknown"),
                    "author": exp.get("author", "system"),
                    "source_module": "experiment_tracking/tracker",
                },
            ))
            count += 1

            # Parent lineage edge
            parent = exp.get("parent_experiment_id")
            if parent:
                graph.add_edge(KnowledgeEdge(
                    source_id=f"experiment:{parent}",
                    target_id=exp_id,
                    edge_type=EdgeType.LINEAGE,
                ))

        logger.info("Populated %d experiment nodes", count)
        return count

    @staticmethod
    def populate_from_portfolio(
        graph: ResearchKnowledgeGraph,
        portfolio_result: dict,
    ) -> int:
        """Add portfolio node and strategy→portfolio edges."""
        pid = portfolio_result.get("portfolio_id", "")
        port_id = f"portfolio:{pid}"
        graph.add_node(KnowledgeNode(
            node_id=port_id,
            node_type=NodeType.PORTFOLIO,
            name=portfolio_result.get("portfolio_name", "unnamed"),
            metadata={
                "allocation_method": portfolio_result.get("allocation_method", ""),
                "strategy_count": portfolio_result.get("metrics", {}).get("strategy_count", 0),
                "source_module": "strategy_portfolio/engine",
            },
        ))

        # Add strategy → portfolio edges
        edge_count = 0
        for strat in portfolio_result.get("strategies", []):
            strat_name = strat.get("name", "")
            strat_id = f"strategy:{strat_name}"
            graph.add_edge(KnowledgeEdge(
                source_id=strat_id,
                target_id=port_id,
                edge_type=EdgeType.COMPOSED_INTO,
                weight=strat.get("weight", 0),
            ))
            edge_count += 1

        # Add correlation edges between strategies in the portfolio
        div = portfolio_result.get("diversification", {})
        corr_matrix = div.get("correlation_matrix", {})
        names = list(corr_matrix.keys())
        for i, na in enumerate(names):
            for j, nb in enumerate(names):
                if j <= i:
                    continue
                corr = corr_matrix.get(na, {}).get(nb, 0)
                if abs(corr) > 0.3:
                    graph.add_edge(KnowledgeEdge(
                        source_id=f"strategy:{na}",
                        target_id=f"strategy:{nb}",
                        edge_type=EdgeType.CORRELATED_WITH,
                        weight=round(corr, 4),
                    ))

        logger.info("Populated portfolio %s with %d strategy edges", pid, edge_count)
        return 1

    @staticmethod
    def populate_regimes(graph: ResearchKnowledgeGraph, regime_names: list[str]) -> int:
        """Add regime nodes."""
        for regime in regime_names:
            graph.add_node(KnowledgeNode(
                node_id=f"regime:{regime}",
                node_type=NodeType.REGIME,
                name=regime.replace("_", " ").title(),
                metadata={"regime_type": regime},
            ))
        return len(regime_names)
