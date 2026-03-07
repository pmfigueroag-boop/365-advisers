"""
src/engines/signal_lab/__init__.py
─────────────────────────────────────────────────────────────────────────────
Signal Research Lab — systematic signal evaluation, comparison, and stability.
"""

from .evaluator import SignalEvaluator
from .comparator import SignalComparator
from .stability import StabilityAnalyzer
from .redundancy import RedundancyDetector
from .report import LabReport

__all__ = [
    "SignalEvaluator",
    "SignalComparator",
    "StabilityAnalyzer",
    "RedundancyDetector",
    "LabReport",
]
