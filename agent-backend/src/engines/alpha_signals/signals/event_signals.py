"""
src/engines/alpha_signals/signals/event_signals.py
──────────────────────────────────────────────────────────────────────────────
Event Alpha Signals — detect corporate events and catalysts that may
precede significant price movements.
"""

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    SignalCategory,
    SignalDirection,
)
from src.engines.alpha_signals.registry import registry


EVENT_SIGNALS = [
    AlphaSignalDefinition(
        id="event.earnings_surprise",
        name="Earnings Surprise",
        category=SignalCategory.EVENT,
        description="YoY earnings growth above threshold suggests positive fundamental surprise",
        feature_path="fundamental.earnings_growth_yoy",
        direction=SignalDirection.ABOVE,
        threshold=0.20,
        strong_threshold=0.40,
        weight=1.2,
        tags=["earnings", "catalyst"],
    ),
    AlphaSignalDefinition(
        id="event.revenue_acceleration",
        name="Revenue Acceleration",
        category=SignalCategory.EVENT,
        description="Strong YoY revenue growth signals business momentum",
        feature_path="fundamental.revenue_growth_yoy",
        direction=SignalDirection.ABOVE,
        threshold=0.10,
        strong_threshold=0.25,
        weight=1.0,
        tags=["growth", "top_line"],
    ),
    AlphaSignalDefinition(
        id="event.volatility_squeeze",
        name="Volatility Squeeze (Event Setup)",
        category=SignalCategory.EVENT,
        description="Extremely narrow BB width preceding an event may amplify price reaction",
        feature_path="technical.bb_upper",
        direction=SignalDirection.BELOW,
        threshold=0.0,  # dynamically: (bb_upper - bb_lower) / bb_basis < 0.04
        weight=0.9,
        tags=["pre_event", "setup"],
    ),
    AlphaSignalDefinition(
        id="event.high_beta_sector",
        name="High Beta Sector Exposure",
        category=SignalCategory.EVENT,
        description="High beta increases sensitivity to market and sector catalysts",
        feature_path="fundamental.beta",
        direction=SignalDirection.ABOVE,
        threshold=1.5,
        strong_threshold=2.0,
        weight=0.7,
        tags=["beta", "sensitivity"],
    ),
]

# Auto-register
registry.register_many(EVENT_SIGNALS)
