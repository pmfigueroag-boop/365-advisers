"""
src/engines/concept_drift/__init__.py
──────────────────────────────────────────────────────────────────────────────
Concept Drift Detection Engine module.
"""

from src.engines.concept_drift.aggregator import DriftAggregator
from src.engines.concept_drift.detectors import (
    CorrelationBreakdownDetector,
    DistributionShiftDetector,
    RegimeShiftDetector,
)
from src.engines.concept_drift.engine import ConceptDriftEngine
from src.engines.concept_drift.models import (
    ConceptDriftReport,
    DetectorType,
    DriftAlert,
    DriftConfig,
    DriftDetection,
    DriftSeverity,
)

__all__ = [
    "ConceptDriftEngine",
    "ConceptDriftReport",
    "CorrelationBreakdownDetector",
    "DetectorType",
    "DistributionShiftDetector",
    "DriftAggregator",
    "DriftAlert",
    "DriftConfig",
    "DriftDetection",
    "DriftSeverity",
    "RegimeShiftDetector",
]
