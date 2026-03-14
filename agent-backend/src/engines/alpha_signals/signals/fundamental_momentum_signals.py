"""
src/engines/alpha_signals/signals/fundamental_momentum_signals.py
──────────────────────────────────────────────────────────────────────────────
C6: Fundamental Momentum Signals — detect improving or deteriorating
fundamentals trends (not just static snapshots).

These signals fire when fundamentals are TRENDING in a direction,
adding a temporal dimension to the score.
"""

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    SignalCategory,
    SignalDirection,
)
from src.engines.alpha_signals.registry import registry


FUNDAMENTAL_MOMENTUM_SIGNALS = [
    # ── Positive fundamental momentum (bullish) ─────────────────────────
    AlphaSignalDefinition(
        id="fundmom.revenue_accelerating",
        name="Revenue Growth Accelerating",
        category=SignalCategory.GROWTH,
        description="Revenue growth rate increasing QoQ — business gaining momentum",
        feature_path="fundamental.revenue_acceleration",
        direction=SignalDirection.ABOVE,
        threshold=0.02,
        strong_threshold=0.10,
        weight=1.2,
        tags=["fundamental_momentum", "acceleration"],
    ),
    AlphaSignalDefinition(
        id="fundmom.margin_expanding",
        name="Margin Expansion",
        category=SignalCategory.QUALITY,
        description="Profit margins expanding — operational leverage improving",
        feature_path="fundamental.margin_trend",
        direction=SignalDirection.ABOVE,
        threshold=0.10,        # margin trend quality > 0.10 = meaningful expansion
        strong_threshold=0.50,  # strong expansion signal
        weight=1.1,
        tags=["fundamental_momentum", "margin"],
    ),

    # ── Negative fundamental momentum (bearish) ─────────────────────────
    AlphaSignalDefinition(
        id="fundmom.revenue_decelerating",
        name="Revenue Growth Decelerating",
        category=SignalCategory.GROWTH,
        description="Revenue growth rate declining — business losing momentum",
        feature_path="fundamental.revenue_acceleration",
        direction=SignalDirection.BELOW,
        threshold=-0.02,
        strong_threshold=-0.10,
        weight=1.1,
        tags=["fundamental_momentum", "deceleration", "risk"],
    ),
    AlphaSignalDefinition(
        id="fundmom.margin_compressing",
        name="Margin Compression",
        category=SignalCategory.QUALITY,
        description="Profit margins contracting — pricing power or cost pressure",
        feature_path="fundamental.margin_trend",
        direction=SignalDirection.BELOW,
        threshold=-0.10,       # margin trend quality < -0.10 = meaningful compression
        strong_threshold=-0.50, # strong compression signal
        weight=1.0,
        tags=["fundamental_momentum", "margin", "risk"],
    ),
]

# Auto-register
registry.register_many(FUNDAMENTAL_MOMENTUM_SIGNALS)
