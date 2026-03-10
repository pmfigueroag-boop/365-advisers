"""
src/engines/idea_generation/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Idea Generation Engine.

Defines the typed output structures used across detectors, the
ranking engine, and the API layer.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


# ─── Enumerations ─────────────────────────────────────────────────────────────

class IdeaType(str, Enum):
    VALUE = "value"
    QUALITY = "quality"
    GROWTH = "growth"
    MOMENTUM = "momentum"
    REVERSAL = "reversal"
    EVENT = "event"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SignalStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class IdeaStatus(str, Enum):
    ACTIVE = "active"
    ANALYZED = "analyzed"
    DISMISSED = "dismissed"


# ─── Signal Detail ────────────────────────────────────────────────────────────

class SignalDetail(BaseModel):
    """A single detected signal within a detector."""
    name: str
    description: str = ""
    value: float
    threshold: float
    strength: SignalStrength


# ─── Detector Result ──────────────────────────────────────────────────────────

class DetectorResult(BaseModel):
    """Output of a single detector for a single ticker.

    Scoring dimensions
    ------------------
    signal_strength : float
        How intense the detected signal is right now (0–1).
    confidence_score : float
        How reliable/credible this detection is, based on the number
        and quality of confirming sub-signals (0–1).
    alpha_score is computed downstream by the ranker from composite factors.
    """
    idea_type: IdeaType
    confidence: ConfidenceLevel
    signal_strength: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Reliability score: fired_signals / total_signals with quality adjustments",
    )
    signals: list[SignalDetail]
    detector: str = Field("", description="Name of the detector that produced this result")
    metadata: dict = Field(default_factory=dict)


# ─── Idea Candidate ──────────────────────────────────────────────────────────

class IdeaCandidate(BaseModel):
    """A fully formed investment idea ready for ranking and presentation.

    Scoring dimensions
    ------------------
    signal_strength : float
        Instantaneous intensity of the detected signal (0–1).
    confidence_score : float
        Reliability/credibility of the idea based on signal confirmation (0–1).
    alpha_score : float
        Composite attractiveness score computed by the ranker (0–1+).
        Stored in ``metadata["composite_alpha_score"]`` when available.
    """
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    ticker: str
    name: str = ""
    sector: str = ""
    idea_type: IdeaType
    confidence: ConfidenceLevel
    signal_strength: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Reliability score based on signal confirmation quality",
    )
    priority: int = 0
    signals: list[SignalDetail]
    detector: str = Field("", description="Name of the detector that produced this idea")
    status: IdeaStatus = IdeaStatus.ACTIVE
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=24)
    )
    metadata: dict = Field(default_factory=dict)


# ─── Scan Result ─────────────────────────────────────────────────────────────

class IdeaScanResult(BaseModel):
    """Complete output of a universe scan."""
    scan_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    scanned_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    universe_size: int = 0
    ideas: list[IdeaCandidate] = Field(default_factory=list)
    scan_duration_ms: float = 0.0
    detector_stats: dict = Field(default_factory=dict)
