"""
src/engines/concept_drift/repository.py
──────────────────────────────────────────────────────────────────────────────
Persistence layer for concept drift alerts.
"""

from __future__ import annotations

import json
import logging

from src.data.database import ConceptDriftRecord, SessionLocal

logger = logging.getLogger("365advisers.concept_drift.repository")


class ConceptDriftRepository:
    """CRUD for concept drift alerts."""

    def save_alerts(self, run_id: str, alerts: list) -> int:
        """Persist drift alerts for a run."""
        with SessionLocal() as db:
            count = 0
            for alert in alerts:
                detections_json = json.dumps(
                    [d.model_dump() for d in alert.detections],
                )
                rec = ConceptDriftRecord(
                    run_id=run_id,
                    signal_id=alert.signal_id,
                    severity=alert.severity,
                    active_detectors=alert.active_detectors,
                    drift_score=alert.drift_score,
                    detections_json=detections_json,
                    recommended_action=alert.recommended_action,
                )
                db.add(rec)
                count += 1
            db.commit()
            logger.info("DRIFT-REPO: Saved %d alerts for run %s", count, run_id)
            return count

    def get_alerts(self, run_id: str) -> list[dict]:
        """Get all alerts for a run."""
        with SessionLocal() as db:
            rows = (
                db.query(ConceptDriftRecord)
                .filter(ConceptDriftRecord.run_id == run_id)
                .order_by(ConceptDriftRecord.drift_score.desc())
                .all()
            )
            return [self._to_dict(r) for r in rows]

    def get_active_alerts(self, min_severity: str = "info") -> list[dict]:
        """Get currently active alerts above a minimum severity."""
        severity_order = {"info": 0, "warning": 1, "critical": 2}
        min_level = severity_order.get(min_severity, 0)

        with SessionLocal() as db:
            rows = (
                db.query(ConceptDriftRecord)
                .filter(ConceptDriftRecord.active_detectors > 0)
                .order_by(ConceptDriftRecord.drift_score.desc())
                .all()
            )
            results = []
            for r in rows:
                level = severity_order.get(r.severity, 0)
                if level >= min_level:
                    results.append(self._to_dict(r))
            return results

    @staticmethod
    def _to_dict(row: ConceptDriftRecord) -> dict:
        detections = []
        if row.detections_json:
            try:
                detections = json.loads(row.detections_json)
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "run_id": row.run_id,
            "signal_id": row.signal_id,
            "severity": row.severity,
            "active_detectors": row.active_detectors,
            "drift_score": row.drift_score,
            "detections": detections,
            "recommended_action": row.recommended_action,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
