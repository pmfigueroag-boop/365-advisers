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
    memo: str = Field(description="Short analysis memo")
    key_metrics_used: list[str] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    is_fallback: bool = Field(default=False, description="True if LLM call failed")


class CommitteeVerdict(BaseModel):
    """Committee Supervisor output — synthesized from 4 agent memos."""
    signal: str = "HOLD"
    score: float = Field(default=5.0, ge=0, le=10)
    confidence: float = Field(default=0.5, ge=0, le=1)
    risk_adjusted_score: float = Field(default=4.5, ge=0, le=10)
    consensus_narrative: str = ""
    key_catalysts: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    allocation_recommendation: str = ""


class FundamentalResult(BaseModel):
    """Envelope for a complete fundamental analysis."""
    ticker: str
    agent_memos: list[AgentMemo] = Field(default_factory=list)
    data_ready: dict = Field(default_factory=dict)
    committee_verdict: CommitteeVerdict = Field(default_factory=CommitteeVerdict)
    research_memo: str = ""
    # Deterministic scoring (added by FundamentalScoringEngine)
    deterministic_score: float | None = Field(default=None, ge=0, le=10,
                                               description="Deterministic score 0-10 from ratios")
    deterministic_signal: str | None = Field(default=None,
                                              description="Signal from deterministic scoring")
    score_evidence: list[str] = Field(default_factory=list,
                                       description="Evidence trail from deterministic scoring")
    data_coverage: float = Field(default=0.0, ge=0, le=1,
                                  description="Fraction of ratios available 0-1")


class ModuleScore(BaseModel):
    """Per-module deterministic score with evidence trail."""
    name: str = Field(description="Module name: trend, momentum, volatility, volume, structure")
    score: float = Field(ge=0, le=10, description="Normalised 0–10 score")
    signal: str = Field(description="Module-level signal status")
    evidence: list[str] = Field(default_factory=list, description="Evidence explaining this score")
    details: dict = Field(default_factory=dict, description="Raw indicator values for audit")


class TechnicalBiasResult(BaseModel):
    """Professional-grade technical bias assessment."""
    primary_bias: str = "NEUTRAL"
    bias_strength: float = Field(default=0.0, ge=0, le=1,
                                  description="Continuous bias magnitude 0–1")
    trend_alignment: str = "NEUTRAL"
    risk_reward_ratio: float = Field(default=1.0, description="R/R ratio from structure levels")
    key_levels: dict = Field(default_factory=dict)
    actionable_zone: str = "NEUTRAL_ZONE"
    time_horizon: str = "MEDIUM"
    setup_quality: float = Field(default=0.0, ge=0, le=1,
                                  description="0–1 reliability proxy for this setup")


class PositionSizingResult(BaseModel):
    """Volatility-adjusted position sizing recommendation."""
    method: str = "VOLATILITY_ADJUSTED"
    suggested_pct_of_portfolio: float = Field(default=0.0, ge=0, le=1)
    stop_loss_price: float = 0.0
    stop_loss_pct: float = 0.0
    take_profit_price: float = 0.0
    take_profit_pct: float = 0.0
    risk_per_trade_pct: float = 0.02
    risk_reward_ratio: float = 1.0
    position_conviction: str = "MEDIUM"
    rationale: list[str] = Field(default_factory=list)


class TechnicalResult(BaseModel):
    """Summary output from the technical analysis engine."""
    ticker: str
    technical_score: float
    signal: str
    strength: str = "Weak"
    technical_confidence: float = Field(default=0.5, ge=0, le=1,
                                        description="Inter-module agreement metric 0–1")
    from_cache: bool = False
    module_scores: list[ModuleScore] = Field(default_factory=list)
    volatility_condition: str = "NORMAL"
    summary: dict = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list,
                                description="Aggregated evidence from all modules")
    strongest_module: str = ""
    weakest_module: str = ""
    confirmation_level: str = Field(default="LOW",
                                    description="HIGH / MEDIUM / LOW based on module agreement")
    bias: TechnicalBiasResult = Field(default_factory=TechnicalBiasResult)
    position_sizing: PositionSizingResult = Field(default_factory=PositionSizingResult)
    setup_quality: float = Field(default=0.0, ge=0, le=1,
                                  description="Setup reliability proxy 0–1")

