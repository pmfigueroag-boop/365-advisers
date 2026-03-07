"""
src/engines/signal_ensemble/__init__.py
──────────────────────────────────────────────────────────────────────────────
Signal Ensemble Intelligence module.
"""

from src.engines.signal_ensemble.co_fire import CoFireAnalyzer
from src.engines.signal_ensemble.engine import EnsembleIntelligenceEngine
from src.engines.signal_ensemble.models import (
    CoFireEvent,
    EnsembleConfig,
    EnsembleReport,
    SignalCombination,
)
from src.engines.signal_ensemble.stability import StabilityAnalyzer
from src.engines.signal_ensemble.synergy import SynergyScorer

__all__ = [
    "CoFireAnalyzer",
    "CoFireEvent",
    "EnsembleConfig",
    "EnsembleIntelligenceEngine",
    "EnsembleReport",
    "SignalCombination",
    "StabilityAnalyzer",
    "SynergyScorer",
]
