"""
src/engines/alpha_signals/signals/growth_signals.py
──────────────────────────────────────────────────────────────────────────────
Growth Alpha Signals — detect companies with accelerating revenue,
improving earnings quality, high operating leverage, and strong R&D
efficiency that indicate sustainable future growth.
"""

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    SignalCategory,
    SignalDirection,
)
from src.engines.alpha_signals.registry import registry


GROWTH_SIGNALS = [
    AlphaSignalDefinition(
        id="growth.revenue_acceleration",
        name="Revenue Acceleration",
        category=SignalCategory.GROWTH,
        description="Revenue growth rate increasing QoQ — second derivative positive signals expanding demand (Coatue/Tiger Global)",
        feature_path="fundamental.revenue_acceleration",
        direction=SignalDirection.ABOVE,
        threshold=0.02,
        strong_threshold=0.05,
        weight=1.3,
        enabled=False,  # P1.3: DISABLED — exact duplicate of fundmom.revenue_accelerating
        tags=["acceleration", "demand_expansion"],
    ),
    AlphaSignalDefinition(
        id="growth.earnings_surprise",
        name="Standardized Unexpected Earnings (SUE)",
        category=SignalCategory.GROWTH,
        description="EPS beat vs consensus — post-earnings announcement drift generates alpha for 60-90 days (Jegadeesh-Titman)",
        feature_path="fundamental.earnings_surprise_pct",
        direction=SignalDirection.ABOVE,
        threshold=0.05,
        strong_threshold=0.15,
        weight=1.2,
        tags=["PEAD", "earnings_momentum"],
    ),
    AlphaSignalDefinition(
        id="growth.estimate_revision_breadth",
        name="Estimate Revision Breadth",
        category=SignalCategory.GROWTH,
        description="Ratio of upward to total EPS revisions — broad consensus shift predicts trend continuation (Two Sigma/Citadel)",
        feature_path="fundamental.revision_breadth",
        direction=SignalDirection.ABOVE,
        threshold=0.3,
        strong_threshold=0.7,
        weight=1.1,
        tags=["analyst_consensus", "revision_momentum"],
    ),
    AlphaSignalDefinition(
        id="growth.operating_leverage",
        name="Operating Leverage Ratio",
        category=SignalCategory.GROWTH,
        description="EBIT growth / Revenue growth > 1.5 means each marginal revenue dollar generates disproportionate profit",
        feature_path="fundamental.operating_leverage",
        direction=SignalDirection.ABOVE,
        threshold=1.5,
        strong_threshold=2.5,
        weight=1.0,
        tags=["scalability", "fixed_cost_amortization"],
    ),
    AlphaSignalDefinition(
        id="growth.rule_of_40",
        name="Rule of 40 (SaaS/Tech)",
        category=SignalCategory.GROWTH,
        description="Revenue Growth + FCF Margin > 40 signals healthy growth-profitability balance (Bessemer/a16z standard)",
        feature_path="fundamental.rule_of_40",
        direction=SignalDirection.ABOVE,
        threshold=40.0,
        strong_threshold=60.0,
        weight=0.9,
        tags=["saas", "growth_quality_balance"],
    ),
    AlphaSignalDefinition(
        id="growth.capex_intensity",
        name="Growth Investment (CapEx/D&A)",
        category=SignalCategory.GROWTH,
        description="CapEx exceeding depreciation indicates investment in future productive capacity (growth capex vs maintenance)",
        feature_path="fundamental.capex_to_depreciation",
        direction=SignalDirection.ABOVE,
        threshold=1.3,
        strong_threshold=1.8,
        weight=0.8,
        tags=["capex", "capacity_expansion"],
    ),
    AlphaSignalDefinition(
        id="growth.rd_efficiency",
        name="R&D Efficiency",
        category=SignalCategory.GROWTH,
        description="Revenue growth per R&D dollar — high efficiency means innovation driving top-line expansion",
        feature_path="fundamental.rd_efficiency",
        direction=SignalDirection.ABOVE,
        threshold=1.5,
        strong_threshold=3.0,
        weight=0.9,
        tags=["innovation", "research_productivity"],
    ),
]

# Auto-register
registry.register_many(GROWTH_SIGNALS)
