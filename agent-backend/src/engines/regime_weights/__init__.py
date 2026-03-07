"""
src/engines/regime_weights/__init__.py
──────────────────────────────────────────────────────────────────────────────
Regime-Adaptive Signal Weighting module.
"""

from src.engines.regime_weights.engine import AdaptiveWeightEngine
from src.engines.regime_weights.evaluator import RegimePerformanceEvaluator
from src.engines.regime_weights.models import (
    AdaptiveWeightConfig,
    AdaptiveWeightReport,
    RegimeSignalStats,
    RegimeWeightProfile,
)

__all__ = [
    "AdaptiveWeightConfig",
    "AdaptiveWeightEngine",
    "AdaptiveWeightReport",
    "RegimePerformanceEvaluator",
    "RegimeSignalStats",
    "RegimeWeightProfile",
]
