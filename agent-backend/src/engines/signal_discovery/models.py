"""
src/engines/signal_discovery/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic models for the Signal Discovery Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ─── Enums ──────────────────────────────────────────────────────────────────

class CandidateType(str, Enum):
    SINGLE = "single"
    RATIO = "ratio"
    INTERACTION = "interaction"
    ZSCORE = "zscore"


class CandidateStatus(str, Enum):
    DISCOVERED = "discovered"
    REJECTED = "rejected"
    PROMOTED = "promoted"


# ─── Configuration ──────────────────────────────────────────────────────────

class DiscoveryConfig(BaseModel):
    """Configurable parameters for signal discovery."""
    min_ic: float = Field(0.03, description="Minimum information coefficient")
    min_hit_rate: float = Field(0.52, description="Must beat coin flip")
    min_stability: float = Field(0.50, description="IC persistent in ≥50% windows")
    min_sample_size: int = Field(30, ge=10)
    significance_alpha: float = Field(0.05, gt=0, lt=1)
    use_bonferroni: bool = True
    stability_window_months: int = Field(6, ge=1)
    max_candidates: int = Field(500, ge=1)


# ─── Candidate Signal ──────────────────────────────────────────────────────

class CandidateSignal(BaseModel):
    """A discovered candidate signal with evaluation metrics."""
    candidate_id: str
    name: str = ""
    feature_formula: str = ""
    candidate_type: str = CandidateType.SINGLE.value
    direction: str = "above"
    threshold: float = 0.0
    category: str = ""

    # Evaluation metrics
    information_coefficient: float = 0.0
    hit_rate: float = 0.0
    sharpe_ratio: float = 0.0
    sample_size: int = 0
    stability: float = 0.0
    p_value: float = 1.0
    adjusted_p_value: float = 1.0

    # Decision
    status: str = CandidateStatus.DISCOVERED.value


# ─── Report ─────────────────────────────────────────────────────────────────

class DiscoveryReport(BaseModel):
    """Complete signal discovery output."""
    config: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    candidates: list[CandidateSignal] = Field(default_factory=list)
    total_generated: int = 0
    total_evaluated: int = 0
    total_stable: int = 0
    total_promoted: int = 0
    total_rejected: int = 0
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
