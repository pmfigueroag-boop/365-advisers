"""
src/engines/alpha_signals/signals/momentum_signals.py
──────────────────────────────────────────────────────────────────────────────
Momentum Alpha Signals — detect strong upward price trends using
technical indicators like moving averages, RSI, and MACD.
"""

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    SignalCategory,
    SignalDirection,
)
from src.engines.alpha_signals.registry import registry


MOMENTUM_SIGNALS = [
    AlphaSignalDefinition(
        id="momentum.golden_cross",
        name="Moving Average Crossover (Golden Cross)",
        category=SignalCategory.MOMENTUM,
        description="SMA50 above SMA200 indicates a bullish structural trend",
        feature_path="technical.sma_50_200_spread",
        direction=SignalDirection.ABOVE,
        threshold=0.0,      # fires when SMA50/SMA200 spread is positive
        strong_threshold=0.05,  # strong when SMA50 is 5%+ above SMA200
        weight=1.3,
        tags=["trend", "crossover"],
    ),
    AlphaSignalDefinition(
        id="momentum.price_above_ema20",
        name="Strong Price Trend",
        category=SignalCategory.MOMENTUM,
        description="Price above rolling mean confirms bullish positioning",
        feature_path="technical.mean_reversion_z",
        direction=SignalDirection.ABOVE,
        threshold=0.0,        # fires when price is above its 1yr rolling mean
        strong_threshold=1.0, # strong when price is 1 std above mean
        weight=1.0,
        tags=["price_action", "trend"],
    ),
    AlphaSignalDefinition(
        id="momentum.rsi_bullish",
        name="Positive RSI",
        category=SignalCategory.MOMENTUM,
        description="RSI in the 50–70 range signals healthy bullish momentum",
        feature_path="technical.rsi",
        direction=SignalDirection.BETWEEN,
        threshold=50.0,
        upper_threshold=70.0,
        weight=1.0,
        tags=["momentum", "oscillator"],
    ),
    AlphaSignalDefinition(
        id="momentum.macd_bullish",
        name="MACD Bullish Signal",
        category=SignalCategory.MOMENTUM,
        description="Positive MACD histogram indicates accelerating upward momentum",
        feature_path="technical.macd_hist",
        direction=SignalDirection.ABOVE,
        threshold=0.0,
        strong_threshold=0.5,
        weight=1.1,
        tags=["momentum", "macd"],
    ),
    AlphaSignalDefinition(
        id="momentum.volume_surge",
        name="Volume Surge",
        category=SignalCategory.MOMENTUM,
        description="Volume z-score above 1.5 standard deviations confirms trend conviction",
        feature_path="technical.volume_surprise",
        direction=SignalDirection.ABOVE,
        threshold=1.5,         # fires at 1.5 sigma above 20-day average
        strong_threshold=2.5,  # strong at 2.5 sigma
        weight=0.8,
        tags=["volume", "confirmation"],
    ),
    # ── M06–M08: Expanded institutional momentum signals ──────────
    AlphaSignalDefinition(
        id="momentum.high_52w_proximity",
        name="52-Week High Proximity",
        category=SignalCategory.MOMENTUM,
        description="Price within 5% of 52-week high signals strong momentum continuation (George-Hwang 2004)",
        feature_path="technical.pct_from_52w_high",
        direction=SignalDirection.ABOVE,
        threshold=-0.05,
        strong_threshold=-0.03,
        weight=1.0,
        tags=["proximity", "anchoring_bias"],
    ),
    AlphaSignalDefinition(
        id="momentum.relative_strength_sector",
        name="Relative Strength vs Sector",
        category=SignalCategory.MOMENTUM,
        description="Stock outperforming its sector isolates alpha momentum from beta rotation (O'Shaughnessy)",
        feature_path="technical.relative_sector_strength",
        direction=SignalDirection.ABOVE,
        threshold=0.05,
        strong_threshold=0.15,
        weight=1.1,
        tags=["relative_strength", "alpha_isolation"],
    ),
    AlphaSignalDefinition(
        id="momentum.adx_trend_strength",
        name="ADX Trend Strength",
        category=SignalCategory.MOMENTUM,
        description="ADX above 25 confirms a strong directional trend; avoids whipsaw in trendless markets (CTA filter)",
        feature_path="technical.adx",
        direction=SignalDirection.ABOVE,
        threshold=25.0,
        strong_threshold=35.0,
        weight=0.9,
        tags=["trend_strength", "directional"],
    ),
]

# Auto-register
registry.register_many(MOMENTUM_SIGNALS)
