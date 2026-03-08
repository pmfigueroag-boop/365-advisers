"""
src/engines/experiment_tracking/__init__.py
─────────────────────────────────────────────────────────────────────────────
Research Experiment Tracking System — register, version, compare, and
reproduce quantitative research experiments.
"""

from .models import (
    ResearchExperimentType,
    ResearchExperimentCreate,
    ResearchExperimentSummary,
    ReproductionResult,
    compute_data_fingerprint,
)
from .tracker import ResearchExperimentTracker
from .comparator import ExperimentComparator
from .reproducibility import ReproducibilityEngine
from .hooks import ExperimentHook

__all__ = [
    # Models
    "ResearchExperimentType",
    "ResearchExperimentCreate",
    "ResearchExperimentSummary",
    "ReproductionResult",
    "compute_data_fingerprint",
    # Core
    "ResearchExperimentTracker",
    "ExperimentComparator",
    "ReproducibilityEngine",
    "ExperimentHook",
]
