"""
src/engines/concept_drift/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic models for the Concept Drift Detection Engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ─── Enums ──────────────────────────────────────────────────────────────────

class DriftSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DetectorType(str, Enum):
    DISTRIBUTION_SHIFT = "distribution_shift"
    CORRELATION_BREAKDOWN = "correlation_breakdown"
    REGIME_SHIFT = "regime_shift"


# ─── Configuration ──────────────────────────────────────────────────────────

class DriftConfig(BaseModel):
    """Configurable parameters for drift detection."""
    ks_alpha: float = Field(0.05, description="KS test significance level")
    ks_critical_alpha: float = Field(0.001, description="KS test critical level")
    corr_breakdown_threshold: float = Field(0.30, description="Correlation drop threshold")
    cusum_k: float = Field(0.5, description="CUSUM allowance parameter")
    cusum_h: float = Field(4.0, description="CUSUM decision interval")
    rolling_window_days: int = Field(60, ge=10)
    baseline_window_days: int = Field(252, ge=30)
    min_samples: int = Field(30, ge=10)


# ─── Detection Result ──────────────────────────────────────────────────────

class DriftDetection(BaseModel):
    """Result from a single drift detector."""
    detector: str  # DetectorType value
    detected: bool = False
    statistic: float = 0.0
    p_value: float | None = None
    threshold: float = 0.0
    detail: str = ""


# ─── Alert ──────────────────────────────────────────────────────────────────

class DriftAlert(BaseModel):
    """Aggregated drift alert for a signal."""
    signal_id: str
    signal_name: str = ""
    severity: str = DriftSeverity.INFO.value
    detections: list[DriftDetection] = Field(default_factory=list)
    active_detectors: int = 0
    recommended_action: str = ""
    drift_score: float = Field(0.0, ge=0, le=1, description="Composite drift score")


# ─── Report ─────────────────────────────────────────────────────────────────

class ConceptDriftReport(BaseModel):
    """Complete concept drift analysis output."""
    config: DriftConfig = Field(default_factory=DriftConfig)
    alerts: list[DriftAlert] = Field(default_factory=list)
    total_signals_scanned: int = 0
    drifting_signals: int = 0
    critical_count: int = 0
    warning_count: int = 0
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
