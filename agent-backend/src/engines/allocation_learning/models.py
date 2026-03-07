"""
src/engines/allocation_learning/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic models for the Reinforcement-Style Allocation Learning Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


# ─── Configuration ──────────────────────────────────────────────────────────

class AllocationConfig(BaseModel):
    """Configurable parameters for allocation learning."""
    buckets: list[float] = Field(
        default_factory=lambda: [0.01, 0.02, 0.03, 0.05, 0.08],
    )
    bucket_names: list[str] = Field(
        default_factory=lambda: ["micro", "small", "medium", "large", "concentrated"],
    )
    ucb_c: float = Field(1.41, gt=0, description="UCB exploration constant (√2)")
    min_observations: int = Field(5, ge=1)
    reward_decay: float = Field(0.95, gt=0, le=1)
    max_history: int = Field(500, ge=10)


# ─── Outcome ────────────────────────────────────────────────────────────────

class AllocationOutcome(BaseModel):
    """A single allocation outcome observation."""
    ticker: str
    bucket_id: str
    allocation_pct: float = 0.0
    forward_return: float = 0.0
    holding_period_days: int = 20
    volatility: float = 0.0
    max_drawdown: float = 0.0


# ─── Bucket State ──────────────────────────────────────────────────────────

class BucketState(BaseModel):
    """Current state of one bandit arm (sizing bucket)."""
    bucket_id: str
    allocation_pct: float = 0.0
    total_pulls: int = 0
    avg_reward: float = 0.0
    ucb_score: float = Field(default=float("inf"))
    total_return: float = 0.0
    best_return: float = 0.0
    worst_return: float = 0.0


# ─── Report ─────────────────────────────────────────────────────────────────

class AllocationReport(BaseModel):
    """Complete allocation learning output."""
    config: AllocationConfig = Field(default_factory=AllocationConfig)
    bucket_states: list[BucketState] = Field(default_factory=list)
    recommended_bucket: str = ""
    recommended_allocation: float = 0.0
    total_observations: int = 0
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
