"""
src/engines/meta_learning/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic models for the Meta-Learning Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ─── Recommendation Types ──────────────────────────────────────────────────

class RecommendationType(str, Enum):
    BOOST_WEIGHT = "boost_weight"
    REDUCE_WEIGHT = "reduce_weight"
    DISABLE_SIGNAL = "disable_signal"
    ENABLE_SIGNAL = "enable_signal"
    PROMOTE_DETECTOR = "promote_detector"
    DEMOTE_DETECTOR = "demote_detector"
    REBALANCE_REGIME = "rebalance_regime"


class TrendDirection(str, Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"


# ─── Configuration ──────────────────────────────────────────────────────────

class MetaLearningConfig(BaseModel):
    """Configurable thresholds for meta-learning analysis."""
    sharpe_decline_warn: float = Field(0.20, description="Sharpe decline % → warn")
    sharpe_decline_critical: float = Field(0.40, description="Sharpe decline % → critical")
    sharpe_boost_percentile: float = Field(0.10, description="Top percentile → boost")
    detector_accuracy_promote: float = Field(0.65, description="Hit rate → promote")
    detector_accuracy_demote: float = Field(0.40, description="Hit rate → demote")
    min_sample_size: int = Field(20, ge=5)
    lookback_days: int = Field(90, ge=7)
    boost_multiplier: float = Field(1.3, description="Weight multiplier for boosted signals")
    reduce_multiplier: float = Field(0.5, description="Weight multiplier for reduced signals")


# ─── Health Snapshots ──────────────────────────────────────────────────────

class SignalHealthSnapshot(BaseModel):
    """Health status of a single signal."""
    signal_id: str
    signal_name: str = ""
    sharpe_current: float = 0.0
    sharpe_baseline: float = 0.0
    sharpe_decline_pct: float = 0.0
    hit_rate: float = 0.0
    sample_size: int = 0
    trend: str = TrendDirection.STABLE.value
    best_regime: str = ""
    worst_regime: str = ""
    current_weight: float = 1.0


class DetectorHealthSnapshot(BaseModel):
    """Health status of a single detector type."""
    detector_type: str
    total_ideas: int = 0
    positive_ideas: int = 0
    accuracy: float = 0.0
    avg_return: float = 0.0
    trend: str = TrendDirection.STABLE.value


# ─── Recommendation ─────────────────────────────────────────────────────────

class MetaRecommendation(BaseModel):
    """An actionable recommendation from meta-learning."""
    target_id: str
    target_name: str = ""
    recommendation: str  # RecommendationType value
    reason: str = ""
    current_value: float = 0.0
    suggested_value: float = 0.0
    confidence: float = Field(0.0, ge=0, le=1)
    priority: int = Field(3, ge=1, le=3, description="1=urgent, 2=high, 3=normal")


# ─── Report ─────────────────────────────────────────────────────────────────

class MetaLearningReport(BaseModel):
    """Complete meta-learning analysis output."""
    config: MetaLearningConfig = Field(default_factory=MetaLearningConfig)
    recommendations: list[MetaRecommendation] = Field(default_factory=list)
    signal_health: list[SignalHealthSnapshot] = Field(default_factory=list)
    detector_health: list[DetectorHealthSnapshot] = Field(default_factory=list)
    summary: dict[str, int] = Field(
        default_factory=dict, description="Count per recommendation type",
    )
    total_signals_analyzed: int = 0
    total_detectors_analyzed: int = 0
    urgent_actions: int = 0
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
