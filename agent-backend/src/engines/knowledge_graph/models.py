"""
src/engines/knowledge_graph/models.py
─────────────────────────────────────────────────────────────────────────────
Research Knowledge Graph — data models for nodes and edges.

8 node types, 12 edge types, typed adjacency model.
"""

from __future__ import annotations

from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any


class NodeType(str, Enum):
    SIGNAL = "signal"
    FEATURE = "feature"
    STRATEGY = "strategy"
    PORTFOLIO = "portfolio"
    EXPERIMENT = "experiment"
    DATASET = "dataset"
    MODEL = "model"
    REGIME = "regime"


class EdgeType(str, Enum):
    DERIVED_FROM = "derived_from"          # Signal → Feature
    USED_BY = "used_by"                    # Signal → Strategy
    COMPOSED_INTO = "composed_into"        # Strategy → Portfolio
    EVALUATED_BY = "evaluated_by"          # Strategy → Experiment
    PRODUCED = "produced"                  # Experiment → Model
    DEPENDS_ON = "depends_on"              # Experiment → Dataset
    SUPERSEDES = "supersedes"              # Signal/Strategy → older version
    VALIDATED_BY = "validated_by"          # Strategy → walk-forward Exp
    CORRELATED_WITH = "correlated_with"    # Strategy ↔ Strategy
    OVERLAPS_WITH = "overlaps_with"        # Strategy ↔ Strategy (positions)
    ACTIVE_IN = "active_in"               # Strategy → Regime
    LINEAGE = "lineage"                    # Experiment → Experiment


class KnowledgeNode(BaseModel):
    """A node in the Research Knowledge Graph."""
    node_id: str                           # "signal:momentum_12m"
    node_type: NodeType
    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    created_at: str | None = None


class KnowledgeEdge(BaseModel):
    """A directed edge in the Research Knowledge Graph."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class GraphStats(BaseModel):
    """Summary statistics for the knowledge graph."""
    total_nodes: int = 0
    total_edges: int = 0
    nodes_by_type: dict[str, int] = Field(default_factory=dict)
    edges_by_type: dict[str, int] = Field(default_factory=dict)
