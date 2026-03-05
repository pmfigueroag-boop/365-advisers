"""
src/engines/alpha_signals/signals/macro_signals.py
──────────────────────────────────────────────────────────────────────────────
Macro Context Signals — regime-level signals derived from cross-asset
and macro-economic indicators that act as confidence modifiers for
all other signal categories.

These signals do not generate opportunities directly; instead they
adjust thresholds and weights across the signal pipeline.
"""

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    SignalCategory,
    SignalDirection,
)
from src.engines.alpha_signals.registry import registry


MACRO_SIGNALS = [
    AlphaSignalDefinition(
        id="macro.yield_curve_steep",
        name="Yield Curve Regime",
        category=SignalCategory.MACRO,
        description="Positive 10Y-2Y spread signals expansionary regime — favors growth/momentum; inverted signals recession risk",
        feature_path="macro.yield_curve_spread",
        direction=SignalDirection.ABOVE,
        threshold=0.0,
        strong_threshold=1.5,
        weight=1.0,
        tags=["regime", "interest_rates", "recession_predictor"],
    ),
    AlphaSignalDefinition(
        id="macro.credit_spread_benign",
        name="Credit Spread Stress",
        category=SignalCategory.MACRO,
        description="HY OAS z-score below 1 signals benign credit conditions — risk-on amplifier (Bridgewater framework)",
        feature_path="macro.hy_oas_zscore",
        direction=SignalDirection.BELOW,
        threshold=1.0,
        strong_threshold=-1.0,
        weight=1.0,
        tags=["credit_stress", "systemic_risk"],
    ),
    AlphaSignalDefinition(
        id="macro.cross_asset_risk_on",
        name="Cross-Asset Risk Appetite",
        category=SignalCategory.MACRO,
        description="Average 20d momentum of SPX, HY, commodities, USD-inv — positive signals broad risk-on environment (Man AHL)",
        feature_path="macro.risk_appetite",
        direction=SignalDirection.ABOVE,
        threshold=0.0,
        strong_threshold=0.03,
        weight=0.9,
        tags=["cross_asset", "regime", "risk_appetite"],
    ),
]

# Auto-register
registry.register_many(MACRO_SIGNALS)
