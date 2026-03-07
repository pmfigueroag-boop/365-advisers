"""
src/engines/meta_learning/__init__.py
──────────────────────────────────────────────────────────────────────────────
Meta-Learning Engine module.
"""

from src.engines.meta_learning.analyzer import MetaAnalyzer
from src.engines.meta_learning.collectors import (
    DetectorCollector,
    RegimeCollector,
    SignalCollector,
)
from src.engines.meta_learning.engine import MetaLearningEngine
from src.engines.meta_learning.models import (
    DetectorHealthSnapshot,
    MetaLearningConfig,
    MetaLearningReport,
    MetaRecommendation,
    RecommendationType,
    SignalHealthSnapshot,
    TrendDirection,
)
from src.engines.meta_learning.recommender import MetaRecommender

__all__ = [
    "DetectorCollector",
    "DetectorHealthSnapshot",
    "MetaAnalyzer",
    "MetaLearningConfig",
    "MetaLearningEngine",
    "MetaLearningReport",
    "MetaRecommendation",
    "MetaRecommender",
    "RecommendationType",
    "RegimeCollector",
    "SignalCollector",
    "SignalHealthSnapshot",
    "TrendDirection",
]
