"""
src/engines/alpha_signals/signals/quality_signals.py
──────────────────────────────────────────────────────────────────────────────
Quality Alpha Signals — detect companies with durable competitive
advantages, strong returns on capital, and financial discipline.
"""

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    SignalCategory,
    SignalDirection,
)
from src.engines.alpha_signals.registry import registry


QUALITY_SIGNALS = [
    AlphaSignalDefinition(
        id="quality.high_roic",
        name="High ROIC",
        category=SignalCategory.QUALITY,
        description="Return on Invested Capital above threshold indicates strong capital efficiency",
        feature_path="fundamental.roic",
        direction=SignalDirection.ABOVE,
        threshold=0.15,
        strong_threshold=0.25,
        weight=1.3,
        tags=["moat", "capital_efficiency"],
    ),
    AlphaSignalDefinition(
        id="quality.stable_margins",
        name="Stable Margins",
        category=SignalCategory.QUALITY,
        description="Expanding or stable operating margins indicate business resilience",
        feature_path="fundamental.margin_trend",
        direction=SignalDirection.ABOVE,
        threshold=0.0,
        strong_threshold=0.03,
        weight=1.0,
        tags=["margin_stability", "operating_leverage"],
    ),
    AlphaSignalDefinition(
        id="quality.strong_earnings_quality",
        name="Strong Earnings Quality",
        category=SignalCategory.QUALITY,
        description="High earnings stability score indicates predictable, reliable earnings",
        feature_path="fundamental.earnings_stability",
        direction=SignalDirection.ABOVE,
        threshold=7.0,
        strong_threshold=8.5,
        weight=1.1,
        tags=["earnings_quality", "predictability"],
    ),
    AlphaSignalDefinition(
        id="quality.low_leverage",
        name="Low Leverage",
        category=SignalCategory.QUALITY,
        description="Low debt-to-equity indicates conservative balance sheet management",
        feature_path="fundamental.debt_to_equity",
        direction=SignalDirection.BELOW,
        threshold=0.5,
        strong_threshold=0.25,
        weight=0.9,
        tags=["balance_sheet", "financial_strength"],
    ),
    AlphaSignalDefinition(
        id="quality.high_roe",
        name="High Return on Equity",
        category=SignalCategory.QUALITY,
        description="ROE above threshold signals efficient equity capital deployment",
        feature_path="fundamental.roe",
        direction=SignalDirection.ABOVE,
        threshold=0.15,
        strong_threshold=0.25,
        weight=1.0,
        tags=["profitability", "equity_returns"],
    ),
    # ── Q06–Q08: Expanded institutional quality signals ────────────
    AlphaSignalDefinition(
        id="quality.interest_coverage_fortress",
        name="Interest Coverage Fortress",
        category=SignalCategory.QUALITY,
        description="High EBIT/Interest coverage signals debt-servicing capacity without stress (rating-agency metric)",
        feature_path="fundamental.interest_coverage",
        direction=SignalDirection.ABOVE,
        threshold=5.0,
        strong_threshold=10.0,
        weight=0.9,
        tags=["financial_strength", "credit_quality"],
    ),
    AlphaSignalDefinition(
        id="quality.piotroski_f_score",
        name="Piotroski F-Score",
        category=SignalCategory.QUALITY,
        description="Composite 9-factor fundamental quality score — F >= 8 signals strong fundamentals (Piotroski 2000)",
        feature_path="fundamental.f_score",
        direction=SignalDirection.ABOVE,
        threshold=6.0,
        strong_threshold=8.0,
        weight=1.2,
        tags=["composite_quality", "academic_factor"],
    ),
    AlphaSignalDefinition(
        id="quality.asset_turnover_improving",
        name="Asset Turnover Efficiency",
        category=SignalCategory.QUALITY,
        description="Improving revenue per dollar of assets indicates management extracting more from existing base",
        feature_path="fundamental.asset_turnover",
        direction=SignalDirection.ABOVE,
        threshold=0.5,
        strong_threshold=1.0,
        weight=0.8,
        tags=["operational_efficiency", "dupont"],
    ),
]

# Auto-register
registry.register_many(QUALITY_SIGNALS)
