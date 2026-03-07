"""
src/engines/walk_forward/repository.py
──────────────────────────────────────────────────────────────────────────────
Persistence layer for walk-forward validation runs.

Stores run metadata, fold definitions, and per-signal results in the
walk_forward_* tables.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from src.data.database import (
    SessionLocal,
    WalkForwardFoldRecord,
    WalkForwardRunRecord,
    WalkForwardSignalResultRecord,
)
from src.engines.walk_forward.models import (
    WalkForwardConfig,
    WalkForwardFold,
    WalkForwardRun,
    WFSignalFoldResult,
    WFSignalSummary,
)

logger = logging.getLogger("365advisers.walk_forward.repository")


class WalkForwardRepository:
    """CRUD for walk-forward runs, folds, and signal results."""

    # ── Write ─────────────────────────────────────────────────────────────

    def save_run(self, run: WalkForwardRun) -> None:
        """Persist a complete walk-forward run to the database."""
        with SessionLocal() as db:
            # 1. Run record
            run_rec = WalkForwardRunRecord(
                run_id=run.run_id,
                config_json=run.config.model_dump_json(),
                total_folds=run.total_folds,
                robust_signals_json=json.dumps(run.robust_signals),
                overfit_signals_json=json.dumps(run.overfit_signals),
                status=run.status,
                execution_time_s=run.execution_time_seconds,
                error_message=run.error_message,
            )
            db.add(run_rec)
            db.flush()  # so run_id is available for FK

            # 2. Fold records
            fold_id_map: dict[int, int] = {}  # fold_index → DB id
            for fold in run.folds:
                fold_rec = WalkForwardFoldRecord(
                    run_id=run.run_id,
                    fold_index=fold.fold_index,
                    train_start=fold.train_start.isoformat(),
                    train_end=fold.train_end.isoformat(),
                    test_start=fold.test_start.isoformat(),
                    test_end=fold.test_end.isoformat(),
                )
                db.add(fold_rec)
                db.flush()
                fold_id_map[fold.fold_index] = fold_rec.id

            # 3. Signal result records (from all summaries)
            for summary in run.signal_summaries:
                for fr in summary.fold_results:
                    fold_db_id = fold_id_map.get(fr.fold_index)
                    if fold_db_id is None:
                        continue
                    result_rec = WalkForwardSignalResultRecord(
                        fold_id=fold_db_id,
                        signal_id=fr.signal_id,
                        signal_name=fr.signal_name,
                        is_hit_rate=fr.is_hit_rate,
                        is_sharpe=fr.is_sharpe,
                        is_alpha=fr.is_alpha,
                        is_firings=fr.is_firings,
                        qualified=fr.qualified,
                        oos_hit_rate=fr.oos_hit_rate,
                        oos_sharpe=fr.oos_sharpe,
                        oos_alpha=fr.oos_alpha,
                        oos_firings=fr.oos_firings,
                    )
                    db.add(result_rec)

            db.commit()
            logger.info(
                "WF-REPO: Saved run %s (%d folds, %d signal summaries)",
                run.run_id, len(run.folds), len(run.signal_summaries),
            )

    # ── Read ──────────────────────────────────────────────────────────────

    def list_runs(self, limit: int = 20) -> list[dict]:
        """Return compact summaries of recent walk-forward runs."""
        with SessionLocal() as db:
            rows = (
                db.query(WalkForwardRunRecord)
                .order_by(WalkForwardRunRecord.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "run_id": r.run_id,
                    "total_folds": r.total_folds,
                    "status": r.status,
                    "execution_time_s": r.execution_time_s,
                    "robust_signals": json.loads(r.robust_signals_json or "[]"),
                    "overfit_signals": json.loads(r.overfit_signals_json or "[]"),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]

    def get_run_summary(self, run_id: str) -> dict | None:
        """Retrieve a run summary with fold and signal counts."""
        with SessionLocal() as db:
            run = (
                db.query(WalkForwardRunRecord)
                .filter(WalkForwardRunRecord.run_id == run_id)
                .first()
            )
            if not run:
                return None

            fold_count = (
                db.query(WalkForwardFoldRecord)
                .filter(WalkForwardFoldRecord.run_id == run_id)
                .count()
            )

            return {
                "run_id": run.run_id,
                "total_folds": run.total_folds,
                "status": run.status,
                "execution_time_s": run.execution_time_s,
                "robust_signals": json.loads(run.robust_signals_json or "[]"),
                "overfit_signals": json.loads(run.overfit_signals_json or "[]"),
                "config": json.loads(run.config_json or "{}"),
                "fold_count": fold_count,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "error_message": run.error_message,
            }

    def get_signal_results(self, run_id: str, signal_id: str) -> list[dict]:
        """Get per-fold results for a specific signal in a run."""
        with SessionLocal() as db:
            folds = (
                db.query(WalkForwardFoldRecord)
                .filter(WalkForwardFoldRecord.run_id == run_id)
                .all()
            )
            fold_ids = [f.id for f in folds]
            fold_map = {f.id: f for f in folds}

            if not fold_ids:
                return []

            results = (
                db.query(WalkForwardSignalResultRecord)
                .filter(
                    WalkForwardSignalResultRecord.fold_id.in_(fold_ids),
                    WalkForwardSignalResultRecord.signal_id == signal_id,
                )
                .all()
            )
            return [
                {
                    "fold_index": fold_map[r.fold_id].fold_index if r.fold_id in fold_map else -1,
                    "train_start": fold_map[r.fold_id].train_start if r.fold_id in fold_map else None,
                    "train_end": fold_map[r.fold_id].train_end if r.fold_id in fold_map else None,
                    "test_start": fold_map[r.fold_id].test_start if r.fold_id in fold_map else None,
                    "test_end": fold_map[r.fold_id].test_end if r.fold_id in fold_map else None,
                    "is_hit_rate": r.is_hit_rate,
                    "is_sharpe": r.is_sharpe,
                    "is_alpha": r.is_alpha,
                    "is_firings": r.is_firings,
                    "qualified": r.qualified,
                    "oos_hit_rate": r.oos_hit_rate,
                    "oos_sharpe": r.oos_sharpe,
                    "oos_alpha": r.oos_alpha,
                    "oos_firings": r.oos_firings,
                }
                for r in results
            ]
