"""
src/contracts/decision.py
──────────────────────────────────────────────────────────────────────────────
Layer 6 output contracts — Decision Engine / CIO Memo.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from src.contracts.scoring import OpportunityScoreResult
from src.contracts.sizing import PositionAllocation


class CIOMemo(BaseModel):
    """Institutional investment memo produced by the CIO Synthesiser."""
    thesis_summary: str = ""
    valuation_view: str = ""
    technical_context: str = ""
    key_catalysts: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)


class InvestmentDecision(BaseModel):
    """
    Complete output of the Decision Engine (Layer 6).
    This is the primary user-facing output of the analysis pipeline.
    """
    ticker: str
    investment_position: str = "Neutral"     # Strong Opportunity, Moderate, Neutral, Caution, Avoid
    confidence_score: float = 0.5            # 0.0 – 1.0
    fundamental_aggregate: float = 5.0       # 0.0 – 10.0
    technical_aggregate: float = 5.0         # 0.0 – 10.0
    opportunity: OpportunityScoreResult = Field(default_factory=OpportunityScoreResult)
    position_sizing: PositionAllocation = Field(default_factory=PositionAllocation)
    cio_memo: CIOMemo = Field(default_factory=CIOMemo)
    elapsed_ms: int = 0
