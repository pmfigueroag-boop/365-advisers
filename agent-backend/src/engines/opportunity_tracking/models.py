"""
src/engines/opportunity_tracking/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Opportunity Performance Tracking system.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class DetectorAccuracy(BaseModel):
    """Per-detector or per-confidence performance summary."""
    label: str
    idea_count: int = 0
    hit_rate: float = 0.0
    avg_return: float = 0.0
    avg_excess_return: float = 0.0
    sharpe: float = 0.0


class OpportunityPerformanceSummary(BaseModel):
    """Aggregate performance of generated ideas."""
    total_ideas: int = 0
    total_tracked: int = 0
    total_complete: int = 0
    hit_rate_20d: float = 0.0
    avg_return_20d: float = 0.0
    avg_excess_return_20d: float = 0.0
    best_idea: str = ""
    worst_idea: str = ""
    by_type: dict[str, DetectorAccuracy] = Field(default_factory=dict)
    by_confidence: dict[str, DetectorAccuracy] = Field(default_factory=dict)
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
