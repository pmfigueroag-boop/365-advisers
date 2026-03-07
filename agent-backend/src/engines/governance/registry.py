"""
src/engines/governance/registry.py
─────────────────────────────────────────────────────────────────────────────
ExperimentRegistry — Tracks every research run (backtest, walk-forward,
discovery, calibration, ensemble) with full configuration snapshots and
artifact storage for institutional reproducibility.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.data.database import SessionLocal

from .models import (
    ArtifactType,
    ExperimentArtifactCreate,
    ExperimentArtifactSummary,
    ExperimentCreate,
    ExperimentStatus,
    ExperimentSummary,
    ExperimentType,
)

logger = logging.getLogger("365advisers.governance.registry")


class ExperimentRegistry:
    """Central registry for all research experiments.

    Every backtest run, walk-forward validation, signal discovery, calibration,
    or ensemble evaluation is registered here with its full configuration
    snapshot so that any result can be reproduced.
    """

    # ── Create ────────────────────────────────────────────────────────────────

    def register(self, payload: ExperimentCreate) -> str:
        """Register a new experiment.  Returns the experiment_id (UUID)."""
        from src.data.database import ExperimentRecord

        experiment_id = uuid.uuid4().hex[:16]

        with SessionLocal() as db:
            record = ExperimentRecord(
                experiment_id=experiment_id,
                experiment_type=payload.experiment_type.value,
                name=payload.name,
                config_snapshot_json=json.dumps(payload.config_snapshot),
                signal_versions_json=json.dumps(payload.signal_versions),
                parent_experiment_id=payload.parent_experiment_id,
                status=ExperimentStatus.PENDING.value,
                metrics_json="{}",
                created_by=payload.created_by,
            )
            db.add(record)
            db.commit()

        logger.info(
            "Experiment registered: %s [%s] — %s",
            experiment_id,
            payload.experiment_type.value,
            payload.name,
        )
        return experiment_id

    # ── Status transitions ────────────────────────────────────────────────────

    def mark_running(self, experiment_id: str) -> None:
        self._update_status(experiment_id, ExperimentStatus.RUNNING)

    def mark_completed(
        self,
        experiment_id: str,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        self._update_status(
            experiment_id, ExperimentStatus.COMPLETED, metrics=metrics
        )

    def mark_failed(
        self, experiment_id: str, error: str | None = None
    ) -> None:
        self._update_status(
            experiment_id, ExperimentStatus.FAILED, error=error
        )

    # ── Artifacts ─────────────────────────────────────────────────────────────

    def attach_artifact(
        self,
        experiment_id: str,
        artifact: ExperimentArtifactCreate,
    ) -> int:
        """Attach an artifact (weights, thresholds, report…) to an experiment."""
        from src.data.database import ExperimentArtifactRecord

        with SessionLocal() as db:
            record = ExperimentArtifactRecord(
                experiment_id=experiment_id,
                artifact_type=artifact.artifact_type.value,
                artifact_json=json.dumps(artifact.payload),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            artifact_id = record.id

        logger.info(
            "Artifact attached to %s: type=%s",
            experiment_id,
            artifact.artifact_type.value,
        )
        return artifact_id

    # ── Queries ───────────────────────────────────────────────────────────────

    def get(self, experiment_id: str) -> ExperimentSummary | None:
        from src.data.database import ExperimentRecord, ExperimentArtifactRecord

        with SessionLocal() as db:
            row = (
                db.query(ExperimentRecord)
                .filter(ExperimentRecord.experiment_id == experiment_id)
                .first()
            )
            if not row:
                return None

            artifact_count = (
                db.query(ExperimentArtifactRecord)
                .filter(ExperimentArtifactRecord.experiment_id == experiment_id)
                .count()
            )

            return self._to_summary(row, artifact_count)

    def list_experiments(
        self,
        experiment_type: ExperimentType | None = None,
        status: ExperimentStatus | None = None,
        limit: int = 50,
    ) -> list[ExperimentSummary]:
        from src.data.database import ExperimentRecord

        with SessionLocal() as db:
            q = db.query(ExperimentRecord)
            if experiment_type:
                q = q.filter(
                    ExperimentRecord.experiment_type == experiment_type.value
                )
            if status:
                q = q.filter(ExperimentRecord.status == status.value)

            rows = (
                q.order_by(ExperimentRecord.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._to_summary(r) for r in rows]

    def get_artifacts(
        self, experiment_id: str
    ) -> list[ExperimentArtifactSummary]:
        from src.data.database import ExperimentArtifactRecord

        with SessionLocal() as db:
            rows = (
                db.query(ExperimentArtifactRecord)
                .filter(ExperimentArtifactRecord.experiment_id == experiment_id)
                .order_by(ExperimentArtifactRecord.created_at.asc())
                .all()
            )
            return [
                ExperimentArtifactSummary(
                    artifact_id=r.id,
                    experiment_id=r.experiment_id,
                    artifact_type=ArtifactType(r.artifact_type),
                    created_at=r.created_at,
                )
                for r in rows
            ]

    # ── Internals ─────────────────────────────────────────────────────────────

    def _update_status(
        self,
        experiment_id: str,
        status: ExperimentStatus,
        metrics: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        from src.data.database import ExperimentRecord

        with SessionLocal() as db:
            row = (
                db.query(ExperimentRecord)
                .filter(ExperimentRecord.experiment_id == experiment_id)
                .first()
            )
            if not row:
                logger.warning("Experiment %s not found", experiment_id)
                return

            row.status = status.value
            if status in (ExperimentStatus.COMPLETED, ExperimentStatus.FAILED):
                row.completed_at = datetime.now(timezone.utc)
            if metrics:
                row.metrics_json = json.dumps(metrics)
            if error:
                row.error_message = error
            db.commit()

        logger.info("Experiment %s → %s", experiment_id, status.value)

    @staticmethod
    def _to_summary(
        row: Any, artifact_count: int = 0
    ) -> ExperimentSummary:
        return ExperimentSummary(
            experiment_id=row.experiment_id,
            experiment_type=ExperimentType(row.experiment_type),
            name=row.name,
            status=ExperimentStatus(row.status),
            parent_experiment_id=row.parent_experiment_id,
            metrics=json.loads(row.metrics_json or "{}"),
            created_at=row.created_at,
            completed_at=row.completed_at,
            created_by=row.created_by or "auto",
            artifact_count=artifact_count,
        )
