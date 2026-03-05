"""
src/engines/idea_generation/distributed/__init__.py
──────────────────────────────────────────────────────────────────────────────
Distributed Idea Generation — public API.
"""

from src.engines.idea_generation.distributed.dispatcher import ScanDispatcher
from src.engines.idea_generation.distributed.aggregator import ResultAggregator

__all__ = ["ScanDispatcher", "ResultAggregator"]
