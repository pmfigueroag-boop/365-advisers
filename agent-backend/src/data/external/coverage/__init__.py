"""
src/data/external/coverage/__init__.py
──────────────────────────────────────────────────────────────────────────────
Source Coverage Subsystem.

Tracks which data sources were used in each analysis, their freshness,
and computes a composite Analysis Completeness Score (0–100).
"""

from src.data.external.coverage.models import (
    SourceConfidence,
    SourceCoverageReport,
    SourceFreshness,
    SourceStatus,
)
from src.data.external.coverage.tracker import CoverageTracker
from src.data.external.coverage.scoring import AnalysisCompletenessScorer

__all__ = [
    "SourceConfidence",
    "SourceCoverageReport",
    "SourceFreshness",
    "SourceStatus",
    "CoverageTracker",
    "AnalysisCompletenessScorer",
]
