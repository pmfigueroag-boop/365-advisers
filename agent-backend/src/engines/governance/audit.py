"""
src/engines/governance/audit.py
─────────────────────────────────────────────────────────────────────────────
AuditLogger — Append-only, immutable audit trail for all governance-relevant
events: experiment lifecycle, signal version changes, weight updates,
calibrations, and administrative actions.

This log is critical for institutional compliance and post-mortem analysis.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from src.data.database import SessionLocal

from .models import AuditAction, AuditEntry

logger = logging.getLogger("365advisers.governance.audit")


class AuditLogger:
    """Immutable audit trail for the governance layer.

    All writes are append-only.  No update or delete operations exist.
    """

    def log(self, entry: AuditEntry) -> int:
        """Record an audit event.  Returns the audit entry ID."""
        from src.data.database import GovernanceAuditRecord

        with SessionLocal() as db:
            record = GovernanceAuditRecord(
                action=entry.action.value,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                details_json=json.dumps(entry.details),
                performed_by=entry.performed_by,
                timestamp=entry.timestamp or datetime.now(timezone.utc),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            entry_id = record.id

        logger.info(
            "AUDIT: %s on %s/%s by %s",
            entry.action.value,
            entry.entity_type,
            entry.entity_id,
            entry.performed_by,
        )
        return entry_id

    def query(
        self,
        entity_type: str | None = None,
        entity_id: str | None = None,
        action: AuditAction | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query the audit trail with optional filters."""
        from src.data.database import GovernanceAuditRecord

        with SessionLocal() as db:
            q = db.query(GovernanceAuditRecord)

            if entity_type:
                q = q.filter(GovernanceAuditRecord.entity_type == entity_type)
            if entity_id:
                q = q.filter(GovernanceAuditRecord.entity_id == entity_id)
            if action:
                q = q.filter(GovernanceAuditRecord.action == action.value)

            rows = (
                q.order_by(GovernanceAuditRecord.timestamp.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": r.id,
                    "action": r.action,
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "details": json.loads(r.details_json or "{}"),
                    "performed_by": r.performed_by,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                }
                for r in rows
            ]

    def get_entity_history(self, entity_type: str, entity_id: str) -> list[dict]:
        """Get the complete audit history for a specific entity."""
        return self.query(entity_type=entity_type, entity_id=entity_id, limit=500)

    # ── Convenience methods ───────────────────────────────────────────────────

    def log_experiment_created(
        self, experiment_id: str, experiment_type: str, name: str
    ) -> int:
        return self.log(
            AuditEntry(
                action=AuditAction.EXPERIMENT_CREATED,
                entity_type="experiment",
                entity_id=experiment_id,
                details={"type": experiment_type, "name": name},
            )
        )

    def log_experiment_completed(
        self, experiment_id: str, metrics: dict | None = None
    ) -> int:
        return self.log(
            AuditEntry(
                action=AuditAction.EXPERIMENT_COMPLETED,
                entity_type="experiment",
                entity_id=experiment_id,
                details={"metrics_summary": metrics or {}},
            )
        )

    def log_signal_version(
        self,
        signal_id: str,
        version: int,
        config: dict,
        experiment_id: str | None = None,
    ) -> int:
        return self.log(
            AuditEntry(
                action=AuditAction.SIGNAL_VERSION_CREATED,
                entity_type="signal",
                entity_id=signal_id,
                details={
                    "version": version,
                    "config": config,
                    "experiment_id": experiment_id,
                },
            )
        )

    def log_weight_updated(
        self,
        signal_id: str,
        old_weight: float,
        new_weight: float,
        source: str = "auto",
    ) -> int:
        return self.log(
            AuditEntry(
                action=AuditAction.WEIGHT_UPDATED,
                entity_type="signal",
                entity_id=signal_id,
                details={
                    "old_weight": old_weight,
                    "new_weight": new_weight,
                    "source": source,
                },
            )
        )

    def log_calibration_applied(
        self,
        signal_id: str,
        parameter: str,
        old_value: float,
        new_value: float,
        run_id: str | None = None,
    ) -> int:
        return self.log(
            AuditEntry(
                action=AuditAction.CALIBRATION_APPLIED,
                entity_type="signal",
                entity_id=signal_id,
                details={
                    "parameter": parameter,
                    "old_value": old_value,
                    "new_value": new_value,
                    "run_id": run_id,
                },
            )
        )
