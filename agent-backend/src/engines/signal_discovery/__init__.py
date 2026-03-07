"""
src/engines/signal_discovery/__init__.py
──────────────────────────────────────────────────────────────────────────────
Signal Discovery Engine module.
"""

from src.engines.signal_discovery.engine import SignalDiscoveryEngine
from src.engines.signal_discovery.evaluator import CandidateEvaluator
from src.engines.signal_discovery.generator import FeatureGenerator
from src.engines.signal_discovery.models import (
    CandidateSignal,
    CandidateStatus,
    CandidateType,
    DiscoveryConfig,
    DiscoveryReport,
)

__all__ = [
    "CandidateEvaluator",
    "CandidateSignal",
    "CandidateStatus",
    "CandidateType",
    "DiscoveryConfig",
    "DiscoveryReport",
    "FeatureGenerator",
    "SignalDiscoveryEngine",
]
