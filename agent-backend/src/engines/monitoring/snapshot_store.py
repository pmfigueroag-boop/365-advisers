"""
src/engines/monitoring/snapshot_store.py
──────────────────────────────────────────────────────────────────────────────
In-memory snapshot store for the Monitoring Engine.

Maintains the previous snapshot for each ticker to enable diff-based
change detection. Snapshots are kept in memory (not persisted) since
they are transient comparison points.
"""

from __future__ import annotations

from src.engines.monitoring.models import OpportunitySnapshot


class SnapshotStore:
    """Thread-safe in-memory store for opportunity snapshots."""

    _snapshots: dict[str, OpportunitySnapshot] = {}

    @classmethod
    def get(cls, ticker: str) -> OpportunitySnapshot | None:
        """Get the previous snapshot for a ticker."""
        return cls._snapshots.get(ticker)

    @classmethod
    def put(cls, snapshot: OpportunitySnapshot) -> None:
        """Store a snapshot, replacing the previous one."""
        cls._snapshots[snapshot.ticker] = snapshot

    @classmethod
    def get_all(cls) -> dict[str, OpportunitySnapshot]:
        """Get all stored snapshots."""
        return dict(cls._snapshots)

    @classmethod
    def clear(cls) -> None:
        """Clear all snapshots."""
        cls._snapshots.clear()

    @classmethod
    def count(cls) -> int:
        return len(cls._snapshots)
