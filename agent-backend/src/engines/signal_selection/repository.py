"""
src/engines/signal_selection/repository.py
──────────────────────────────────────────────────────────────────────────────
Persistence layer for signal redundancy analysis results.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.data.database import SignalRedundancyRecord, SessionLocal

logger = logging.getLogger("365advisers.signal_selection.repository")


class SignalSelectionRepository:
    """CRUD for signal redundancy profiles."""

    # ── Write ─────────────────────────────────────────────────────────────

    def save_profiles(
        self,
        run_id: str,
        profiles: list,
    ) -> int:
        """
        Persist redundancy profiles for a run.

        Parameters
        ----------
        run_id : str
        profiles : list[SignalRedundancyProfile]

        Returns
        -------
        int
            Number of saved records.
        """
        with SessionLocal() as db:
            count = 0
            for p in profiles:
                rec = SignalRedundancyRecord(
                    run_id=run_id,
                    signal_id=p.signal_id,
                    signal_name=p.signal_name,
                    max_correlation=p.max_correlation,
                    max_corr_partner=p.max_corr_partner,
                    max_mi=p.max_mi,
                    incremental_alpha=p.incremental_alpha,
                    redundancy_score=p.redundancy_score,
                    classification=p.classification.value,
                    recommended_weight=p.recommended_weight,
                )
                db.add(rec)
                count += 1
            db.commit()
            logger.info("SEL-REPO: Saved %d profiles for run %s", count, run_id)
            return count

    # ── Read ──────────────────────────────────────────────────────────────

    def get_profiles(self, run_id: str) -> list[dict]:
        """Get all redundancy profiles for a run."""
        with SessionLocal() as db:
            rows = (
                db.query(SignalRedundancyRecord)
                .filter(SignalRedundancyRecord.run_id == run_id)
                .order_by(SignalRedundancyRecord.redundancy_score.desc())
                .all()
            )
            return [self._to_dict(r) for r in rows]

    def get_signal_profile(self, signal_id: str) -> dict | None:
        """Get the latest redundancy profile for a signal."""
        with SessionLocal() as db:
            row = (
                db.query(SignalRedundancyRecord)
                .filter(SignalRedundancyRecord.signal_id == signal_id)
                .order_by(SignalRedundancyRecord.created_at.desc())
                .first()
            )
            if not row:
                return None
            return self._to_dict(row)

    @staticmethod
    def _to_dict(row: SignalRedundancyRecord) -> dict:
        return {
            "signal_id": row.signal_id,
            "signal_name": row.signal_name,
            "run_id": row.run_id,
            "max_correlation": row.max_correlation,
            "max_corr_partner": row.max_corr_partner,
            "max_mi": row.max_mi,
            "incremental_alpha": row.incremental_alpha,
            "redundancy_score": row.redundancy_score,
            "classification": row.classification,
            "recommended_weight": row.recommended_weight,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
