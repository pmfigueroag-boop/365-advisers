"""
src/contracts/analysis.py
──────────────────────────────────────────────────────────────────────────────
Layer 3 output contracts — results produced by the Fundamental and
Technical Analysis Engines.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


# ─── Agent Memo (individual analyst output) ───────────────────────────────────

class AgentMemo(BaseModel):
    """Output of a single fundamental analyst agent."""
    agent_name: str
    signal: Literal["BUY", "HOLD", "SELL"] = "HOLD"
    confidence: float = 0.5  # 0.0 – 1.0
    analysis: str = ""
    selected_metrics: list[str] = Field(default_factory=list)
    # Institutional subscores for the Scoring Engine
    opportunity_subscores: dict[str, float] = Field(default_factory=dict)


# ─── Fundamental Result ───────────────────────────────────────────────────────

class CommitteeVerdict(BaseModel):
    """Synthesised verdict from the investment committee."""
    score: float = 5.0                    # 0.0 – 10.0
    confidence: float = 0.5              # 0.0 – 1.0
    signal: Literal["BUY", "HOLD", "SELL"] = "HOLD"
    consensus_narrative: str = ""
    key_catalysts: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)


class FundamentalResult(BaseModel):
    """Complete output of the Fundamental Analysis Engine (Layer 3a)."""
    ticker: str
    data_ready: dict = Field(default_factory=dict)       # raw ratios + company info for frontend
    agent_memos: list[AgentMemo] = Field(default_factory=list)
    committee_verdict: CommitteeVerdict = Field(default_factory=CommitteeVerdict)
    research_memo: str = ""                              # markdown 1-pager


# ─── Technical Result ─────────────────────────────────────────────────────────

class ModuleScore(BaseModel):
    """Score output of a single technical module."""
    name: str
    score: float = 5.0       # 0.0 – 10.0
    signal: str = "NEUTRAL"
    details: dict = Field(default_factory=dict)


class TechnicalResult(BaseModel):
    """Complete output of the Technical Analysis Engine (Layer 3b)."""
    ticker: str
    technical_score: float = 5.0   # aggregate 0.0 – 10.0
    signal: str = "NEUTRAL"        # STRONG_BUY → STRONG_SELL
    strength: str = "Moderate"
    volatility_condition: str = "NORMAL"  # LOW, NORMAL, ELEVATED, HIGH
    module_scores: list[ModuleScore] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)   # full summary dict for backward compat
