"""
src/engines/scorecard/models.py
─────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Live Performance Scorecard.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TrackingHorizon(str, Enum):
    DAY_1 = "1d"
    DAY_5 = "5d"
    DAY_20 = "20d"
    DAY_60 = "60d"


class SignalScorecard(BaseModel):
    """Live performance card for a single alpha signal."""
    signal_id: str
    signal_name: str = ""
    category: str = ""

    # ── Metrics
    total_firings: int = 0
    hit_rate: float = 0.0           # % of firings with positive return
    avg_return: float = 0.0         # Mean forward return
    avg_excess_return: float = 0.0  # vs benchmark
    information_ratio: float = 0.0  # excess_return / tracking_error
    signal_stability: float = 0.0   # Rolling hit-rate consistency (0-1)
    pnl_contribution: float = 0.0   # Estimated P&L contribution

    # ── By horizon
    metrics_by_horizon: dict[str, dict[str, float]] = Field(default_factory=dict)

    # ── Meta
    last_fired: datetime | None = None
    is_active: bool = True


class IdeaScorecard(BaseModel):
    """Live performance card for idea quality."""
    idea_type: str
    total_ideas: int = 0
    hit_rate: float = 0.0
    avg_excess_return: float = 0.0
    avg_time_to_materialize_days: float = 0.0
    quality_score: float = 0.0     # Blended quality metric (0-10)

    # By confidence level
    by_confidence: dict[str, dict[str, float]] = Field(default_factory=dict)


class ScorecardSummary(BaseModel):
    """Top-level scorecard aggregation."""
    total_signals_tracked: int = 0
    total_ideas_tracked: int = 0
    overall_hit_rate: float = 0.0
    overall_information_ratio: float = 0.0
    overall_alpha_bps: float = 0.0   # basis points of alpha
    best_signal: str = ""
    worst_signal: str = ""
    signals_above_threshold: int = 0
    signals_below_threshold: int = 0
    last_updated: datetime | None = None

    signal_scorecards: list[SignalScorecard] = Field(default_factory=list)
    idea_scorecards: list[IdeaScorecard] = Field(default_factory=list)
