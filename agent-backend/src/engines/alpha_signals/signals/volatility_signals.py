"""
src/engines/alpha_signals/signals/volatility_signals.py
──────────────────────────────────────────────────────────────────────────────
Volatility Alpha Signals — detect compression, expansion, and breakout
conditions in price volatility that may precede significant moves.
"""

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    SignalCategory,
    SignalDirection,
)
from src.engines.alpha_signals.registry import registry


VOLATILITY_SIGNALS = [
    AlphaSignalDefinition(
        id="volatility.bb_compression",
        name="Volatility Compression",
        category=SignalCategory.VOLATILITY,
        description="Narrow Bollinger Band width indicates a volatility squeeze preceding a breakout",
        feature_path="technical.bb_width",
        direction=SignalDirection.BELOW,
        threshold=0.04,  # P1.2 fix: bb_width < 4% = compression
        weight=1.2,
        tags=["squeeze", "breakout_setup"],
    ),
    AlphaSignalDefinition(
        id="volatility.atr_expansion",
        name="ATR Expansion",
        category=SignalCategory.VOLATILITY,
        description="Rising Average True Range signals increasing price volatility and potential moves",
        feature_path="technical.atr",
        direction=SignalDirection.ABOVE,
        threshold=0.0,
        strong_threshold=0.0,
        weight=0.9,
        enabled=False,  # AVS: DISABLED — ATR always > 0 → fire=100%, IC=0.0
        tags=["range_expansion", "momentum_confirmation"],
    ),
    AlphaSignalDefinition(
        id="volatility.bb_lower_proximity",
        name="Bollinger Lower Band Proximity",
        category=SignalCategory.VOLATILITY,
        description="Price near lower Bollinger Band may indicate oversold conditions. Fires when bb_width is high (>6%) AND price is below the 20-day SMA (negative z-score via rsi_14 < 35).",
        feature_path="technical.rsi_14",
        direction=SignalDirection.BELOW,
        threshold=35.0,  # P1.2 fix: RSI < 35 = price near BB lower (proxy)
        weight=1.0,
        tags=["mean_reversion", "oversold"],
    ),
    # ── VL04–VL05: Expanded institutional volatility signals ──────
    AlphaSignalDefinition(
        id="volatility.vix_term_contango",
        name="VIX Term Structure Contango",
        category=SignalCategory.VOLATILITY,
        description="VIX spot below 3-month future (contango) signals calm markets — favorable for risk-on positioning",
        feature_path="technical.vix_term_spread",
        direction=SignalDirection.ABOVE,
        threshold=0.03,
        strong_threshold=0.10,
        weight=0.8,
        tags=["macro_vol", "regime"],
    ),
    AlphaSignalDefinition(
        id="volatility.realized_vol_regime",
        name="Realized Volatility Regime",
        category=SignalCategory.VOLATILITY,
        description="Low realized-vol regime favors momentum/trend signals; high-vol regime favors mean-reversion/value",
        feature_path="technical.realized_vol_20d",
        direction=SignalDirection.BELOW,
        threshold=0.20,
        strong_threshold=0.12,
        weight=0.7,
        tags=["regime_detection", "vol_clustering"],
    ),
]

# Auto-register
registry.register_many(VOLATILITY_SIGNALS)
