"""
src/engines/alpha_decay/__init__.py
──────────────────────────────────────────────────────────────────────────────
Alpha Decay & Signal Half-Life Model — measures how long an investment
signal maintains its predictive power before losing relevance.

Sits between the Alpha Signals Library and the Composite Alpha Score Engine.

Public API:
    from src.engines.alpha_decay import DecayEngine, ActivationTracker
"""

from src.engines.alpha_decay.models import (  # noqa: F401
    DecayConfig,
    DecayFunctionType,
    FreshnessLevel,
    SignalActivation,
    DecayAdjustedSignal,
    CategoryDecaySummary,
    DecayAdjustedProfile,
    DEFAULT_HALF_LIFE_DAYS,
)
from src.engines.alpha_decay.engine import DecayEngine      # noqa: F401
from src.engines.alpha_decay.tracker import ActivationTracker  # noqa: F401
