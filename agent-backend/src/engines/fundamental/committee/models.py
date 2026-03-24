"""
src/engines/fundamental/committee/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic schemas for the Investment Committee simulation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


# ─── Agent Identity ───────────────────────────────────────────────────────────


class ICMember(BaseModel):
    """Identity card for an Investment Committee member."""

    name: str = Field(..., description="Display name, e.g. 'Value Analyst'")
    role: str = Field(..., description="Institutional role title")
    framework: str = Field(..., description="Investment philosophy (e.g. 'Graham/Buffett')")
    bias: str = Field(
        default="",
        description="Known analytical bias, e.g. 'Tends to favour cheap stocks'",
    )


# ─── Round 1: Present ────────────────────────────────────────────────────────


class PositionMemo(BaseModel):
    """Agent's initial position memo (Round 1)."""

    agent: str = Field(..., description="Agent name")
    signal: str = Field(
        default="HOLD",
        description="BUY | SELL | HOLD | STRONG_BUY | STRONG_SELL",
    )
    conviction: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Conviction 0.0–1.0"
    )
    thesis: str = Field(default="", description="2–4 sentence thesis")
    key_metrics: list[str] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


# ─── Round 2: Challenge ──────────────────────────────────────────────────────


class Challenge(BaseModel):
    """A targeted objection from one agent to another (Round 2)."""

    challenger: str = Field(..., description="Name of the challenging agent")
    target: str = Field(..., description="Name of the challenged agent")
    objection: str = Field(..., description="The specific objection or counter-argument")
    evidence: list[str] = Field(
        default_factory=list, description="Supporting data points"
    )
    severity: str = Field(
        default="moderate",
        description="low | moderate | high — how material is this objection",
    )


# ─── Round 3: Rebuttal ───────────────────────────────────────────────────────


class Rebuttal(BaseModel):
    """An agent's defense against a received challenge (Round 3)."""

    agent: str = Field(..., description="Name of the defending agent")
    challenger: str = Field(..., description="Who issued the challenge")
    defense: str = Field(..., description="Rebuttal argument")
    concession: str = Field(
        default="",
        description="Any point conceded (empty = no concession)",
    )
    conviction_adjustment: float = Field(
        default=0.0,
        ge=-0.5,
        le=0.5,
        description="How much conviction shifted (-0.5 to +0.5)",
    )


# ─── Round 4: Vote ───────────────────────────────────────────────────────────


class Vote(BaseModel):
    """Agent's final vote after the debate (Round 4)."""

    agent: str
    signal: str = Field(default="HOLD", description="Final signal after debate")
    conviction: float = Field(default=0.5, ge=0.0, le=1.0)
    rationale: str = Field(
        default="", description="Brief justification for final position"
    )
    dissents: bool = Field(
        default=False,
        description="True if agent's vote opposes the emerging majority",
    )
    conviction_drift: float = Field(
        default=0.0,
        description="Change from initial conviction (Round 1 → Round 4)",
    )


# ─── Full Session Record ─────────────────────────────────────────────────────


class ICTranscript(BaseModel):
    """Complete transcript of an Investment Committee session."""

    ticker: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    members: list[ICMember] = Field(default_factory=list)
    round_1_memos: list[PositionMemo] = Field(default_factory=list)
    round_2_challenges: list[Challenge] = Field(default_factory=list)
    round_3_rebuttals: list[Rebuttal] = Field(default_factory=list)
    round_4_votes: list[Vote] = Field(default_factory=list)
    verdict: Optional[ICVerdict] = None
    elapsed_ms: int = 0


# ─── Final Verdict ────────────────────────────────────────────────────────────


class ICVerdict(BaseModel):
    """Chairman's final synthesis after deliberation."""

    signal: str = Field(default="HOLD", description="Consensus signal")
    score: float = Field(
        default=5.0, ge=0.0, le=10.0, description="Committee score 0–10"
    )
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    consensus_strength: str = Field(
        default="mixed",
        description="unanimous | strong_majority | majority | split | contested",
    )
    narrative: str = Field(
        default="", description="Chairman's synthesis paragraph"
    )
    key_catalysts: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    dissenting_opinions: list[str] = Field(
        default_factory=list,
        description="Summaries of notable dissents",
    )
    conviction_drift_summary: str = Field(
        default="",
        description="How convictions shifted through the debate",
    )
    vote_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="Vote tally by signal, e.g. {'BUY': 4, 'HOLD': 1, 'SELL': 1}",
    )


# Fix forward reference for ICTranscript.verdict
ICTranscript.model_rebuild()
