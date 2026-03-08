"""
src/engines/knowledge_graph/hooks.py
─────────────────────────────────────────────────────────────────────────────
GraphHook — auto-registration helper for the Knowledge Graph.

Used by research engines to automatically register nodes and edges
when research artifacts are created.
"""

from __future__ import annotations

import logging

from .models import EdgeType, KnowledgeEdge, KnowledgeNode, NodeType
from .graph import ResearchKnowledgeGraph

logger = logging.getLogger("365advisers.knowledge_graph.hooks")


class GraphHook:
    """Auto-registration helper for the Knowledge Graph."""

    def __init__(self, graph: ResearchKnowledgeGraph):
        self.graph = graph

    def on_signal_created(self, signal_id: str, name: str, category: str = "", **metadata) -> str:
        """Register a signal node."""
        node_id = f"signal:{signal_id}"
        self.graph.add_node(KnowledgeNode(
            node_id=node_id,
            node_type=NodeType.SIGNAL,
            name=name,
            metadata={"category": category, **metadata},
        ))
        return node_id

    def on_strategy_created(
        self, strategy_id: str, name: str, signal_ids: list[str] | None = None, **metadata
    ) -> str:
        """Register a strategy node and signal→strategy edges."""
        node_id = f"strategy:{strategy_id}"
        self.graph.add_node(KnowledgeNode(
            node_id=node_id,
            node_type=NodeType.STRATEGY,
            name=name,
            metadata=metadata,
        ))

        if signal_ids:
            for sid in signal_ids:
                self.graph.add_edge(KnowledgeEdge(
                    source_id=f"signal:{sid}",
                    target_id=node_id,
                    edge_type=EdgeType.USED_BY,
                ))

        return node_id

    def on_experiment_created(
        self,
        experiment_id: str,
        name: str,
        experiment_type: str = "",
        strategy_id: str | None = None,
        parent_experiment_id: str | None = None,
        **metadata,
    ) -> str:
        """Register an experiment node and link edges."""
        node_id = f"experiment:{experiment_id}"
        self.graph.add_node(KnowledgeNode(
            node_id=node_id,
            node_type=NodeType.EXPERIMENT,
            name=name,
            metadata={"experiment_type": experiment_type, **metadata},
        ))

        if strategy_id:
            self.graph.add_edge(KnowledgeEdge(
                source_id=f"strategy:{strategy_id}",
                target_id=node_id,
                edge_type=EdgeType.EVALUATED_BY,
            ))

        if parent_experiment_id:
            self.graph.add_edge(KnowledgeEdge(
                source_id=f"experiment:{parent_experiment_id}",
                target_id=node_id,
                edge_type=EdgeType.LINEAGE,
            ))

        return node_id

    def on_portfolio_created(
        self,
        portfolio_id: str,
        name: str,
        strategy_ids: list[str] | None = None,
        **metadata,
    ) -> str:
        """Register a portfolio node and strategy→portfolio edges."""
        node_id = f"portfolio:{portfolio_id}"
        self.graph.add_node(KnowledgeNode(
            node_id=node_id,
            node_type=NodeType.PORTFOLIO,
            name=name,
            metadata=metadata,
        ))

        if strategy_ids:
            for sid in strategy_ids:
                self.graph.add_edge(KnowledgeEdge(
                    source_id=f"strategy:{sid}",
                    target_id=node_id,
                    edge_type=EdgeType.COMPOSED_INTO,
                ))

        return node_id
