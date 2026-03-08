"""
src/engines/knowledge_graph/__init__.py
─────────────────────────────────────────────────────────────────────────────
Research Knowledge Graph — connect all research elements.
"""

from .models import (
    NodeType,
    EdgeType,
    KnowledgeNode,
    KnowledgeEdge,
    GraphStats,
)
from .graph import ResearchKnowledgeGraph
from .populator import GraphPopulator
from .patterns import PatternDiscovery
from .hooks import GraphHook

__all__ = [
    # Models
    "NodeType",
    "EdgeType",
    "KnowledgeNode",
    "KnowledgeEdge",
    "GraphStats",
    # Core
    "ResearchKnowledgeGraph",
    "GraphPopulator",
    "PatternDiscovery",
    "GraphHook",
]
