"""
src/engines/strategy/version_history.py
─────────────────────────────────────────────────────────────────────────────
StrategyVersionHistory — track strategy parameter changes over time.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from src.data.database import SessionLocal

logger = logging.getLogger("365advisers.strategy.version_history")


class StrategyVersionHistory:
    """Track and compare strategy configuration changes."""

    @staticmethod
    def record_version(
        strategy_id: str,
        version: int,
        config: dict,
        reason: str = "",
        author: str = "system",
    ) -> str:
        """Record a new strategy version snapshot.

        Uses the governance experiment_artifacts table for storage.
        """
        from src.data.database import ExperimentArtifact
        import uuid

        artifact_id = uuid.uuid4().hex[:12]
        with SessionLocal() as db:
            record = ExperimentArtifact(
                artifact_id=artifact_id,
                experiment_id=f"strategy_{strategy_id}",
                artifact_type="strategy_version",
                name=f"v{version}",
                data_json=json.dumps({
                    "strategy_id": strategy_id,
                    "version": version,
                    "config": config,
                    "reason": reason,
                    "author": author,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }),
            )
            db.add(record)
            db.commit()

        logger.info("Strategy %s version %d recorded", strategy_id, version)
        return artifact_id

    @staticmethod
    def get_version_history(strategy_id: str) -> list[dict]:
        """Get all version snapshots for a strategy."""
        from src.data.database import ExperimentArtifact

        with SessionLocal() as db:
            rows = (
                db.query(ExperimentArtifact)
                .filter(
                    ExperimentArtifact.experiment_id == f"strategy_{strategy_id}",
                    ExperimentArtifact.artifact_type == "strategy_version",
                )
                .order_by(ExperimentArtifact.created_at.desc())
                .all()
            )
            return [json.loads(r.data_json) for r in rows]

    @staticmethod
    def get_version(strategy_id: str, version: int) -> dict | None:
        """Get a specific version snapshot."""
        history = StrategyVersionHistory.get_version_history(strategy_id)
        for entry in history:
            if entry.get("version") == version:
                return entry
        return None

    @staticmethod
    def compare_versions(strategy_id: str, v1: int, v2: int) -> dict:
        """Compare two strategy versions and return the diff."""
        ver1 = StrategyVersionHistory.get_version(strategy_id, v1)
        ver2 = StrategyVersionHistory.get_version(strategy_id, v2)

        if not ver1 or not ver2:
            return {"error": "One or both versions not found"}

        cfg1 = ver1.get("config", {})
        cfg2 = ver2.get("config", {})

        diff = _compute_config_diff(cfg1, cfg2)

        return {
            "strategy_id": strategy_id,
            "version_a": v1,
            "version_b": v2,
            "changes": diff,
            "change_count": len(diff),
        }


def _compute_config_diff(a: dict, b: dict, prefix: str = "") -> list[dict]:
    """Compute flat diff between two config dicts."""
    changes = []
    all_keys = set(list(a.keys()) + list(b.keys()))

    for key in sorted(all_keys):
        path = f"{prefix}.{key}" if prefix else key
        val_a = a.get(key)
        val_b = b.get(key)

        if val_a == val_b:
            continue

        if isinstance(val_a, dict) and isinstance(val_b, dict):
            changes.extend(_compute_config_diff(val_a, val_b, path))
        else:
            changes.append({
                "path": path,
                "old": val_a,
                "new": val_b,
            })

    return changes
