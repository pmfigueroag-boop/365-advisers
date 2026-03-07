"""
src/engines/online_learning/repository.py
──────────────────────────────────────────────────────────────────────────────
Persistence layer for online learning updates.
"""

from __future__ import annotations

import logging

from src.data.database import OnlineLearningRecord, SessionLocal

logger = logging.getLogger("365advisers.online_learning.repository")


class OnlineLearningRepository:
    """CRUD for online learning weight updates."""

    def save_updates(self, run_id: str, updates: list) -> int:
        """Persist weight updates for a run."""
        with SessionLocal() as db:
            count = 0
            for u in updates:
                rec = OnlineLearningRecord(
                    run_id=run_id,
                    signal_id=u.signal_id,
                    weight_before=u.weight_before,
                    weight_after=u.weight_after,
                    delta=u.delta,
                    raw_delta=u.raw_delta,
                    dampened=u.dampened,
                    observation_return=u.observation_return,
                    learning_rate_used=u.learning_rate_used,
                )
                db.add(rec)
                count += 1
            db.commit()
            logger.info("OL-REPO: Saved %d updates for run %s", count, run_id)
            return count

    def get_updates(self, run_id: str) -> list[dict]:
        """Get all updates for a run."""
        with SessionLocal() as db:
            rows = (
                db.query(OnlineLearningRecord)
                .filter(OnlineLearningRecord.run_id == run_id)
                .order_by(OnlineLearningRecord.id)
                .all()
            )
            return [self._to_dict(r) for r in rows]

    def get_latest_weights(self) -> list[dict]:
        """Get the most recent weight for each signal."""
        with SessionLocal() as db:
            from sqlalchemy import func
            subq = (
                db.query(
                    OnlineLearningRecord.signal_id,
                    func.max(OnlineLearningRecord.id).label("max_id"),
                )
                .group_by(OnlineLearningRecord.signal_id)
                .subquery()
            )
            rows = (
                db.query(OnlineLearningRecord)
                .join(subq, OnlineLearningRecord.id == subq.c.max_id)
                .all()
            )
            return [
                {"signal_id": r.signal_id, "weight": r.weight_after}
                for r in rows
            ]

    @staticmethod
    def _to_dict(row: OnlineLearningRecord) -> dict:
        return {
            "run_id": row.run_id,
            "signal_id": row.signal_id,
            "weight_before": row.weight_before,
            "weight_after": row.weight_after,
            "delta": row.delta,
            "raw_delta": row.raw_delta,
            "dampened": row.dampened,
            "observation_return": row.observation_return,
            "learning_rate_used": row.learning_rate_used,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
