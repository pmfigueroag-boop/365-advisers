"""
src/engines/governance/versioning.py
─────────────────────────────────────────────────────────────────────────────
SignalVersionManager — Maintains an immutable version history of signal
configurations (thresholds, weights, half_life, enabled status).

Every time a calibration or online-learning update modifies a signal's
parameters, a new version is snapshotted here.  This enables:
  • Point-in-time reconstruction of the signal set
  • Diff between any two versions
  • Rollback to a previous configuration
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from src.data.database import SessionLocal

from .models import SignalVersionCreate, SignalVersionSummary

logger = logging.getLogger("365advisers.governance.versioning")


class SignalVersionManager:
    """Versioned history of signal configurations."""

    def create_version(self, payload: SignalVersionCreate) -> int:
        """Snapshot the current config for a signal.  Returns version_id."""
        from src.data.database import SignalVersionRecord

        with SessionLocal() as db:
            # Find the latest version number for this signal
            latest = (
                db.query(SignalVersionRecord)
                .filter(SignalVersionRecord.signal_id == payload.signal_id)
                .order_by(SignalVersionRecord.version_number.desc())
                .first()
            )
            next_version = (latest.version_number + 1) if latest else 1

            # Close the previous version's effective window
            if latest and latest.effective_until is None:
                latest.effective_until = datetime.now(timezone.utc)

            record = SignalVersionRecord(
                signal_id=payload.signal_id,
                version_number=next_version,
                config_json=json.dumps(payload.config),
                effective_from=datetime.now(timezone.utc),
                produced_by_experiment=payload.produced_by_experiment,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            version_id = record.id

        logger.info(
            "Signal %s → v%d (experiment=%s)",
            payload.signal_id,
            next_version,
            payload.produced_by_experiment or "manual",
        )
        return version_id

    def get_current(self, signal_id: str) -> SignalVersionSummary | None:
        """Return the active (latest) version of a signal."""
        from src.data.database import SignalVersionRecord

        with SessionLocal() as db:
            row = (
                db.query(SignalVersionRecord)
                .filter(
                    SignalVersionRecord.signal_id == signal_id,
                    SignalVersionRecord.effective_until.is_(None),
                )
                .order_by(SignalVersionRecord.version_number.desc())
                .first()
            )
            return self._to_summary(row) if row else None

    def get_version(
        self, signal_id: str, version_number: int
    ) -> SignalVersionSummary | None:
        """Return a specific version of a signal's config."""
        from src.data.database import SignalVersionRecord

        with SessionLocal() as db:
            row = (
                db.query(SignalVersionRecord)
                .filter(
                    SignalVersionRecord.signal_id == signal_id,
                    SignalVersionRecord.version_number == version_number,
                )
                .first()
            )
            return self._to_summary(row) if row else None

    def list_versions(
        self, signal_id: str, limit: int = 20
    ) -> list[SignalVersionSummary]:
        """Return the version history for a signal (newest first)."""
        from src.data.database import SignalVersionRecord

        with SessionLocal() as db:
            rows = (
                db.query(SignalVersionRecord)
                .filter(SignalVersionRecord.signal_id == signal_id)
                .order_by(SignalVersionRecord.version_number.desc())
                .limit(limit)
                .all()
            )
            return [self._to_summary(r) for r in rows]

    def diff(
        self, signal_id: str, v1: int, v2: int
    ) -> dict[str, Any]:
        """Return the diff between two versions of a signal config."""
        ver1 = self.get_version(signal_id, v1)
        ver2 = self.get_version(signal_id, v2)

        if not ver1 or not ver2:
            return {"error": "One or both versions not found"}

        changes: dict[str, Any] = {}
        all_keys = set(ver1.config.keys()) | set(ver2.config.keys())
        for key in sorted(all_keys):
            old_val = ver1.config.get(key)
            new_val = ver2.config.get(key)
            if old_val != new_val:
                changes[key] = {"from": old_val, "to": new_val}

        return {
            "signal_id": signal_id,
            "from_version": v1,
            "to_version": v2,
            "changes": changes,
        }

    def snapshot_all_signals(
        self, experiment_id: str | None = None
    ) -> dict[str, Any]:
        """Take a snapshot of all current signal configs.
        Returns a dict keyed by signal_id with the current config.
        Useful for freezing the signal set at experiment start.
        """
        from src.data.database import SignalVersionRecord

        with SessionLocal() as db:
            rows = (
                db.query(SignalVersionRecord)
                .filter(SignalVersionRecord.effective_until.is_(None))
                .order_by(SignalVersionRecord.signal_id)
                .all()
            )
            return {
                r.signal_id: json.loads(r.config_json or "{}")
                for r in rows
            }

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _to_summary(row: Any) -> SignalVersionSummary:
        return SignalVersionSummary(
            version_id=row.id,
            signal_id=row.signal_id,
            version_number=row.version_number,
            config=json.loads(row.config_json or "{}"),
            effective_from=row.effective_from,
            effective_until=row.effective_until,
            produced_by_experiment=row.produced_by_experiment,
        )
