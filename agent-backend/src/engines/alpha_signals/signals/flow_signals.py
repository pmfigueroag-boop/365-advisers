"""
src/engines/alpha_signals/signals/flow_signals.py
──────────────────────────────────────────────────────────────────────────────
Flow Alpha Signals — detect institutional activity patterns, unusual
volume, and accumulation/distribution behavior.
"""

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    SignalCategory,
    SignalDirection,
)
from src.engines.alpha_signals.registry import registry


FLOW_SIGNALS = [
    AlphaSignalDefinition(
        id="flow.unusual_volume",
        name="Unusual Volume",
        category=SignalCategory.FLOW,
        description="Volume significantly above 20-day average suggests institutional activity",
        feature_path="technical.volume",
        direction=SignalDirection.ABOVE,
        threshold=0.0,  # compared against volume_avg_20 * 1.5 dynamically
        strong_threshold=0.0,  # compared against volume_avg_20 * 2.0
        weight=1.1,
        tags=["institutional_flow", "volume_anomaly"],
    ),
    AlphaSignalDefinition(
        id="flow.accumulation_pattern",
        name="Accumulation Patterns",
        category=SignalCategory.FLOW,
        description="Rising OBV alongside flat/rising price suggests institutional accumulation",
        feature_path="technical.obv",
        direction=SignalDirection.ABOVE,
        threshold=0.0,
        weight=1.0,
        tags=["accumulation", "smart_money"],
    ),
    AlphaSignalDefinition(
        id="flow.volume_price_divergence",
        name="Volume-Price Divergence",
        category=SignalCategory.FLOW,
        description="Volume trend diverging from price trend may signal upcoming reversal",
        feature_path="technical.volume",
        direction=SignalDirection.ABOVE,
        threshold=0.0,
        weight=0.9,
        tags=["divergence", "institutional_positioning"],
    ),
    # ── F04–F05: Expanded institutional flow signals ──────────────
    AlphaSignalDefinition(
        id="flow.mfi_oversold",
        name="MFI Capitulation Signal",
        category=SignalCategory.FLOW,
        description="Money Flow Index below 20 indicates volume-weighted oversold capitulation — potential bottom",
        feature_path="technical.mfi",
        direction=SignalDirection.BELOW,
        threshold=25.0,
        strong_threshold=15.0,
        weight=1.0,
        tags=["capitulation", "volume_weighted_rsi"],
    ),
    AlphaSignalDefinition(
        id="flow.dark_pool_absorption",
        name="Dark Pool Absorption",
        category=SignalCategory.FLOW,
        description="High volume with unusually low price movement (Wyckoff effort vs result) suggests institutional block trading",
        feature_path="technical.effort_result_ratio",
        direction=SignalDirection.ABOVE,
        threshold=2.0,
        strong_threshold=4.0,
        weight=1.0,
        tags=["dark_pool", "wyckoff", "block_trading"],
    ),
]

# Auto-register
registry.register_many(FLOW_SIGNALS)
