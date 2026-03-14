"""
src/engines/alpha_signals/signals/risk_signals.py
──────────────────────────────────────────────────────────────────────────────
Bearish / Risk Alpha Signals — detect overvalued, overbought, or
deteriorating conditions that should PULL the CASE score downward.

These signals fire when conditions are UNFAVORABLE.  The CASE engine
treats them as negative contributions to their respective category subscores.

P0 Corrective C3: The system previously had only bullish signals.
"""

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    SignalCategory,
    SignalDirection,
)
from src.engines.alpha_signals.registry import registry


RISK_SIGNALS = [
    # ── Momentum Bearish ─────────────────────────────────────────────────
    AlphaSignalDefinition(
        id="risk.rsi_overbought",
        name="RSI Overbought",
        category=SignalCategory.MOMENTUM,
        description="RSI above 70 signals overbought conditions — elevated reversal risk",
        feature_path="technical.rsi",
        direction=SignalDirection.ABOVE,
        threshold=70.0,
        strong_threshold=80.0,
        weight=1.2,
        tags=["bearish", "overbought", "risk"],
    ),
    AlphaSignalDefinition(
        id="risk.death_cross",
        name="Death Cross (SMA50 < SMA200)",
        category=SignalCategory.MOMENTUM,
        description="SMA50 below SMA200 indicates a structural bearish trend",
        feature_path="technical.sma50_below_sma200",
        direction=SignalDirection.BELOW,
        threshold=0.0,
        strong_threshold=-0.05,
        weight=1.3,
        tags=["bearish", "trend", "crossover", "risk"],
    ),
    AlphaSignalDefinition(
        id="risk.macd_bearish",
        name="MACD Bearish Divergence",
        category=SignalCategory.MOMENTUM,
        description="Negative MACD histogram signals decelerating or negative momentum",
        feature_path="technical.macd_hist",
        direction=SignalDirection.BELOW,
        threshold=0.0,
        strong_threshold=-0.5,
        weight=1.0,
        tags=["bearish", "macd", "risk"],
    ),

    # ── Value Bearish (Overvaluation) ────────────────────────────────────
    AlphaSignalDefinition(
        id="risk.pe_expensive",
        name="P/E Expensive",
        category=SignalCategory.VALUE,
        description="P/E ratio above 35 signals stretched valuation — premium priced in",
        feature_path="fundamental.pe_ratio",
        direction=SignalDirection.ABOVE,
        threshold=35.0,
        strong_threshold=50.0,
        weight=1.1,
        tags=["bearish", "overvalued", "risk"],
    ),
    AlphaSignalDefinition(
        id="risk.ev_ebitda_expensive",
        name="EV/EBITDA Expensive",
        category=SignalCategory.VALUE,
        description="EV/EBITDA above 25 suggests inflated enterprise valuation",
        feature_path="fundamental.ev_ebitda",
        direction=SignalDirection.ABOVE,
        threshold=25.0,
        strong_threshold=35.0,
        weight=0.9,
        tags=["bearish", "overvalued", "risk"],
    ),

    # ── Quality Bearish (Deterioration) ──────────────────────────────────
    AlphaSignalDefinition(
        id="risk.high_leverage",
        name="Excessive Leverage",
        category=SignalCategory.QUALITY,
        description="Debt-to-equity above 2.0 indicates elevated financial risk",
        feature_path="fundamental.debt_to_equity",
        direction=SignalDirection.ABOVE,
        threshold=2.0,
        strong_threshold=3.0,
        weight=1.1,
        tags=["bearish", "leverage", "risk"],
    ),
    AlphaSignalDefinition(
        id="risk.negative_margin",
        name="Negative Profit Margin",
        category=SignalCategory.QUALITY,
        description="Net margin below 0 indicates the company is losing money",
        feature_path="fundamental.net_margin",
        direction=SignalDirection.BELOW,
        threshold=0.0,
        strong_threshold=-0.10,
        weight=1.2,
        tags=["bearish", "profitability", "risk"],
    ),

    # ── Growth Bearish (Deceleration) ────────────────────────────────────
    AlphaSignalDefinition(
        id="risk.revenue_decline",
        name="Revenue Decline",
        category=SignalCategory.GROWTH,
        description="Negative revenue growth YoY signals business contraction",
        feature_path="fundamental.revenue_growth_yoy",
        direction=SignalDirection.BELOW,
        threshold=0.0,
        strong_threshold=-0.10,
        weight=1.1,
        tags=["bearish", "contraction", "risk"],
    ),
    AlphaSignalDefinition(
        id="risk.earnings_decline",
        name="Earnings Decline",
        category=SignalCategory.GROWTH,
        description="Negative earnings growth signals profit deterioration",
        feature_path="fundamental.earnings_growth_yoy",
        direction=SignalDirection.BELOW,
        threshold=0.0,
        strong_threshold=-0.15,
        weight=1.0,
        tags=["bearish", "contraction", "risk"],
    ),

    # ── Volatility Bearish ───────────────────────────────────────────────
    AlphaSignalDefinition(
        id="risk.high_beta",
        name="High Beta (Excess Volatility)",
        category=SignalCategory.VOLATILITY,
        description="Beta above 1.5 indicates amplified market risk exposure",
        feature_path="fundamental.beta",
        direction=SignalDirection.ABOVE,
        threshold=1.5,
        strong_threshold=2.0,
        weight=0.8,
        tags=["bearish", "volatility", "risk"],
    ),
]

# Auto-register
registry.register_many(RISK_SIGNALS)
