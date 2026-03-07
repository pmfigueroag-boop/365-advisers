"""
src/engines/research_data/__init__.py
─────────────────────────────────────────────────────────────────────────────
Research Dataset Layer — versioned, reproducible datasets for quant research.
"""

from .models import (
    FeatureSnapshotRecord,
    SignalHistoryRecord,
    ResearchDatasetRecord,
    ResearchDatasetMemberRecord,
)
from .feature_store import FeatureStore
from .signal_store import SignalStore
from .dataset_builder import DatasetBuilder
from .snapshot import PointInTimeSnapshot

__all__ = [
    "FeatureSnapshotRecord",
    "SignalHistoryRecord",
    "ResearchDatasetRecord",
    "ResearchDatasetMemberRecord",
    "FeatureStore",
    "SignalStore",
    "DatasetBuilder",
    "PointInTimeSnapshot",
]
