"""
src/engines/alpha_signals/__init__.py
──────────────────────────────────────────────────────────────────────────────
Alpha Signals Library — structured catalog of quantitative signals that
feed the Idea Generation Engine.

Importing this package auto-registers all signal definitions.
"""

# Import sub-packages to trigger auto-registration
from src.engines.alpha_signals import signals  # noqa: F401

# Public API
from src.engines.alpha_signals.models import (   # noqa: F401
    SignalCategory,
    SignalDirection,
    SignalStrength,
    ConfidenceLevel,
    AlphaSignalDefinition,
    EvaluatedSignal,
    CategoryScore,
    SignalProfile,
    CompositeScore,
)
from src.engines.alpha_signals.registry import registry       # noqa: F401
from src.engines.alpha_signals.evaluator import SignalEvaluator  # noqa: F401
from src.engines.alpha_signals.combiner import SignalCombiner    # noqa: F401
