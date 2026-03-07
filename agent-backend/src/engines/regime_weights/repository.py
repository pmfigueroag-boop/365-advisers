"""
src/engines/regime_weights/repository.py
──────────────────────────────────────────────────────────────────────────────
Persistence layer for regime-adaptive weight profiles.
"""

from __future__ import annotations

import json
import logging

from src.data.database import RegimeWeightRecord, SessionLocal

logger = logging.getLogger("365advisers.regime_weights.repository")


class RegimeWeightRepository:
    """CRUD for regime weight profiles."""

    def save_profiles(
        self,
        run_id: str,
        profiles: list,
    ) -> int:
        """
        Persist regime weight profiles for a run.

        Parameters
        ----------
        run_id : str
        profiles : list[RegimeWeightProfile]

        Returns
        -------
        int
            Number of saved records.
        """
        with SessionLocal() as db:
            count = 0
            for p in profiles:
                # Serialize regime_stats to JSON
                stats_json = json.dumps({
                    k: v.model_dump() for k, v in p.regime_stats.items()
                }) if p.regime_stats else "{}"

                rec = RegimeWeightRecord(
                    run_id=run_id,
                    signal_id=p.signal_id,
                    signal_name=p.signal_name,
                    current_regime=p.current_regime,
                    base_weight=p.base_weight,
                    regime_multiplier=p.current_multiplier,
                    effective_weight=p.effective_weight,
                    best_regime=p.best_regime,
                    worst_regime=p.worst_regime,
                    regime_stats_json=stats_json,
                )
                db.add(rec)
                count += 1
            db.commit()
            logger.info("RW-REPO: Saved %d profiles for run %s", count, run_id)
            return count

    def get_profiles(self, run_id: str) -> list[dict]:
        """Get all regime weight profiles for a run."""
        with SessionLocal() as db:
            rows = (
                db.query(RegimeWeightRecord)
                .filter(RegimeWeightRecord.run_id == run_id)
                .order_by(RegimeWeightRecord.effective_weight.desc())
                .all()
            )
            return [self._to_dict(r) for r in rows]

    def get_signal_profile(self, signal_id: str) -> dict | None:
        """Get the latest regime weight profile for a signal."""
        with SessionLocal() as db:
            row = (
                db.query(RegimeWeightRecord)
                .filter(RegimeWeightRecord.signal_id == signal_id)
                .order_by(RegimeWeightRecord.created_at.desc())
                .first()
            )
            if not row:
                return None
            return self._to_dict(row)

    @staticmethod
    def _to_dict(row: RegimeWeightRecord) -> dict:
        stats = {}
        if row.regime_stats_json:
            try:
                stats = json.loads(row.regime_stats_json)
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "signal_id": row.signal_id,
            "signal_name": row.signal_name,
            "run_id": row.run_id,
            "current_regime": row.current_regime,
            "base_weight": row.base_weight,
            "regime_multiplier": row.regime_multiplier,
            "effective_weight": row.effective_weight,
            "best_regime": row.best_regime,
            "worst_regime": row.worst_regime,
            "regime_stats": stats,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
