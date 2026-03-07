"""
src/engines/online_learning/__init__.py
──────────────────────────────────────────────────────────────────────────────
Online Learning Engine module.
"""

from src.engines.online_learning.dampener import ChangeDampener
from src.engines.online_learning.engine import OnlineLearningEngine
from src.engines.online_learning.models import (
    LearningState,
    OnlineLearningConfig,
    OnlineLearningReport,
    SignalObservation,
    WeightUpdate,
)
from src.engines.online_learning.updater import EMAUpdater

__all__ = [
    "ChangeDampener",
    "EMAUpdater",
    "LearningState",
    "OnlineLearningConfig",
    "OnlineLearningEngine",
    "OnlineLearningReport",
    "SignalObservation",
    "WeightUpdate",
]
