"""
src/engines/signal_selection/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic models for the Signal Selection & Redundancy Pruning Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ─── Enums ───────────────────────────────────────────────────────────────────

class RedundancyClass(str, Enum):
    """Signal redundancy classification."""
    KEEP = "keep"
    REDUCE_WEIGHT = "reduce_weight"
    CANDIDATE_REMOVAL = "candidate_removal"
    REMOVE = "remove"


# ─── Configuration ──────────────────────────────────────────────────────────

class RedundancyConfig(BaseModel):
    """Configurable parameters for redundancy analysis."""
    forward_window: int = Field(20, description="Forward return window for analysis")
    min_overlap: int = Field(10, ge=3, description="Minimum co-occurring events for pair")
    corr_threshold: float = Field(0.80, description="High-correlation flag threshold")
    mi_bins: int = Field(20, ge=5, description="Histogram bins for MI estimation")
    w_corr: float = Field(0.35, ge=0, le=1, description="Redundancy weight: correlation")
    w_mi: float = Field(0.25, ge=0, le=1, description="Redundancy weight: mutual info")
    w_alpha: float = Field(0.40, ge=0, le=1, description="Redundancy weight: incremental alpha")
    auto_disable_threshold: float = Field(
        0.75, description="REMOVE if score ≥ this",
    )
    candidate_threshold: float = Field(
        0.55, description="CANDIDATE_REMOVAL if score ≥ this",
    )
    reduce_threshold: float = Field(
        0.30, description="REDUCE_WEIGHT if score ≥ this",
    )
    weight_reduction_factor: float = Field(
        0.5, description="Multiply weight by this for REDUCE signals",
    )


# ─── Pair Analysis ──────────────────────────────────────────────────────────

class SignalPairAnalysis(BaseModel):
    """Pairwise analysis between two signals."""
    signal_a: str
    signal_b: str
    correlation: float = 0.0
    abs_correlation: float = 0.0
    mutual_information: float = 0.0
    overlap_count: int = 0
    redundant: bool = False


# ─── Per-Signal Profile ─────────────────────────────────────────────────────

class SignalRedundancyProfile(BaseModel):
    """Redundancy analysis result for a single signal."""
    signal_id: str
    signal_name: str = ""
    category: str = ""
    # Correlation
    max_correlation: float = 0.0
    max_corr_partner: str = ""
    avg_abs_correlation: float = 0.0
    # Mutual Information
    max_mi: float = 0.0
    max_mi_partner: str = ""
    # Incremental Alpha
    incremental_alpha: float = 0.0
    # Composite Score
    redundancy_score: float = 0.0
    classification: RedundancyClass = RedundancyClass.KEEP
    recommended_weight: float = 1.0
    # Ranked correlations
    most_correlated: list[str] = Field(default_factory=list)
    total_events: int = 0


# ─── Report ─────────────────────────────────────────────────────────────────

class RedundancyReport(BaseModel):
    """Complete redundancy analysis output."""
    config: RedundancyConfig = Field(default_factory=RedundancyConfig)
    profiles: list[SignalRedundancyProfile] = Field(default_factory=list)
    correlation_matrix: dict[str, dict[str, float]] = Field(default_factory=dict)
    pair_analyses: list[SignalPairAnalysis] = Field(default_factory=list)
    # Classification buckets
    keep_signals: list[str] = Field(default_factory=list)
    reduce_signals: list[str] = Field(default_factory=list)
    candidate_removal: list[str] = Field(default_factory=list)
    remove_signals: list[str] = Field(default_factory=list)
    # Summary
    total_signals: int = 0
    total_redundancy_pairs: int = 0
    avg_redundancy_score: float = 0.0
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
