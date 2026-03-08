"""
src/engines/knowledge_graph/graph.py
─────────────────────────────────────────────────────────────────────────────
ResearchKnowledgeGraph — in-memory graph engine with adjacency list.

Graph operations:
  - add/remove nodes and edges
  - neighbors, path (BFS), subgraph, ancestors, descendants
  - impact analysis (downstream count)
  - stats
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

from .models import (
    EdgeType,
    GraphStats,
    KnowledgeEdge,
    KnowledgeNode,
    NodeType,
)

logger = logging.getLogger("365advisers.knowledge_graph.graph")


class ResearchKnowledgeGraph:
    """In-memory research knowledge graph with adjacency list storage."""

    def __init__(self):
        self._nodes: dict[str, KnowledgeNode] = {}
        # Adjacency lists: node_id → list of edges
        self._outgoing: dict[str, list[KnowledgeEdge]] = {}  # source → [edges]
        self._incoming: dict[str, list[KnowledgeEdge]] = {}  # target → [edges]

    # ── Node Operations ───────────────────────────────────────────────────

    def add_node(self, node: KnowledgeNode) -> None:
        """Add a node to the graph. Updates if exists."""
        if not node.created_at:
            node.created_at = datetime.now(timezone.utc).isoformat()
        self._nodes[node.node_id] = node
        self._outgoing.setdefault(node.node_id, [])
        self._incoming.setdefault(node.node_id, [])

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and all its edges."""
        if node_id not in self._nodes:
            return False

        # Remove edges
        out_edges = list(self._outgoing.get(node_id, []))
        for edge in out_edges:
            self._incoming.get(edge.target_id, [])
            self._incoming[edge.target_id] = [
                e for e in self._incoming.get(edge.target_id, [])
                if e.source_id != node_id
            ]

        in_edges = list(self._incoming.get(node_id, []))
        for edge in in_edges:
            self._outgoing[edge.source_id] = [
                e for e in self._outgoing.get(edge.source_id, [])
                if e.target_id != node_id
            ]

        del self._nodes[node_id]
        self._outgoing.pop(node_id, None)
        self._incoming.pop(node_id, None)
        return True

    def get_node(self, node_id: str) -> KnowledgeNode | None:
        return self._nodes.get(node_id)

    def get_nodes_by_type(self, node_type: NodeType) -> list[KnowledgeNode]:
        return [n for n in self._nodes.values() if n.node_type == node_type]

    # ── Edge Operations ───────────────────────────────────────────────────

    def add_edge(self, edge: KnowledgeEdge) -> None:
        """Add a directed edge. No duplicate (source, target, type)."""
        if not edge.created_at:
            edge.created_at = datetime.now(timezone.utc).isoformat()

        # Ensure nodes exist
        self._outgoing.setdefault(edge.source_id, [])
        self._incoming.setdefault(edge.target_id, [])

        # Check for duplicate
        for existing in self._outgoing.get(edge.source_id, []):
            if existing.target_id == edge.target_id and existing.edge_type == edge.edge_type:
                existing.weight = edge.weight  # Update weight
                return

        self._outgoing[edge.source_id].append(edge)
        self._incoming[edge.target_id].append(edge)

    def remove_edge(self, source_id: str, target_id: str, edge_type: EdgeType) -> bool:
        """Remove a specific edge."""
        removed = False
        if source_id in self._outgoing:
            before = len(self._outgoing[source_id])
            self._outgoing[source_id] = [
                e for e in self._outgoing[source_id]
                if not (e.target_id == target_id and e.edge_type == edge_type)
            ]
            removed = len(self._outgoing[source_id]) < before

        if target_id in self._incoming:
            self._incoming[target_id] = [
                e for e in self._incoming[target_id]
                if not (e.source_id == source_id and e.edge_type == edge_type)
            ]

        return removed

    def get_edges(self, edge_type: EdgeType | None = None) -> list[KnowledgeEdge]:
        """Get all edges, optionally filtered by type."""
        all_edges = []
        for edges in self._outgoing.values():
            for e in edges:
                if edge_type is None or e.edge_type == edge_type:
                    all_edges.append(e)
        return all_edges

    # ── Graph Queries ─────────────────────────────────────────────────────

    def neighbors(
        self,
        node_id: str,
        direction: str = "both",
        edge_type: EdgeType | None = None,
    ) -> list[dict]:
        """Get direct neighbors of a node.

        Args:
            direction: "outgoing", "incoming", or "both"
            edge_type: Optionally filter by edge type
        """
        results = []

        if direction in ("outgoing", "both"):
            for edge in self._outgoing.get(node_id, []):
                if edge_type and edge.edge_type != edge_type:
                    continue
                node = self._nodes.get(edge.target_id)
                results.append({
                    "node_id": edge.target_id,
                    "name": node.name if node else edge.target_id,
                    "type": node.node_type.value if node else "unknown",
                    "edge_type": edge.edge_type.value,
                    "direction": "outgoing",
                    "weight": edge.weight,
                })

        if direction in ("incoming", "both"):
            for edge in self._incoming.get(node_id, []):
                if edge_type and edge.edge_type != edge_type:
                    continue
                node = self._nodes.get(edge.source_id)
                results.append({
                    "node_id": edge.source_id,
                    "name": node.name if node else edge.source_id,
                    "type": node.node_type.value if node else "unknown",
                    "edge_type": edge.edge_type.value,
                    "direction": "incoming",
                    "weight": edge.weight,
                })

        return results

    def path(self, from_id: str, to_id: str, max_depth: int = 10) -> list[str] | None:
        """Find shortest path between two nodes (BFS)."""
        if from_id not in self._nodes or to_id not in self._nodes:
            return None

        visited = {from_id}
        queue: deque[list[str]] = deque([[from_id]])

        while queue:
            current_path = queue.popleft()
            current = current_path[-1]

            if current == to_id:
                return current_path

            if len(current_path) > max_depth:
                continue

            # Explore outgoing
            for edge in self._outgoing.get(current, []):
                if edge.target_id not in visited:
                    visited.add(edge.target_id)
                    queue.append(current_path + [edge.target_id])

            # Explore incoming (bidirectional)
            for edge in self._incoming.get(current, []):
                if edge.source_id not in visited:
                    visited.add(edge.source_id)
                    queue.append(current_path + [edge.source_id])

        return None

    def subgraph(self, node_id: str, depth: int = 2) -> dict:
        """Get the N-hop neighborhood subgraph."""
        visited_nodes: set[str] = set()
        visited_edges: list[dict] = []
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])

        while queue:
            current, d = queue.popleft()
            if current in visited_nodes:
                continue
            visited_nodes.add(current)

            if d >= depth:
                continue

            # Outgoing
            for edge in self._outgoing.get(current, []):
                visited_edges.append({
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "type": edge.edge_type.value,
                    "weight": edge.weight,
                })
                if edge.target_id not in visited_nodes:
                    queue.append((edge.target_id, d + 1))

            # Incoming
            for edge in self._incoming.get(current, []):
                visited_edges.append({
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "type": edge.edge_type.value,
                    "weight": edge.weight,
                })
                if edge.source_id not in visited_nodes:
                    queue.append((edge.source_id, d + 1))

        nodes = [
            {"node_id": nid, "name": self._nodes[nid].name,
             "type": self._nodes[nid].node_type.value}
            for nid in visited_nodes if nid in self._nodes
        ]

        # Deduplicate edges
        seen_edges = set()
        unique_edges = []
        for e in visited_edges:
            key = (e["source"], e["target"], e["type"])
            if key not in seen_edges:
                seen_edges.add(key)
                unique_edges.append(e)

        return {
            "center": node_id,
            "depth": depth,
            "nodes": nodes,
            "edges": unique_edges,
            "node_count": len(nodes),
            "edge_count": len(unique_edges),
        }

    def ancestors(self, node_id: str, max_depth: int = 10) -> list[dict]:
        """Walk upstream (incoming edges only)."""
        visited = set()
        result = []
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])

        while queue:
            current, d = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            node = self._nodes.get(current)
            if node:
                result.append({
                    "node_id": current,
                    "name": node.name,
                    "type": node.node_type.value,
                    "depth": d,
                })

            if d >= max_depth:
                continue

            for edge in self._incoming.get(current, []):
                if edge.source_id not in visited:
                    queue.append((edge.source_id, d + 1))

        return result

    def descendants(self, node_id: str, max_depth: int = 10) -> list[dict]:
        """Walk downstream (outgoing edges only)."""
        visited = set()
        result = []
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])

        while queue:
            current, d = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            node = self._nodes.get(current)
            if node:
                result.append({
                    "node_id": current,
                    "name": node.name,
                    "type": node.node_type.value,
                    "depth": d,
                })

            if d >= max_depth:
                continue

            for edge in self._outgoing.get(current, []):
                if edge.target_id not in visited:
                    queue.append((edge.target_id, d + 1))

        return result

    def impact_analysis(self, node_id: str) -> dict:
        """Analyze downstream impact of changing a node."""
        desc = self.descendants(node_id)
        # Remove self
        desc = [d for d in desc if d["node_id"] != node_id]

        by_type: dict[str, int] = {}
        for d in desc:
            by_type[d["type"]] = by_type.get(d["type"], 0) + 1

        return {
            "node_id": node_id,
            "total_affected": len(desc),
            "affected_by_type": by_type,
            "affected_nodes": desc,
            "severity": "high" if len(desc) > 10 else ("medium" if len(desc) > 3 else "low"),
        }

    # ── Stats ─────────────────────────────────────────────────────────────

    def stats(self) -> GraphStats:
        nodes_by_type: dict[str, int] = {}
        for n in self._nodes.values():
            nodes_by_type[n.node_type.value] = nodes_by_type.get(n.node_type.value, 0) + 1

        edges_by_type: dict[str, int] = {}
        total_edges = 0
        for edges in self._outgoing.values():
            for e in edges:
                edges_by_type[e.edge_type.value] = edges_by_type.get(e.edge_type.value, 0) + 1
                total_edges += 1

        return GraphStats(
            total_nodes=len(self._nodes),
            total_edges=total_edges,
            nodes_by_type=nodes_by_type,
            edges_by_type=edges_by_type,
        )

    def clear(self):
        """Clear the entire graph."""
        self._nodes.clear()
        self._outgoing.clear()
        self._incoming.clear()
