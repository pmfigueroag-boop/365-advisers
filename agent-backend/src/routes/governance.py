"""
src/routes/governance.py
─────────────────────────────────────────────────────────────────────────────
REST API for the Research Governance layer.

Endpoints:
  Experiments:  CRUD, status transitions, artifact attachment
  Versioning:   Signal version history, diffs, snapshots
  Lineage:      Ancestry/descendant DAG traversal
  Audit:        Query the immutable audit trail
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from src.engines.governance import (
    AuditLogger,
    ExperimentRegistry,
    ModelLineageTracker,
    SignalVersionManager,
)
from src.engines.governance.models import (
    AuditAction,
    ExperimentArtifactCreate,
    ExperimentCreate,
    ExperimentStatus,
    ExperimentType,
    SignalVersionCreate,
)

logger = logging.getLogger("365advisers.routes.governance")

router = APIRouter(prefix="/governance", tags=["governance"])

# ── Singletons ────────────────────────────────────────────────────────────────

_registry = ExperimentRegistry()
_versioning = SignalVersionManager()
_lineage = ModelLineageTracker()
_audit = AuditLogger()


# ═══════════════════════════════════════════════════════════════════════════════
#  EXPERIMENTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/experiments", status_code=201)
def create_experiment(payload: ExperimentCreate):
    """Register a new experiment and return its ID."""
    experiment_id = _registry.register(payload)

    # Audit log
    _audit.log_experiment_created(
        experiment_id,
        payload.experiment_type.value,
        payload.name,
    )

    return {"experiment_id": experiment_id, "status": "pending"}


@router.get("/experiments")
def list_experiments(
    experiment_type: ExperimentType | None = None,
    status: ExperimentStatus | None = None,
    limit: int = Query(default=50, le=200),
):
    """List experiments with optional filters."""
    items = _registry.list_experiments(
        experiment_type=experiment_type,
        status=status,
        limit=limit,
    )
    return {"experiments": [e.model_dump() for e in items], "count": len(items)}


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: str):
    """Get a specific experiment by ID."""
    exp = _registry.get(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp.model_dump()


@router.patch("/experiments/{experiment_id}/status")
def update_experiment_status(
    experiment_id: str,
    status: ExperimentStatus,
    metrics: dict | None = None,
    error: str | None = None,
):
    """Transition an experiment to a new status."""
    exp = _registry.get(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    if status == ExperimentStatus.RUNNING:
        _registry.mark_running(experiment_id)
    elif status == ExperimentStatus.COMPLETED:
        _registry.mark_completed(experiment_id, metrics=metrics)
        _audit.log_experiment_completed(experiment_id, metrics)
    elif status == ExperimentStatus.FAILED:
        _registry.mark_failed(experiment_id, error=error)

    return {"experiment_id": experiment_id, "status": status.value}


# ── Artifacts ─────────────────────────────────────────────────────────────────


@router.post("/experiments/{experiment_id}/artifacts", status_code=201)
def attach_artifact(experiment_id: str, payload: ExperimentArtifactCreate):
    """Attach an artifact to an experiment."""
    exp = _registry.get(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    artifact_id = _registry.attach_artifact(experiment_id, payload)
    return {"artifact_id": artifact_id, "experiment_id": experiment_id}


@router.get("/experiments/{experiment_id}/artifacts")
def get_artifacts(experiment_id: str):
    """List all artifacts for an experiment."""
    artifacts = _registry.get_artifacts(experiment_id)
    return {
        "experiment_id": experiment_id,
        "artifacts": [a.model_dump() for a in artifacts],
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  SIGNAL VERSIONING
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/signals/versions", status_code=201)
def create_signal_version(payload: SignalVersionCreate):
    """Snapshot a signal's current config as a new version."""
    version_id = _versioning.create_version(payload)

    # Get the version to log
    ver = _versioning.get_current(payload.signal_id)
    if ver:
        _audit.log_signal_version(
            payload.signal_id,
            ver.version_number,
            ver.config,
            payload.produced_by_experiment,
        )

    return {
        "version_id": version_id,
        "signal_id": payload.signal_id,
        "version": ver.version_number if ver else None,
    }


@router.get("/signals/{signal_id}/versions")
def list_signal_versions(signal_id: str, limit: int = Query(default=20, le=100)):
    """List version history for a signal."""
    versions = _versioning.list_versions(signal_id, limit=limit)
    return {
        "signal_id": signal_id,
        "versions": [v.model_dump() for v in versions],
    }


@router.get("/signals/{signal_id}/current")
def get_current_signal_version(signal_id: str):
    """Get the active (latest) version of a signal."""
    ver = _versioning.get_current(signal_id)
    if not ver:
        raise HTTPException(status_code=404, detail="No versions found")
    return ver.model_dump()


@router.get("/signals/{signal_id}/diff")
def diff_signal_versions(signal_id: str, v1: int, v2: int):
    """Compare two versions of a signal config."""
    return _versioning.diff(signal_id, v1, v2)


@router.get("/signals/snapshot")
def snapshot_all_signals(experiment_id: str | None = None):
    """Get a snapshot of all currently active signal configs."""
    snapshot = _versioning.snapshot_all_signals(experiment_id)
    return {"signal_count": len(snapshot), "signals": snapshot}


# ═══════════════════════════════════════════════════════════════════════════════
#  MODEL LINEAGE
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/lineage/{experiment_id}/ancestry")
def get_ancestry(experiment_id: str, max_depth: int = Query(default=10, le=50)):
    """Get the full ancestry chain for an experiment."""
    nodes = _lineage.get_ancestry(experiment_id, max_depth=max_depth)
    return {
        "experiment_id": experiment_id,
        "ancestry": [n.model_dump() for n in nodes],
    }


@router.get("/lineage/{experiment_id}/descendants")
def get_descendants(experiment_id: str, max_depth: int = Query(default=10, le=50)):
    """Get all experiments derived from this one."""
    nodes = _lineage.get_descendants(experiment_id, max_depth=max_depth)
    return {
        "experiment_id": experiment_id,
        "descendants": [n.model_dump() for n in nodes],
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIT TRAIL
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/audit")
def query_audit(
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: AuditAction | None = None,
    limit: int = Query(default=100, le=500),
):
    """Query the immutable governance audit trail."""
    entries = _audit.query(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        limit=limit,
    )
    return {"entries": entries, "count": len(entries)}


@router.get("/audit/{entity_type}/{entity_id}")
def get_entity_audit_history(entity_type: str, entity_id: str):
    """Get the full audit history for a specific entity."""
    entries = _audit.get_entity_history(entity_type, entity_id)
    return {"entity_type": entity_type, "entity_id": entity_id, "entries": entries}
