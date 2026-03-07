"""
src/engines/walk_forward/__init__.py
──────────────────────────────────────────────────────────────────────────────
Walk-Forward Validation Engine — prevents overfitting by separating
in-sample calibration from out-of-sample validation across temporal folds.
"""

from src.engines.walk_forward.engine import WalkForwardEngine
from src.engines.walk_forward.models import (
    WalkForwardConfig,
    WalkForwardFold,
    WalkForwardMode,
    WalkForwardRun,
    WFSignalFoldResult,
    WFSignalSummary,
    StabilityClassification,
)

__all__ = [
    "WalkForwardEngine",
    "WalkForwardConfig",
    "WalkForwardFold",
    "WalkForwardMode",
    "WalkForwardRun",
    "WFSignalFoldResult",
    "WFSignalSummary",
    "StabilityClassification",
]
