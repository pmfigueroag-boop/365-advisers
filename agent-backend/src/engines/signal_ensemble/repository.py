"""
src/engines/signal_ensemble/repository.py
──────────────────────────────────────────────────────────────────────────────
Persistence layer for signal ensemble analysis results.
"""

from __future__ import annotations

import json
import logging

from src.data.database import SignalEnsembleRecord, SessionLocal

logger = logging.getLogger("365advisers.signal_ensemble.repository")


class EnsembleRepository:
    """CRUD for signal ensemble profiles."""

    def save_ensembles(
        self,
        run_id: str,
        combinations: list,
    ) -> int:
        """Persist ensemble combinations for a run."""
        with SessionLocal() as db:
            count = 0
            for c in combinations:
                rec = SignalEnsembleRecord(
                    run_id=run_id,
                    signal_ids_json=json.dumps(c.signals),
                    co_fire_count=c.co_fire_count,
                    synergy_score=c.synergy_score,
                    stability=c.stability,
                    ensemble_score=c.ensemble_score,
                    joint_sharpe=c.joint_sharpe,
                    joint_hit_rate=c.joint_hit_rate,
                )
                db.add(rec)
                count += 1
            db.commit()
            logger.info("ENS-REPO: Saved %d ensembles for run %s", count, run_id)
            return count

    def get_ensembles(self, run_id: str) -> list[dict]:
        """Get all ensembles for a run."""
        with SessionLocal() as db:
            rows = (
                db.query(SignalEnsembleRecord)
                .filter(SignalEnsembleRecord.run_id == run_id)
                .order_by(SignalEnsembleRecord.ensemble_score.desc())
                .all()
            )
            return [self._to_dict(r) for r in rows]

    def get_top_ensembles(self, limit: int = 10) -> list[dict]:
        """Get the top ensembles across all runs."""
        with SessionLocal() as db:
            rows = (
                db.query(SignalEnsembleRecord)
                .order_by(SignalEnsembleRecord.ensemble_score.desc())
                .limit(limit)
                .all()
            )
            return [self._to_dict(r) for r in rows]

    @staticmethod
    def _to_dict(row: SignalEnsembleRecord) -> dict:
        signals = []
        if row.signal_ids_json:
            try:
                signals = json.loads(row.signal_ids_json)
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "run_id": row.run_id,
            "signals": signals,
            "co_fire_count": row.co_fire_count,
            "synergy_score": row.synergy_score,
            "stability": row.stability,
            "ensemble_score": row.ensemble_score,
            "joint_sharpe": row.joint_sharpe,
            "joint_hit_rate": row.joint_hit_rate,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
