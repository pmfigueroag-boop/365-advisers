"""
src/engines/signal_discovery/repository.py
──────────────────────────────────────────────────────────────────────────────
Persistence layer for signal discovery candidates.
"""

from __future__ import annotations

import logging

from src.data.database import SignalCandidateRecord, SessionLocal

logger = logging.getLogger("365advisers.signal_discovery.repository")


class SignalDiscoveryRepository:
    """CRUD for signal discovery candidates."""

    def save_candidates(self, run_id: str, candidates: list) -> int:
        """Persist discovered candidates for a run."""
        with SessionLocal() as db:
            count = 0
            for c in candidates:
                rec = SignalCandidateRecord(
                    run_id=run_id,
                    candidate_id=c.candidate_id,
                    name=c.name,
                    feature_formula=c.feature_formula,
                    direction=c.direction,
                    threshold=c.threshold,
                    category=c.category,
                    information_coefficient=c.information_coefficient,
                    hit_rate=c.hit_rate,
                    sharpe_ratio=c.sharpe_ratio,
                    sample_size=c.sample_size,
                    stability=c.stability,
                    p_value=c.p_value,
                    adjusted_p_value=c.adjusted_p_value,
                    status=c.status,
                )
                db.add(rec)
                count += 1
            db.commit()
            logger.info("DISC-REPO: Saved %d candidates for run %s", count, run_id)
            return count

    def get_candidates(self, run_id: str) -> list[dict]:
        """Get all candidates for a run."""
        with SessionLocal() as db:
            rows = (
                db.query(SignalCandidateRecord)
                .filter(SignalCandidateRecord.run_id == run_id)
                .order_by(SignalCandidateRecord.information_coefficient.desc())
                .all()
            )
            return [self._to_dict(r) for r in rows]

    def get_promoted(self) -> list[dict]:
        """Get all promoted candidates across all runs."""
        with SessionLocal() as db:
            rows = (
                db.query(SignalCandidateRecord)
                .filter(SignalCandidateRecord.status == "promoted")
                .order_by(SignalCandidateRecord.information_coefficient.desc())
                .all()
            )
            return [self._to_dict(r) for r in rows]

    @staticmethod
    def _to_dict(row: SignalCandidateRecord) -> dict:
        return {
            "run_id": row.run_id,
            "candidate_id": row.candidate_id,
            "name": row.name,
            "feature_formula": row.feature_formula,
            "direction": row.direction,
            "threshold": row.threshold,
            "category": row.category,
            "information_coefficient": row.information_coefficient,
            "hit_rate": row.hit_rate,
            "sharpe_ratio": row.sharpe_ratio,
            "sample_size": row.sample_size,
            "stability": row.stability,
            "p_value": row.p_value,
            "adjusted_p_value": row.adjusted_p_value,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
