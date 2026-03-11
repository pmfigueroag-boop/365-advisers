"""
src/contracts/analysis.py
──────────────────────────────────────────────────────────────────────────────
Pydantic contracts for the Analysis module.

These contracts describe the actual data structures flowing through the
fundamental graph and combined pipeline. Field names match the LangGraph
engine output (graph.py) — not aspirational schemas.
"""

from pydantic import BaseModel, Field


class AgentMemo(BaseModel):
    """One analyst's output from the fundamental LangGraph engine."""
    agent: str = Field(description="Agent name (e.g. 'Value & Margin of Safety')")
    framework: str = Field(description="Investment framework used")
    signal: str = Field(description="BUY | SELL | HOLD | AVOID")
    conviction: float = Field(ge=0.0, le=1.0, description="0.0–1.0 confidence")
    memo: str = Field(description="Short analysis memo in Spanish")
    key_metrics_used: list[str] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    is_fallback: bool = Field(default=False, description="True if LLM call failed")


class CommitteeVerdict(BaseModel):
    """Committee Supervisor output — synthesized from 4 agent memos."""
    signal: str
    score: float = Field(ge=0, le=10)
    confidence: float = Field(ge=0, le=1)
    risk_adjusted_score: float = Field(ge=0, le=10)
    consensus_narrative: str
    key_catalysts: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    allocation_recommendation: str = ""


class FundamentalResult(BaseModel):
    """Envelope for a complete fundamental analysis."""
    ticker: str
    agents: list[AgentMemo]
    committee: CommitteeVerdict
    research_memo: str = ""


class TechnicalResult(BaseModel):
    """Summary output from the technical analysis engine."""
    ticker: str
    technical_score: float
    signal: str
    from_cache: bool = False
    modules: dict = Field(default_factory=dict)
    indicators: dict = Field(default_factory=dict)
    summary: dict = Field(default_factory=dict)
