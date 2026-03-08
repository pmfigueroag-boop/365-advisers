"""
src/engines/experiment_tracking/tracker.py
─────────────────────────────────────────────────────────────────────────────
ResearchExperimentTracker — central experiment tracking system.

Wraps the existing ExperimentRegistry with research-specific features:
  - Tags, hypothesis, description
  - Data fingerprint
  - Search/filter by tags
  - Experiment tagging
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from .models import (
    ResearchExperimentCreate,
    ResearchExperimentSummary,
    ResearchExperimentType,
    compute_data_fingerprint,
)

logger = logging.getLogger("365advisers.experiment_tracking.tracker")

# ── In-memory store (mirrors governance ExperimentRegistry pattern) ───────────
# For production, this delegates to the governance ExperimentRegistry + DB.
# For standalone operation / testing, uses in-memory storage.

_experiments: dict[str, dict] = {}
_tags: dict[str, list[str]] = {}  # experiment_id → tags
_artifacts: dict[str, list[dict]] = {}  # experiment_id → artifacts


class ResearchExperimentTracker:
    """Central experiment tracking with research-specific extensions."""

    @staticmethod
    def register(payload: ResearchExperimentCreate) -> str:
        """Register a new research experiment. Returns experiment_id."""
        exp_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()

        record = {
            "experiment_id": exp_id,
            "experiment_type": payload.experiment_type.value,
            "name": payload.name,
            "description": payload.description,
            "author": payload.author,
            "hypothesis": payload.hypothesis,
            "tags": list(payload.tags),
            "status": "pending",
            "config_snapshot": payload.config_snapshot,
            "signal_versions": payload.signal_versions,
            "strategy_version": payload.strategy_version,
            "data_fingerprint": payload.data_fingerprint,
            "metrics": {},
            "parent_experiment_id": payload.parent_experiment_id,
            "child_experiment_ids": [],
            "artifact_count": 0,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "error": None,
        }
        _experiments[exp_id] = record
        _tags[exp_id] = list(payload.tags)
        _artifacts[exp_id] = []

        # Register parent→child link
        if payload.parent_experiment_id and payload.parent_experiment_id in _experiments:
            _experiments[payload.parent_experiment_id]["child_experiment_ids"].append(exp_id)

        logger.info("Experiment registered: %s (%s)", exp_id, payload.name)
        return exp_id

    @staticmethod
    def mark_running(experiment_id: str) -> None:
        if experiment_id in _experiments:
            _experiments[experiment_id]["status"] = "running"
            _experiments[experiment_id]["started_at"] = datetime.now(timezone.utc).isoformat()

    @staticmethod
    def mark_completed(experiment_id: str, metrics: dict[str, Any] | None = None) -> None:
        if experiment_id in _experiments:
            _experiments[experiment_id]["status"] = "completed"
            _experiments[experiment_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
            if metrics:
                _experiments[experiment_id]["metrics"] = metrics

    @staticmethod
    def mark_failed(experiment_id: str, error: str = "") -> None:
        if experiment_id in _experiments:
            _experiments[experiment_id]["status"] = "failed"
            _experiments[experiment_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
            _experiments[experiment_id]["error"] = error

    @staticmethod
    def attach_artifact(experiment_id: str, artifact_type: str, payload: dict) -> None:
        if experiment_id in _experiments:
            _artifacts.setdefault(experiment_id, []).append({
                "artifact_type": artifact_type,
                "payload": payload,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            _experiments[experiment_id]["artifact_count"] = len(_artifacts[experiment_id])

    @staticmethod
    def get(experiment_id: str) -> ResearchExperimentSummary | None:
        rec = _experiments.get(experiment_id)
        if not rec:
            return None
        return ResearchExperimentSummary(**{
            k: v for k, v in rec.items()
            if k in ResearchExperimentSummary.model_fields
        })

    @staticmethod
    def list_experiments(
        experiment_type: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        author: str | None = None,
        search: str | None = None,
        limit: int = 50,
    ) -> list[ResearchExperimentSummary]:
        """List experiments with enhanced filtering."""
        results = []
        for rec in _experiments.values():
            # Type filter
            if experiment_type and rec["experiment_type"] != experiment_type:
                continue
            # Status filter
            if status and rec["status"] != status:
                continue
            # Author filter
            if author and rec.get("author") != author:
                continue
            # Tags filter (all tags must match)
            if tags:
                exp_tags = set(rec.get("tags", []))
                if not all(t in exp_tags for t in tags):
                    continue
            # Search filter (name, description, hypothesis)
            if search:
                search_lower = search.lower()
                searchable = f"{rec.get('name', '')} {rec.get('description', '')} {rec.get('hypothesis', '')}".lower()
                if search_lower not in searchable:
                    continue

            results.append(ResearchExperimentSummary(**{
                k: v for k, v in rec.items()
                if k in ResearchExperimentSummary.model_fields
            }))

        # Sort by created_at descending
        results.sort(key=lambda x: x.created_at or "", reverse=True)
        return results[:limit]

    @staticmethod
    def tag_experiment(experiment_id: str, tags: list[str]) -> None:
        """Add tags to an experiment."""
        if experiment_id in _experiments:
            existing = set(_experiments[experiment_id].get("tags", []))
            existing.update(tags)
            _experiments[experiment_id]["tags"] = list(existing)
            _tags[experiment_id] = list(existing)

    @staticmethod
    def untag_experiment(experiment_id: str, tags: list[str]) -> None:
        """Remove tags from an experiment."""
        if experiment_id in _experiments:
            existing = set(_experiments[experiment_id].get("tags", []))
            existing -= set(tags)
            _experiments[experiment_id]["tags"] = list(existing)
            _tags[experiment_id] = list(existing)

    @staticmethod
    def get_lineage(experiment_id: str) -> dict:
        """Get parent/child lineage for an experiment."""
        rec = _experiments.get(experiment_id)
        if not rec:
            return {"error": "Experiment not found"}

        parents = []
        if rec.get("parent_experiment_id"):
            parent = _experiments.get(rec["parent_experiment_id"])
            if parent:
                parents.append({
                    "experiment_id": parent["experiment_id"],
                    "name": parent["name"],
                    "type": parent["experiment_type"],
                    "relationship": "produced_by",
                })

        children = []
        for child_id in rec.get("child_experiment_ids", []):
            child = _experiments.get(child_id)
            if child:
                children.append({
                    "experiment_id": child["experiment_id"],
                    "name": child["name"],
                    "type": child["experiment_type"],
                    "relationship": "child",
                })

        return {
            "experiment_id": experiment_id,
            "name": rec["name"],
            "type": rec["experiment_type"],
            "parents": parents,
            "children": children,
            "depth_up": len(parents),
            "depth_down": len(children),
        }

    @staticmethod
    def get_full_ancestry(experiment_id: str, max_depth: int = 10) -> list[dict]:
        """Walk up the lineage chain."""
        visited = set()
        ancestry = []
        queue = [experiment_id]
        depth = 0

        while queue and depth < max_depth:
            next_queue = []
            for eid in queue:
                if eid in visited:
                    continue
                visited.add(eid)
                rec = _experiments.get(eid)
                if rec:
                    ancestry.append({
                        "experiment_id": eid,
                        "name": rec["name"],
                        "type": rec["experiment_type"],
                        "status": rec["status"],
                        "depth": depth,
                    })
                    parent = rec.get("parent_experiment_id")
                    if parent:
                        next_queue.append(parent)
            queue = next_queue
            depth += 1

        return ancestry

    @staticmethod
    def clear():
        """Clear all experiments (for testing)."""
        _experiments.clear()
        _tags.clear()
        _artifacts.clear()
