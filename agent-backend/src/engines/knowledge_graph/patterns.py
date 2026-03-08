"""
src/engines/knowledge_graph/patterns.py
─────────────────────────────────────────────────────────────────────────────
PatternDiscovery — detect research patterns in the Knowledge Graph.

Analyses: co-usage, hub detection, orphan detection, clustering,
lineage depth.
"""

from __future__ import annotations

import logging
from typing import Any

from .models import EdgeType, NodeType
from .graph import ResearchKnowledgeGraph

logger = logging.getLogger("365advisers.knowledge_graph.patterns")


class PatternDiscovery:
    """Discover research patterns in the Knowledge Graph."""

    @staticmethod
    def analyze(graph: ResearchKnowledgeGraph) -> dict:
        """Run all pattern analyses on the graph."""
        return {
            "co_usage": PatternDiscovery.signal_co_usage(graph),
            "hub_nodes": PatternDiscovery.hub_detection(graph),
            "orphan_nodes": PatternDiscovery.orphan_detection(graph),
            "clusters": PatternDiscovery.strategy_clusters(graph),
            "lineage_chains": PatternDiscovery.lineage_depth(graph),
        }

    @staticmethod
    def signal_co_usage(graph: ResearchKnowledgeGraph) -> list[dict]:
        """Find signals frequently used together in strategies."""
        # For each strategy, find its signal neighbors
        strategies = graph.get_nodes_by_type(NodeType.STRATEGY)
        strategy_signals: dict[str, set[str]] = {}

        for strat in strategies:
            neighbors = graph.neighbors(strat.node_id, direction="incoming")
            signals = {
                n["node_id"] for n in neighbors
                if n["type"] == "signal" or n["type"] == "feature"
            }
            if signals:
                strategy_signals[strat.node_id] = signals

        # Count signal pairs co-occurring across strategies
        pair_counts: dict[tuple[str, str], int] = {}
        for strat_id, signals in strategy_signals.items():
            signal_list = sorted(signals)
            for i in range(len(signal_list)):
                for j in range(i + 1, len(signal_list)):
                    pair = (signal_list[i], signal_list[j])
                    pair_counts[pair] = pair_counts.get(pair, 0) + 1

        co_usage = [
            {"signal_a": a, "signal_b": b, "shared_strategies": count}
            for (a, b), count in sorted(pair_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        return co_usage[:20]  # Top 20 pairs

    @staticmethod
    def hub_detection(graph: ResearchKnowledgeGraph, top_n: int = 10) -> list[dict]:
        """Find nodes with the most connections (highest degree centrality)."""
        degree: dict[str, int] = {}

        stats = graph.stats()
        for node_id in [n.node_id for n in graph._nodes.values()]:
            out = len(graph._outgoing.get(node_id, []))
            inc = len(graph._incoming.get(node_id, []))
            degree[node_id] = out + inc

        hubs = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:top_n]

        return [
            {
                "node_id": nid,
                "name": graph._nodes[nid].name if nid in graph._nodes else nid,
                "type": graph._nodes[nid].node_type.value if nid in graph._nodes else "unknown",
                "degree": deg,
                "outgoing": len(graph._outgoing.get(nid, [])),
                "incoming": len(graph._incoming.get(nid, [])),
            }
            for nid, deg in hubs if deg > 0
        ]

    @staticmethod
    def orphan_detection(graph: ResearchKnowledgeGraph) -> list[dict]:
        """Find nodes with zero connections."""
        orphans = []
        for node_id, node in graph._nodes.items():
            out = len(graph._outgoing.get(node_id, []))
            inc = len(graph._incoming.get(node_id, []))
            if out == 0 and inc == 0:
                orphans.append({
                    "node_id": node_id,
                    "name": node.name,
                    "type": node.node_type.value,
                    "created_at": node.created_at,
                })
        return orphans

    @staticmethod
    def strategy_clusters(graph: ResearchKnowledgeGraph) -> list[dict]:
        """Find clusters of closely related strategies via correlation edges."""
        strategies = graph.get_nodes_by_type(NodeType.STRATEGY)
        if not strategies:
            return []

        # Build adjacency for correlated strategies
        adj: dict[str, set[str]] = {s.node_id: set() for s in strategies}
        corr_edges = graph.get_edges(EdgeType.CORRELATED_WITH)
        for edge in corr_edges:
            if edge.source_id in adj:
                adj[edge.source_id].add(edge.target_id)
            if edge.target_id in adj:
                adj[edge.target_id].add(edge.source_id)

        # Simple connected components
        visited = set()
        clusters = []
        cluster_id = 0

        for node_id in adj:
            if node_id in visited:
                continue

            # BFS from this node
            component = set()
            queue = [node_id]
            while queue:
                current = queue.pop()
                if current in visited:
                    continue
                visited.add(current)
                component.add(current)
                for neighbor in adj.get(current, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)

            if len(component) >= 2:
                clusters.append({
                    "cluster_id": cluster_id,
                    "members": sorted(component),
                    "size": len(component),
                })
                cluster_id += 1

        return clusters

    @staticmethod
    def lineage_depth(graph: ResearchKnowledgeGraph) -> list[dict]:
        """Find the deepest lineage chains in the graph."""
        experiments = graph.get_nodes_by_type(NodeType.EXPERIMENT)
        chains = []

        for exp in experiments:
            ancestry = graph.ancestors(exp.node_id)
            if len(ancestry) >= 2:
                chains.append({
                    "root": ancestry[-1]["node_id"] if ancestry else exp.node_id,
                    "leaf": exp.node_id,
                    "depth": len(ancestry),
                    "chain": [a["node_id"] for a in ancestry],
                })

        chains.sort(key=lambda x: x["depth"], reverse=True)
        return chains[:10]
