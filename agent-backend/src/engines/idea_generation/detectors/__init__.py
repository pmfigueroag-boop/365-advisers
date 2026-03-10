"""
Opportunity Detectors — modular scanners for value, quality,
momentum, reversal, growth, and event-driven signals.
"""
from src.engines.idea_generation.detectors.value_detector import ValueDetector
from src.engines.idea_generation.detectors.quality_detector import QualityDetector
from src.engines.idea_generation.detectors.momentum_detector import MomentumDetector
from src.engines.idea_generation.detectors.reversal_detector import ReversalDetector
from src.engines.idea_generation.detectors.growth_detector import GrowthDetector
from src.engines.idea_generation.detectors.event_detector import EventDetector

__all__ = [
    "ValueDetector",
    "QualityDetector",
    "MomentumDetector",
    "ReversalDetector",
    "GrowthDetector",
    "EventDetector",
]
