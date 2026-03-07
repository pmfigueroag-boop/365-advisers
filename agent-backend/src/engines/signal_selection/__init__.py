"""
src/engines/signal_selection/__init__.py
──────────────────────────────────────────────────────────────────────────────
Signal Selection & Redundancy Pruning Engine.
"""

from src.engines.signal_selection.correlation import CorrelationAnalyzer
from src.engines.signal_selection.engine import RedundancyPruningEngine
from src.engines.signal_selection.incremental import IncrementalAlphaAnalyzer
from src.engines.signal_selection.models import (
    RedundancyClass,
    RedundancyConfig,
    RedundancyReport,
    SignalPairAnalysis,
    SignalRedundancyProfile,
)
from src.engines.signal_selection.mutual_info import MutualInfoEstimator

__all__ = [
    "CorrelationAnalyzer",
    "IncrementalAlphaAnalyzer",
    "MutualInfoEstimator",
    "RedundancyClass",
    "RedundancyConfig",
    "RedundancyPruningEngine",
    "RedundancyReport",
    "SignalPairAnalysis",
    "SignalRedundancyProfile",
]
