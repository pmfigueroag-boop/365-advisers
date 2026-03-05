"""
src/engines/ranking/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Global Opportunity Ranking Engine.

Defines configuration, per-asset ranked opportunities, and the full
ranking result with global, sector, and strategy views.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ─── Tier Classification ────────────────────────────────────────────────────

class OpportunityTier(str, Enum):
    TOP_TIER = "Top Tier"
    STRONG = "Strong"
    MODERATE = "Moderate"
    WEAK = "Weak"
    AVOID = "Avoid"


# ─── Configuration ──────────────────────────────────────────────────────────

class RankingConfig(BaseModel):
    """Tunable parameters for the ranking model."""
    w_case: float = Field(0.45, description="Weight for Composite Alpha Score")
    w_opp_score: float = Field(0.35, description="Weight for Opportunity Score")
    w_signal_strength: float = Field(0.20, description="Weight for Signal Strength")
    top_n: int = Field(10, ge=1, description="Number of top opportunities")
    min_alloc_pct: float = Field(2.0, ge=0.0, description="Min allocation per asset (%)")
    max_alloc_pct: float = Field(15.0, ge=1.0, description="Max allocation per asset (%)")
    confidence_multipliers: dict[str, float] = Field(
        default={"high": 1.00, "medium": 0.85, "low": 0.65},
    )


# ─── Ranked Opportunity ─────────────────────────────────────────────────────

class RankedOpportunity(BaseModel):
    """A single ranked asset with unified score and allocation."""
    rank: int = 0
    ticker: str
    name: str = ""
    sector: str = ""
    idea_type: str = ""                 # value|quality|momentum|reversal|event
    uos: float = Field(0.0, description="Unified Opportunity Score 0-100")
    tier: OpportunityTier = OpportunityTier.AVOID
    case_score: float = 0.0             # Raw CASE 0-100
    opportunity_score: float = 0.0      # Raw Opp 0-10
    signal_strength: float = 0.0        # Raw 0-1.0
    confidence: str = "low"             # high|medium|low
    suggested_alloc_pct: float = 0.0    # 0-15%
    signal_count: int = 0
    idea_id: str = ""
    metadata: dict = Field(default_factory=dict)


# ─── Ranking Result ─────────────────────────────────────────────────────────

class RankingResult(BaseModel):
    """Complete output of the ranking engine."""
    global_ranking: list[RankedOpportunity] = Field(default_factory=list)
    by_sector: dict[str, list[RankedOpportunity]] = Field(default_factory=dict)
    by_strategy: dict[str, list[RankedOpportunity]] = Field(default_factory=dict)
    top_n: list[RankedOpportunity] = Field(default_factory=list)
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    universe_size: int = 0
    config: RankingConfig = Field(default_factory=RankingConfig)
