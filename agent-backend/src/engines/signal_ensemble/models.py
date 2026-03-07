"""
src/engines/signal_ensemble/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic models for the Signal Ensemble Intelligence module.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


# ─── Configuration ──────────────────────────────────────────────────────────

class EnsembleConfig(BaseModel):
    """Configurable parameters for ensemble analysis."""
    max_combo_size: int = Field(3, ge=2, le=5, description="Max signals per ensemble")
    min_co_fires: int = Field(10, ge=3, description="Minimum co-fire events")
    date_tolerance: int = Field(3, ge=0, description="±days for co-fire matching")
    forward_window: int = Field(20, description="Forward return window")
    stability_window_months: int = Field(6, ge=2)
    stability_stride_months: int = Field(1, ge=1)
    min_stability: float = Field(0.60, ge=0, le=1)
    min_synergy: float = Field(0.10, description="Min synergy to keep combo")
    max_ensembles: int = Field(10, ge=1, description="Top-N ensembles to keep")
    ensemble_bonus_cap: float = Field(5.0, description="Max CASE bonus points")


# ─── Co-Fire Event ──────────────────────────────────────────────────────────

class CoFireEvent(BaseModel):
    """A co-occurring event between multiple signals."""
    ticker: str
    date: str  # ISO date string
    signal_ids: list[str]
    returns: dict[str, float] = Field(default_factory=dict)
    joint_return: float = 0.0


# ─── Signal Combination ────────────────────────────────────────────────────

class SignalCombination(BaseModel):
    """Analysis of a signal combination (pair or triplet)."""
    signals: list[str]
    signal_names: list[str] = Field(default_factory=list)
    co_fire_count: int = 0
    # Synergy metrics
    joint_sharpe: float = 0.0
    max_individual_sharpe: float = 0.0
    synergy_score: float = 0.0
    # Hit rate
    joint_hit_rate: float = 0.0
    avg_individual_hit_rate: float = 0.0
    incremental_power: float = 0.0
    # Stability
    stability: float = 0.0
    stable_windows: int = 0
    total_windows: int = 0
    # Final score
    ensemble_score: float = 0.0


# ─── Report ─────────────────────────────────────────────────────────────────

class EnsembleReport(BaseModel):
    """Complete ensemble analysis output."""
    config: EnsembleConfig = Field(default_factory=EnsembleConfig)
    combinations: list[SignalCombination] = Field(default_factory=list)
    top_ensembles: list[SignalCombination] = Field(default_factory=list)
    total_pairs_analyzed: int = 0
    synergistic_pairs: int = 0
    stable_ensembles: int = 0
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
