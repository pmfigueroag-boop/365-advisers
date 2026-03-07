"""
src/engines/online_learning/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic models for the Online Learning Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


# ─── Configuration ──────────────────────────────────────────────────────────

class OnlineLearningConfig(BaseModel):
    """Configurable parameters for online learning."""
    learning_rate: float = Field(0.05, gt=0, le=1, description="EMA α")
    max_change_per_step: float = Field(0.10, gt=0, description="Max |Δw| per update")
    min_weight: float = Field(0.01, ge=0)
    max_weight: float = Field(0.50, le=1)
    warmup_observations: int = Field(20, ge=1)
    decay_learning_rate: bool = True
    lr_decay_factor: float = Field(0.995, gt=0, le=1)
    normalize_weights: bool = True


# ─── Observation ────────────────────────────────────────────────────────────

class SignalObservation(BaseModel):
    """A single new data point for a signal."""
    signal_id: str
    forward_return: float = 0.0
    benchmark_return: float = 0.0
    hit: bool = False  # positive return?


# ─── Weight Update ──────────────────────────────────────────────────────────

class WeightUpdate(BaseModel):
    """Result of a single weight update."""
    signal_id: str
    weight_before: float = 0.0
    weight_after: float = 0.0
    delta: float = 0.0
    raw_delta: float = 0.0
    dampened: bool = False
    observation_return: float = 0.0
    learning_rate_used: float = 0.0


# ─── Learning State ────────────────────────────────────────────────────────

class LearningState(BaseModel):
    """Current state of the online learner per signal."""
    signal_id: str
    current_weight: float = 1.0
    observations_count: int = 0
    cumulative_return: float = 0.0
    hit_rate: float = 0.0
    current_learning_rate: float = 0.05


# ─── Report ─────────────────────────────────────────────────────────────────

class OnlineLearningReport(BaseModel):
    """Complete online learning update output."""
    config: OnlineLearningConfig = Field(default_factory=OnlineLearningConfig)
    updates: list[WeightUpdate] = Field(default_factory=list)
    state: list[LearningState] = Field(default_factory=list)
    total_observations: int = 0
    dampened_count: int = 0
    current_learning_rate: float = 0.05
    warmed_up: bool = False
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
