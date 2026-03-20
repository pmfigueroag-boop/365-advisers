"""
src/engines/alpha_signals/signals/bonus_signals.py
──────────────────────────────────────────────────────────────────────────────
Bonus 7.1: High-Value Alpha Signals

New signals with institutional-grade alpha potential:
  - Short Interest Ratio (contrarian/squeeze)
  - Insider Buying (CEO/CFO open market buys)
  - Accruals Quality / Sloan Ratio (earnings quality)
  - Options Put/Call Ratio (contrarian flow)
  - Credit Spread Change (macro risk-off)
  - Analyst Consensus Change (stub — no free data)
"""

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    SignalCategory,
    SignalDirection,
)
from src.engines.alpha_signals.registry import registry


BONUS_SIGNALS = [
    # ── Flow: Short Interest ──────────────────────────────────────────────
    AlphaSignalDefinition(
        id="flow.short_interest_high",
        name="High Short Interest (Squeeze Setup)",
        category=SignalCategory.FLOW,
        description="Short ratio > 5 days-to-cover indicates crowded short. "
                    "Combined with positive price momentum = short squeeze setup. IC: 0.03-0.05",
        feature_path="fundamental.short_ratio",
        direction=SignalDirection.ABOVE,
        threshold=5.0,         # > 5 days to cover
        strong_threshold=10.0,  # extreme squeeze territory
        weight=1.1,
        tags=["short_squeeze", "contrarian", "crowding"],
    ),

    # ── Event: Insider Buying ─────────────────────────────────────────────
    AlphaSignalDefinition(
        id="event.insider_buying",
        name="Net Insider Buying (90d)",
        category=SignalCategory.EVENT,
        description="Net insider buy ratio > 0.6 means insiders (CEO/CFO) are buying at "
                    "open market more than selling — strongest insider signal. IC: 0.04-0.06",
        feature_path="fundamental.net_insider_buy_ratio",
        direction=SignalDirection.ABOVE,
        threshold=0.6,          # > 60% buys vs sells
        strong_threshold=0.8,   # > 80% = very strong conviction
        weight=1.3,
        tags=["insider", "conviction", "catalyst"],
    ),

    # ── Quality: Accruals Quality (Sloan Ratio) ───────────────────────────
    AlphaSignalDefinition(
        id="quality.accruals_quality",
        name="Low Accruals (High Earnings Quality)",
        category=SignalCategory.QUALITY,
        description="Sloan ratio < -0.05 means cash flow exceeds reported earnings — "
                    "high quality earnings. (NI - CFO) / Assets < 0 = conservative accounting. IC: 0.03-0.04",
        feature_path="fundamental.accruals_quality",
        direction=SignalDirection.BELOW,
        threshold=-0.05,         # accruals < -5% of assets = good quality
        strong_threshold=-0.15,  # very conservative accounting
        weight=1.0,
        tags=["earnings_quality", "sloan", "accounting"],
    ),

    AlphaSignalDefinition(
        id="risk.high_accruals",
        name="High Accruals (Low Earnings Quality)",
        category=SignalCategory.RISK,
        description="Sloan ratio > 0.10 means earnings greatly exceed cash flow — "
                    "potential earnings manipulation or aggressive accounting. IC: -0.03",
        feature_path="fundamental.accruals_quality",
        direction=SignalDirection.ABOVE,
        threshold=0.10,          # accruals > 10% of assets = red flag
        strong_threshold=0.20,   # extreme — aggressive accounting
        weight=0.9,
        tags=["earnings_quality", "red_flag", "risk"],
    ),

    # ── Flow: Options Put/Call Ratio ──────────────────────────────────────
    AlphaSignalDefinition(
        id="flow.put_call_extreme",
        name="Extreme Put/Call Ratio (Contrarian)",
        category=SignalCategory.FLOW,
        description="Put/Call ratio > 1.5 indicates extreme pessimism in options market — "
                    "contrarian buy signal (too many puts). IC: 0.02-0.03",
        feature_path="technical.put_call_ratio",
        direction=SignalDirection.ABOVE,
        threshold=1.5,          # > 1.5 = extreme pessimism
        strong_threshold=2.0,   # > 2.0 = panic-level puts
        weight=1.0,
        tags=["contrarian", "options", "sentiment"],
    ),

    # ── Macro: Credit Spread Change ───────────────────────────────────────
    AlphaSignalDefinition(
        id="macro.credit_spread_tightening",
        name="Credit Spread Tightening",
        category=SignalCategory.RISK,
        description="HY credit spread narrowing > 20 bps in 30d signals improving credit "
                    "conditions and risk-on environment — bullish for equities. IC: 0.02-0.04",
        feature_path="fundamental.credit_spread_change",
        direction=SignalDirection.BELOW,
        threshold=-20.0,         # spread tightened > 20 bps
        strong_threshold=-50.0,  # spread tightened > 50 bps
        weight=0.8,
        tags=["macro", "credit", "risk_on"],
    ),

    AlphaSignalDefinition(
        id="macro.credit_spread_widening",
        name="Credit Spread Widening (Risk-Off)",
        category=SignalCategory.RISK,
        description="HY credit spread widening > 30 bps in 30d signals deteriorating credit "
                    "conditions — risk-off, bearish for equities. IC: -0.02",
        feature_path="fundamental.credit_spread_change",
        direction=SignalDirection.ABOVE,
        threshold=30.0,          # spread widened > 30 bps
        strong_threshold=80.0,   # spread widened > 80 bps = crisis
        weight=0.7,
        tags=["macro", "credit", "risk_off", "risk"],
    ),

    # ── Growth: Analyst Consensus Change (stub) ───────────────────────────
    AlphaSignalDefinition(
        id="growth.analyst_upgrade",
        name="Analyst Consensus Upgrade",
        category=SignalCategory.GROWTH,
        description="Mean analyst recommendation improved (lower score = more bullish). "
                    "Requires: 1=Strong Buy, 5=Sell from yfinance. IC: 0.03-0.05",
        feature_path="fundamental.analyst_recommendation",
        direction=SignalDirection.BELOW,
        threshold=2.0,          # mean recommendation < 2.0 = consensus Buy
        strong_threshold=1.5,   # near Strong Buy consensus
        weight=0.9,
        tags=["analyst", "consensus", "upgrade"],
    ),
]

# Auto-register
registry.register_many(BONUS_SIGNALS)
