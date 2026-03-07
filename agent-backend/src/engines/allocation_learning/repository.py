"""
src/engines/allocation_learning/repository.py
──────────────────────────────────────────────────────────────────────────────
Persistence layer for allocation learning outcomes.
"""

from __future__ import annotations

import logging

from src.data.database import AllocationLearningRecord, SessionLocal

logger = logging.getLogger("365advisers.allocation_learning.repository")


class AllocationLearningRepository:
    """CRUD for allocation learning outcomes."""

    def save_outcomes(
        self, run_id: str, outcomes: list, rewards: list[float],
    ) -> int:
        """Persist allocation outcomes for a run."""
        with SessionLocal() as db:
            count = 0
            for outcome, reward in zip(outcomes, rewards):
                rec = AllocationLearningRecord(
                    run_id=run_id,
                    ticker=outcome.ticker,
                    bucket_id=outcome.bucket_id,
                    allocation_pct=outcome.allocation_pct,
                    forward_return=outcome.forward_return,
                    reward=reward,
                    ucb_score=0.0,
                )
                db.add(rec)
                count += 1
            db.commit()
            logger.info("ALLOC-REPO: Saved %d outcomes for run %s", count, run_id)
            return count

    def get_outcomes(self, run_id: str) -> list[dict]:
        """Get all outcomes for a run."""
        with SessionLocal() as db:
            rows = (
                db.query(AllocationLearningRecord)
                .filter(AllocationLearningRecord.run_id == run_id)
                .order_by(AllocationLearningRecord.id)
                .all()
            )
            return [self._to_dict(r) for r in rows]

    def get_bucket_summary(self) -> list[dict]:
        """Get aggregate stats per bucket across all runs."""
        with SessionLocal() as db:
            from sqlalchemy import func
            rows = (
                db.query(
                    AllocationLearningRecord.bucket_id,
                    func.count(AllocationLearningRecord.id).label("count"),
                    func.avg(AllocationLearningRecord.reward).label("avg_reward"),
                    func.avg(AllocationLearningRecord.forward_return).label("avg_return"),
                )
                .group_by(AllocationLearningRecord.bucket_id)
                .all()
            )
            return [
                {
                    "bucket_id": r.bucket_id,
                    "count": r.count,
                    "avg_reward": round(float(r.avg_reward or 0), 4),
                    "avg_return": round(float(r.avg_return or 0), 6),
                }
                for r in rows
            ]

    @staticmethod
    def _to_dict(row: AllocationLearningRecord) -> dict:
        return {
            "run_id": row.run_id,
            "ticker": row.ticker,
            "bucket_id": row.bucket_id,
            "allocation_pct": row.allocation_pct,
            "forward_return": row.forward_return,
            "reward": row.reward,
            "ucb_score": row.ucb_score,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
