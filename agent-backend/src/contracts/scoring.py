"""
src/contracts/scoring.py
──────────────────────────────────────────────────────────────────────────────
Layer 4 output contracts — Institutional Opportunity Scoring.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DimensionScores(BaseModel):
    """Scores for the 4 institutional pillars (0.0 – 10.0 each)."""
    business_quality: float = 5.0
    valuation: float = 5.0
    financial_strength: float = 5.0
    market_behavior: float = 5.0


class FactorBreakdown(BaseModel):
    """12-factor detailed breakdown."""
    # Business Quality
    competitive_moat: float = 5.0
    management_capital_allocation: float = 5.0
    industry_structure: float = 5.0

    # Valuation
    relative_valuation: float = 5.0
    intrinsic_value_gap: float = 5.0
    fcf_yield: float = 5.0

    # Financial Strength
    balance_sheet_strength: float = 5.0
    earnings_stability: float = 5.0
    growth_quality: float = 5.0

    # Market Behavior
    trend_strength: float = 5.0
    momentum: float = 5.0
    institutional_flow: float = 5.0


class SourceDecomposition(BaseModel):
    """Epistemological source breakdown for score transparency."""
    quantitative_metrics: float = 0.5   # % of score from verifiable metrics
    agent_conviction: float = 0.5       # % from LLM agent convictions
    alpha_signal_bridge: float = 0.0    # % from CASE/signal blending


class OpportunityScoreResult(BaseModel):
    """Complete output of the 12-Factor Institutional Scoring Engine (Layer 4)."""
    opportunity_score: float = 5.0      # 0.0 – 10.0
    dimensions: DimensionScores = Field(default_factory=DimensionScores)
    factors: FactorBreakdown = Field(default_factory=FactorBreakdown)
    dimension_weights: dict[str, float] = Field(default_factory=lambda: {
        "business_quality": 0.25,
        "valuation": 0.25,
        "financial_strength": 0.25,
        "market_behavior": 0.25,
    })
    source_decomposition: SourceDecomposition = Field(
        default_factory=SourceDecomposition,
    )
    recorded_at: str = ""
