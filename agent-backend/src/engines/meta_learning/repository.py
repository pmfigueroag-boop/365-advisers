"""
src/engines/meta_learning/repository.py
──────────────────────────────────────────────────────────────────────────────
Persistence layer for meta-learning recommendations.
"""

from __future__ import annotations

import logging

from src.data.database import MetaLearningRecord, SessionLocal

logger = logging.getLogger("365advisers.meta_learning.repository")


class MetaLearningRepository:
    """CRUD for meta-learning recommendations."""

    def save_recommendations(
        self,
        run_id: str,
        recommendations: list,
    ) -> int:
        """Persist recommendations for a run."""
        with SessionLocal() as db:
            count = 0
            for rec in recommendations:
                record = MetaLearningRecord(
                    run_id=run_id,
                    target_id=rec.target_id,
                    target_name=rec.target_name,
                    recommendation=rec.recommendation,
                    reason=rec.reason,
                    current_value=rec.current_value,
                    suggested_value=rec.suggested_value,
                    confidence=rec.confidence,
                    priority=rec.priority,
                )
                db.add(record)
                count += 1
            db.commit()
            logger.info("ML-REPO: Saved %d recommendations for run %s", count, run_id)
            return count

    def get_recommendations(self, run_id: str) -> list[dict]:
        """Get all recommendations for a run."""
        with SessionLocal() as db:
            rows = (
                db.query(MetaLearningRecord)
                .filter(MetaLearningRecord.run_id == run_id)
                .order_by(MetaLearningRecord.priority, MetaLearningRecord.confidence.desc())
                .all()
            )
            return [self._to_dict(r) for r in rows]

    def get_pending(self) -> list[dict]:
        """Get all unapplied recommendations."""
        with SessionLocal() as db:
            rows = (
                db.query(MetaLearningRecord)
                .filter(MetaLearningRecord.applied == False)
                .order_by(MetaLearningRecord.priority, MetaLearningRecord.confidence.desc())
                .all()
            )
            return [self._to_dict(r) for r in rows]

    def mark_applied(self, run_id: str) -> int:
        """Mark all recommendations in a run as applied."""
        with SessionLocal() as db:
            count = (
                db.query(MetaLearningRecord)
                .filter(MetaLearningRecord.run_id == run_id)
                .update({"applied": True})
            )
            db.commit()
            return count

    @staticmethod
    def _to_dict(row: MetaLearningRecord) -> dict:
        return {
            "run_id": row.run_id,
            "target_id": row.target_id,
            "target_name": row.target_name,
            "recommendation": row.recommendation,
            "reason": row.reason,
            "current_value": row.current_value,
            "suggested_value": row.suggested_value,
            "confidence": row.confidence,
            "priority": row.priority,
            "applied": row.applied,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
