"""
src/engines/validation_dashboard/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic response models for the Validation Intelligence Dashboard.

Defines the unified response that aggregates data from all QVF modules
into four dashboard sections.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from src.engines.backtesting.models import CalibrationSuggestion
from src.engines.backtesting.rolling_analyzer import DegradationReport
from src.engines.opportunity_tracking.models import (
    DetectorAccuracy,
    OpportunityPerformanceSummary,
)


# ─── Signal Leaderboard ─────────────────────────────────────────────────────

class SignalLeaderboardEntry(BaseModel):
    """Single signal in the ranked leaderboard."""
    signal_id: str
    signal_name: str = ""
    category: str = ""
    sharpe_20d: float = 0.0
    hit_rate_20d: float = 0.0
    avg_alpha_20d: float = 0.0
    quality_tier: str = "D"
    total_events: int = 0
    # Walk-Forward badge
    stability_class: str | None = None
    stability_score: float | None = None
    # Cost Model badge
    cost_resilience: str | None = None
    cost_drag_bps: float | None = None
    # Benchmark Factor badge
    alpha_source: str | None = None
    factor_alpha: float | None = None


class SignalLeaderboard(BaseModel):
    """Ranked signal overview."""
    total_signals: int = 0
    avg_sharpe: float = 0.0
    avg_hit_rate: float = 0.0
    degrading_count: int = 0
    pure_alpha_count: int = 0
    top_signals: list[SignalLeaderboardEntry] = Field(
        default_factory=list,
        description="Top 10 by Sharpe",
    )
    bottom_signals: list[SignalLeaderboardEntry] = Field(
        default_factory=list,
        description="Bottom 10 by Sharpe",
    )
    degrading_signals: list[DegradationReport] = Field(
        default_factory=list,
    )


# ─── Detector Performance ───────────────────────────────────────────────────

class DetectorPerformanceSection(BaseModel):
    """Idea generation detector accuracy breakdown."""
    detectors: list[DetectorAccuracy] = Field(default_factory=list)
    by_confidence: dict[str, DetectorAccuracy] = Field(default_factory=dict)
    best_detector: str = ""
    worst_detector: str = ""
    total_detectors: int = 0


# ─── Opportunity Tracking ───────────────────────────────────────────────────

class OpportunityTrackingSection(BaseModel):
    """Forward returns of generated ideas."""
    summary: OpportunityPerformanceSummary | None = None
    total_ideas: int = 0
    hit_rate_20d: float = 0.0
    avg_return_20d: float = 0.0
    avg_excess_20d: float = 0.0


# ─── System Health ──────────────────────────────────────────────────────────

class SystemHealthSection(BaseModel):
    """Overall QVF system health indicators."""
    # Stability distribution (from Walk-Forward)
    stability_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="{robust: n, moderate: n, weak: n, overfit: n}",
    )
    avg_stability_score: float = 0.0
    # Alpha decay
    avg_half_life_days: float | None = None
    signals_with_fast_decay: int = 0
    # Cost impact (from Cost Model)
    cost_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="{resilient: n, moderate: n, fragile: n}",
    )
    avg_cost_drag_bps: float = 0.0
    # Factor exposure (from Benchmark Factor)
    alpha_source_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="{pure_alpha: n, mixed: n, factor_beta: n}",
    )
    avg_factor_neutrality: float = 0.0
    # Recalibration
    pending_recalibrations: int = 0
    active_degradation_alerts: int = 0
    recalibration_suggestions: list[CalibrationSuggestion] = Field(
        default_factory=list,
    )


# ─── Unified Response ───────────────────────────────────────────────────────

class ValidationIntelligence(BaseModel):
    """Complete Validation Intelligence Dashboard data."""
    leaderboard: SignalLeaderboard = Field(default_factory=SignalLeaderboard)
    detector_performance: DetectorPerformanceSection = Field(
        default_factory=DetectorPerformanceSection,
    )
    opportunity_tracking: OpportunityTrackingSection = Field(
        default_factory=OpportunityTrackingSection,
    )
    system_health: SystemHealthSection = Field(
        default_factory=SystemHealthSection,
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
