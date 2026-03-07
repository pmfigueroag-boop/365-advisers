"""
src/engines/governance/models.py
─────────────────────────────────────────────────────────────────────────────
Pydantic models (data contracts) for the Research Governance layer.
These are NOT SQLAlchemy models — see database.py for persistence.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ─── Enums ────────────────────────────────────────────────────────────────────


class ExperimentType(str, Enum):
    BACKTEST = "backtest"
    WALK_FORWARD = "walk_forward"
    DISCOVERY = "discovery"
    CALIBRATION = "calibration"
    ENSEMBLE = "ensemble"
    ONLINE_LEARNING = "online_learning"


class ExperimentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ArtifactType(str, Enum):
    WEIGHTS = "weights"
    THRESHOLDS = "thresholds"
    MODEL_PARAMS = "model_params"
    REPORT = "report"
    CONFIG = "config"
    METRICS = "metrics"


class AuditAction(str, Enum):
    EXPERIMENT_CREATED = "experiment_created"
    EXPERIMENT_COMPLETED = "experiment_completed"
    EXPERIMENT_FAILED = "experiment_failed"
    SIGNAL_VERSION_CREATED = "signal_version_created"
    WEIGHT_UPDATED = "weight_updated"
    THRESHOLD_UPDATED = "threshold_updated"
    SIGNAL_ENABLED = "signal_enabled"
    SIGNAL_DISABLED = "signal_disabled"
    CALIBRATION_APPLIED = "calibration_applied"
    LINEAGE_LINK_CREATED = "lineage_link_created"


# ─── Data Models ──────────────────────────────────────────────────────────────


class ExperimentCreate(BaseModel):
    """Payload to register a new experiment."""
    experiment_type: ExperimentType
    name: str
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    signal_versions: dict[str, Any] = Field(default_factory=dict)
    parent_experiment_id: str | None = None
    created_by: str = "auto"


class ExperimentSummary(BaseModel):
    """Read-only summary returned by the registry."""
    experiment_id: str
    experiment_type: ExperimentType
    name: str
    status: ExperimentStatus
    parent_experiment_id: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    completed_at: datetime | None = None
    created_by: str = "auto"
    artifact_count: int = 0


class ExperimentArtifactCreate(BaseModel):
    """Payload to attach an artifact to an experiment."""
    artifact_type: ArtifactType
    payload: dict[str, Any]


class ExperimentArtifactSummary(BaseModel):
    artifact_id: int
    experiment_id: str
    artifact_type: ArtifactType
    created_at: datetime


class SignalVersionCreate(BaseModel):
    """Snapshot of a signal's configuration at a point in time."""
    signal_id: str
    config: dict[str, Any]  # threshold, weight, half_life, enabled, ...
    produced_by_experiment: str | None = None


class SignalVersionSummary(BaseModel):
    version_id: int
    signal_id: str
    version_number: int
    config: dict[str, Any]
    effective_from: datetime
    effective_until: datetime | None = None
    produced_by_experiment: str | None = None


class LineageLink(BaseModel):
    """A directed edge in the model lineage DAG."""
    source_experiment_id: str
    target_experiment_id: str
    relationship: str = "produced_by"  # produced_by | depends_on | supersedes


class LineageNode(BaseModel):
    experiment_id: str
    experiment_type: ExperimentType
    name: str
    status: ExperimentStatus
    parents: list[str] = Field(default_factory=list)
    children: list[str] = Field(default_factory=list)


class AuditEntry(BaseModel):
    """Immutable audit log entry."""
    action: AuditAction
    entity_type: str  # experiment | signal | weight | threshold
    entity_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    performed_by: str = "auto"
    timestamp: datetime | None = None
