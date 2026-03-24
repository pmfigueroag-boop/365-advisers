"""
src/engines/technical/war_room/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic schemas for the Technical IC (War Room) simulation.

6-agent structured debate with 5 rounds:
  Round 1 — ASSESS:     Each specialist evaluates their domain
  Round 2 — CONFLICT:   Disagreements identified, challenges issued
  Round 3 — TIMEFRAME:  Reconciliation across 6 timeframes
  Round 4 — CONVICTION: Final votes with regime-weighted influence
  Round 5 — SYNTHESIS:  Head Technician produces verdict + action plan
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ─── Agent Identity ──────────────────────────────────────────────────────────

class TacticalMember(BaseModel):
    """Identity card for a War Room analyst."""
    name: str
    role: str
    domain: str                      # trend | momentum | volatility | volume | structure | mtf
    framework: str                   # theoretical school
    bias_description: str            # natural analytical tendency


# ─── Round 1 — ASSESS ────────────────────────────────────────────────────────

class TacticalAssessment(BaseModel):
    """Round 1 output: each agent's initial assessment of their domain."""
    agent: str
    domain: str
    signal: Literal["STRONG_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONG_BEARISH"]
    conviction: float = Field(ge=0.0, le=1.0)
    thesis: str                      # 2-3 sentences citing real data
    supporting_data: list[str] = Field(default_factory=list)
    theoretical_framework: str = ""  # theory backing the reading
    cross_module_note: str = ""      # observation on another module


# ─── Round 2 — CONFLICT ──────────────────────────────────────────────────────

class TacticalConflict(BaseModel):
    """Round 2 output: a conflict between two agents."""
    challenger: str
    target: str
    disagreement: str                # what they disagree on
    challenger_evidence: list[str] = Field(default_factory=list)
    theoretical_basis: str = ""      # framework supporting the challenge
    severity: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"


# ─── Round 3 — TIMEFRAME RECONCILIATION ──────────────────────────────────────

class TimeframeAssessment(BaseModel):
    """Round 3 output: each agent's multi-timeframe reconciliation."""
    agent: str
    timeframe_alignment: Literal["ALIGNED", "DIVERGENT", "PARTIAL"]
    dominant_timeframe: str          # which TF they weight most
    timeframe_readings: dict[str, str] = Field(default_factory=dict)  # {"1D": "BULLISH", ...}
    conviction_adjustment: float = 0.0   # how much conviction changed
    defense: str = ""                # response to Round 2 challenges


# ─── Round 4 — CONVICTION VOTE ───────────────────────────────────────────────

class TacticalVote(BaseModel):
    """Round 4 output: final signal, conviction, and drift."""
    agent: str
    signal: Literal["STRONG_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONG_BEARISH"]
    conviction: float = Field(ge=0.0, le=1.0)
    conviction_drift: float = 0.0    # change from Round 1
    rationale: str = ""
    regime_weight: float = 1.0       # influence multiplier from regime
    dissents: bool = False


# ─── Round 5 — HEAD TECHNICIAN VERDICT ────────────────────────────────────────

class ActionPlan(BaseModel):
    """Concrete trading action plan from the War Room."""
    entry_zone: str = ""             # e.g., "$175.50 – $177.00"
    stop_loss: str = ""              # e.g., "$172.80 (below SMA200)"
    take_profit_1: str = ""          # e.g., "$185.00 (nearest resistance)"
    take_profit_2: str = ""          # e.g., "$192.00 (measured move)"
    invalidation: str = ""           # e.g., "Close below $170 on volume"
    risk_reward: str = ""            # e.g., "1:2.4"
    position_size_note: str = ""     # e.g., "Half position due to vol regime"


class TechnicalICVerdict(BaseModel):
    """Round 5 output: Head Technician synthesis and action plan."""
    signal: str                      # STRONG_BUY | BUY | NEUTRAL | SELL | STRONG_SELL
    score: float = 5.0               # conviction-weighted score 0-10 (homologated with IC Debate)
    confidence: float = Field(ge=0.0, le=1.0)
    consensus_strength: Literal[
        "unanimous", "strong_majority", "majority", "split", "contested"
    ] = "majority"
    narrative: str = ""              # executive summary
    action_plan: ActionPlan = Field(default_factory=ActionPlan)
    key_levels: str = ""             # S/R with context
    timing: str = ""                 # entry timing recommendation
    risk_factors: list[str] = Field(default_factory=list)
    vote_breakdown: dict[str, int] = Field(default_factory=dict)  # {"BUY": 3, "NEUTRAL": 2, ...}
    dissenting_opinions: list[str] = Field(default_factory=list)


# ─── Transcript (full session) ────────────────────────────────────────────────

class TechnicalICTranscript(BaseModel):
    """Complete War Room session transcript."""
    ticker: str
    members: list[TacticalMember] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    round_1_assessments: list[TacticalAssessment] = Field(default_factory=list)
    round_2_conflicts: list[TacticalConflict] = Field(default_factory=list)
    round_3_timeframes: list[TimeframeAssessment] = Field(default_factory=list)
    round_4_votes: list[TacticalVote] = Field(default_factory=list)
    verdict: TechnicalICVerdict | None = None

    elapsed_ms: int = 0
