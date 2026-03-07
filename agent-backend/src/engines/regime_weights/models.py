"""
src/engines/regime_weights/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic models for the Regime-Adaptive Signal Weighting module.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


# ─── Configuration ──────────────────────────────────────────────────────────

class AdaptiveWeightConfig(BaseModel):
    """Configurable parameters for regime-adaptive weighting."""
    min_events_per_regime: int = Field(
        10, ge=3, description="Minimum events in a regime to compute stats",
    )
    min_mult: float = Field(0.3, ge=0, description="Floor multiplier (worst regime)")
    max_mult: float = Field(1.5, description="Ceiling multiplier (best regime)")
    neutral_mult: float = Field(1.0, description="Default when data is insufficient")
    forward_window: int = Field(20, description="Forward return window for evaluation")
    ewma_lambda: float = Field(
        0.95, ge=0, le=1, description="EWMA decay for recent regime performance",
    )


# ─── Per-Signal-Per-Regime Stats ────────────────────────────────────────────

class RegimeSignalStats(BaseModel):
    """Performance statistics for one signal in one regime."""
    signal_id: str
    regime: str
    events_count: int = 0
    sharpe: float = 0.0
    hit_rate: float = 0.0
    avg_alpha: float = 0.0
    avg_return: float = 0.0
    regime_multiplier: float = 1.0


# ─── Per-Signal Weight Profile ──────────────────────────────────────────────

class RegimeWeightProfile(BaseModel):
    """Regime-adaptive weight profile for a single signal."""
    signal_id: str
    signal_name: str = ""
    base_weight: float = 1.0
    current_regime: str = ""
    current_multiplier: float = 1.0
    effective_weight: float = 1.0
    regime_stats: dict[str, RegimeSignalStats] = Field(default_factory=dict)
    best_regime: str = ""
    worst_regime: str = ""


# ─── Report ─────────────────────────────────────────────────────────────────

class AdaptiveWeightReport(BaseModel):
    """Complete regime-adaptive weighting output."""
    config: AdaptiveWeightConfig = Field(default_factory=AdaptiveWeightConfig)
    current_regime: str = ""
    profiles: list[RegimeWeightProfile] = Field(default_factory=list)
    regime_distribution: dict[str, int] = Field(
        default_factory=dict, description="Number of trading days per regime",
    )
    total_signals: int = 0
    avg_multiplier: float = 1.0
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
