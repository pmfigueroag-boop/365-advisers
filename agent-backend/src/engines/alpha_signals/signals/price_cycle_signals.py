"""
src/engines/alpha_signals/signals/price_cycle_signals.py
──────────────────────────────────────────────────────────────────────────────
C7: Price Cycle Positioning Signals — where is the stock in its
price cycle? Near highs (potential reversal) or at deep discounts
(potential entry)?

These signals help CASE consider not just the company quality but
the timing/entry point.
"""

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    SignalCategory,
    SignalDirection,
)
from src.engines.alpha_signals.registry import registry


PRICE_CYCLE_SIGNALS = [
    # ── Bullish price cycle (good entry points) ─────────────────────────
    AlphaSignalDefinition(
        id="pricecycle.deep_pullback",
        name="Deep Pullback from 52W High",
        category=SignalCategory.VALUE,
        description="Stock >20% below 52-week high — potential value entry if fundamentals intact",
        feature_path="technical.pct_from_52w_high",
        direction=SignalDirection.BELOW,
        threshold=-0.20,
        strong_threshold=-0.30,
        weight=1.0,
        tags=["price_cycle", "mean_reversion"],
    ),
    AlphaSignalDefinition(
        id="pricecycle.oversold_z",
        name="Mean Reversion Opportunity",
        category=SignalCategory.VALUE,
        description="Price >1.5 std deviations below 1-year average — statistical oversold",
        feature_path="technical.mean_reversion_z",
        direction=SignalDirection.BELOW,
        threshold=-1.5,
        strong_threshold=-2.0,
        weight=0.9,
        tags=["price_cycle", "mean_reversion", "statistical"],
    ),

    # ── Bearish price cycle (stretched entry) ───────────────────────────
    AlphaSignalDefinition(
        id="pricecycle.stretched_above_mean",
        name="Price Stretched Above Mean",
        category=SignalCategory.MOMENTUM,
        description="Price >2 std deviations above 1-year average — statistically overbought",
        feature_path="technical.mean_reversion_z",
        direction=SignalDirection.ABOVE,
        threshold=2.0,
        strong_threshold=2.5,
        weight=0.9,
        tags=["price_cycle", "overbought", "risk"],
    ),
    AlphaSignalDefinition(
        id="pricecycle.near_52w_high_risk",
        name="Near 52-Week High Risk",
        category=SignalCategory.VOLATILITY,
        description="Price within 3% of 52-week high — limited upside, elevated reversal risk",
        feature_path="technical.pct_from_52w_high",
        direction=SignalDirection.ABOVE,
        threshold=-0.03,
        strong_threshold=-0.01,
        weight=0.7,
        tags=["price_cycle", "risk"],
    ),
]

# Auto-register
registry.register_many(PRICE_CYCLE_SIGNALS)
