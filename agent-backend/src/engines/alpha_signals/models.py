"""
src/engines/alpha_signals/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Alpha Signals Library.

Defines the declarative signal definition schema, evaluated signal outputs,
per-asset signal profiles, and composite scoring structures.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ─── Enumerations ─────────────────────────────────────────────────────────────

class SignalCategory(str, Enum):
    VALUE = "value"
    QUALITY = "quality"
    GROWTH = "growth"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    FLOW = "flow"
    EVENT = "event"
    MACRO = "macro"


class SignalDirection(str, Enum):
    """How to compare the observed value against the threshold."""
    ABOVE = "above"      # fires when value > threshold
    BELOW = "below"      # fires when value < threshold
    BETWEEN = "between"  # fires when lower <= value <= upper


class SignalStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ─── Signal Definition ────────────────────────────────────────────────────────

class AlphaSignalDefinition(BaseModel):
    """
    Declarative definition of an alpha signal.

    Each signal maps a feature_path (e.g. "fundamental.fcf_yield") to a
    threshold condition.  The registry holds all definitions and the evaluator
    resolves them against live feature sets.
    """
    id: str = Field(..., description="Unique key, e.g. 'value.fcf_yield_high'")
    name: str = Field(..., description="Human-readable name")
    category: SignalCategory
    description: str = ""
    feature_path: str = Field(
        ...,
        description="Dot-path to the feature: 'fundamental.<attr>' or 'technical.<attr>'",
    )
    direction: SignalDirection = SignalDirection.ABOVE
    threshold: float = 0.0
    upper_threshold: float | None = Field(
        None, description="Upper bound for BETWEEN direction",
    )
    strong_threshold: float | None = Field(
        None, description="Value beyond which the signal is classified STRONG",
    )
    enabled: bool = True
    weight: float = Field(1.0, ge=0.0, description="Relative weight within category")
    tags: list[str] = Field(default_factory=list)


# ─── Evaluated Signal ─────────────────────────────────────────────────────────

class EvaluatedSignal(BaseModel):
    """Result of evaluating a single AlphaSignalDefinition against an asset."""
    signal_id: str
    signal_name: str
    category: SignalCategory
    fired: bool = False
    value: float | None = None
    threshold: float = 0.0
    strength: SignalStrength = SignalStrength.WEAK
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    description: str = ""


# ─── Category Score ───────────────────────────────────────────────────────────

class CategoryScore(BaseModel):
    """Aggregated score for a single signal category."""
    category: SignalCategory
    fired: int = 0
    total: int = 0
    composite_strength: float = Field(0.0, ge=0.0, le=1.0)
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    dominant_strength: SignalStrength = SignalStrength.WEAK


# ─── Signal Profile ──────────────────────────────────────────────────────────

class SignalProfile(BaseModel):
    """Complete evaluated signal profile for a single asset."""
    ticker: str
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    total_signals: int = 0
    fired_signals: int = 0
    signals: list[EvaluatedSignal] = Field(default_factory=list)
    category_summary: dict[str, CategoryScore] = Field(default_factory=dict)


# ─── Composite Score ─────────────────────────────────────────────────────────

class CompositeScore(BaseModel):
    """Cross-category composite score for an asset."""
    overall_strength: float = Field(0.0, ge=0.0, le=1.0)
    overall_confidence: ConfidenceLevel = ConfidenceLevel.LOW
    category_scores: dict[str, CategoryScore] = Field(default_factory=dict)
    multi_category_bonus: bool = False
    dominant_category: SignalCategory | None = None
    active_categories: int = 0
