"""
src/engines/governance/lineage.py
─────────────────────────────────────────────────────────────────────────────
ModelLineageTracker — Maintains a DAG of experiment dependencies, answering
questions like:
  • "Which backtest produced these signal weights?"
  • "What experiments depend on this walk-forward run?"
  • "Show me the full ancestry of the current production config."
"""

from __future__ import annotations

import logging
from typing import Any

from src.data.database import SessionLocal

from .models import ExperimentStatus, ExperimentType, LineageLink, LineageNode

logger = logging.getLogger("365advisers.governance.lineage")


class ModelLineageTracker:
    """DAG of experiment dependencies for institutional model lineage."""

    def link(self, edge: LineageLink) -> None:
        """Create a directed edge: source → target."""
        from src.data.database import ExperimentRecord

        with SessionLocal() as db:
            # Verify both experiments exist
            src = (
                db.query(ExperimentRecord)
                .filter(
                    ExperimentRecord.experiment_id
                    == edge.source_experiment_id
                )
                .first()
            )
            tgt = (
                db.query(ExperimentRecord)
                .filter(
                    ExperimentRecord.experiment_id
                    == edge.target_experiment_id
                )
                .first()
            )
            if not src or not tgt:
                logger.warning(
                    "Lineage link skipped — missing experiment: %s → %s",
                    edge.source_experiment_id,
                    edge.target_experiment_id,
                )
                return

            # If the parent_experiment_id is not already set on the target,
            # set it to the source.  The parent_experiment_id column captures
            # the single "primary" parent; lineage can be more complex, but
            # this keeps backward compat.
            if tgt.parent_experiment_id is None:
                tgt.parent_experiment_id = edge.source_experiment_id
                db.commit()

        logger.info(
            "Lineage: %s —[%s]→ %s",
            edge.source_experiment_id,
            edge.relationship,
            edge.target_experiment_id,
        )

    def get_parents(self, experiment_id: str) -> list[str]:
        """Return direct parent experiment IDs."""
        from src.data.database import ExperimentRecord

        with SessionLocal() as db:
            row = (
                db.query(ExperimentRecord)
                .filter(ExperimentRecord.experiment_id == experiment_id)
                .first()
            )
            if not row or not row.parent_experiment_id:
                return []
            return [row.parent_experiment_id]

    def get_children(self, experiment_id: str) -> list[str]:
        """Return direct child experiment IDs."""
        from src.data.database import ExperimentRecord

        with SessionLocal() as db:
            rows = (
                db.query(ExperimentRecord)
                .filter(
                    ExperimentRecord.parent_experiment_id == experiment_id
                )
                .all()
            )
            return [r.experiment_id for r in rows]

    def get_ancestry(self, experiment_id: str, max_depth: int = 10) -> list[LineageNode]:
        """Walk up the DAG from a given experiment.

        Returns a list of LineageNode objects representing the full ancestry
        chain, from the given experiment up to the root(s).
        """
        visited: set[str] = set()
        ancestry: list[LineageNode] = []
        queue = [experiment_id]
        depth = 0

        while queue and depth < max_depth:
            next_queue: list[str] = []
            for eid in queue:
                if eid in visited:
                    continue
                visited.add(eid)

                node = self._get_node(eid)
                if node:
                    ancestry.append(node)
                    next_queue.extend(node.parents)

            queue = next_queue
            depth += 1

        return ancestry

    def get_descendants(self, experiment_id: str, max_depth: int = 10) -> list[LineageNode]:
        """Walk down the DAG from a given experiment."""
        visited: set[str] = set()
        descendants: list[LineageNode] = []
        queue = [experiment_id]
        depth = 0

        while queue and depth < max_depth:
            next_queue: list[str] = []
            for eid in queue:
                if eid in visited:
                    continue
                visited.add(eid)

                node = self._get_node(eid)
                if node:
                    descendants.append(node)
                    next_queue.extend(node.children)

            queue = next_queue
            depth += 1

        return descendants

    # ── Internals ─────────────────────────────────────────────────────────────

    def _get_node(self, experiment_id: str) -> LineageNode | None:
        from src.data.database import ExperimentRecord

        with SessionLocal() as db:
            row = (
                db.query(ExperimentRecord)
                .filter(ExperimentRecord.experiment_id == experiment_id)
                .first()
            )
            if not row:
                return None

            parents = [row.parent_experiment_id] if row.parent_experiment_id else []

            children_rows = (
                db.query(ExperimentRecord.experiment_id)
                .filter(ExperimentRecord.parent_experiment_id == experiment_id)
                .all()
            )
            children = [c[0] for c in children_rows]

            return LineageNode(
                experiment_id=row.experiment_id,
                experiment_type=ExperimentType(row.experiment_type),
                name=row.name,
                status=ExperimentStatus(row.status),
                parents=parents,
                children=children,
            )
