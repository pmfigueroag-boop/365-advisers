"""
src/engines/compliance/audit_trail.py
--------------------------------------------------------------------------
Immutable Audit Trail — records every investment decision for compliance.

Required by SEC/FINRA/MiFID:
  - Every governor decision (approve/flag/reject) → timestamped log
  - Every rebalance → what changed, why, who triggered
  - Every parameter change → before/after with justification
  - Config snapshots → reproducibility at any point in time

Storage: append-only JSON Lines (.jsonl) file per day.
In production, replace with database + S3 archival.

Usage::

    trail = AuditTrail()
    trail.record_decision(decision)
    trail.record_rebalance(old_weights, new_weights, reason)
    entries = trail.query(signal_id="sig.momentum", limit=50)
"""

from __future__ import annotations

import json
import logging
import hashlib
from datetime import datetime, timezone, date
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.compliance.audit")


# ── Entry Types ──────────────────────────────────────────────────────────────

class AuditEntryType(str, Enum):
    GOVERNANCE_DECISION = "governance_decision"
    REBALANCE = "rebalance"
    PARAMETER_CHANGE = "parameter_change"
    SIGNAL_ACTIVATION = "signal_activation"
    SIGNAL_DEACTIVATION = "signal_deactivation"
    CONFIG_SNAPSHOT = "config_snapshot"
    MANUAL_OVERRIDE = "manual_override"
    ALERT_DISPATCHED = "alert_dispatched"


class AuditEntry(BaseModel):
    """A single immutable audit record."""
    entry_id: str = ""
    entry_type: AuditEntryType
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # Context
    signal_id: str | None = None
    ticker: str | None = None
    actor: str = "system"

    # Decision data
    action: str = ""
    reason: str = ""
    details: dict[str, Any] = Field(default_factory=dict)

    # Integrity
    previous_hash: str = ""
    entry_hash: str = ""

    def compute_hash(self, previous_hash: str = "") -> str:
        """Compute SHA-256 hash for tamper detection."""
        payload = (
            f"{self.entry_type.value}|{self.timestamp.isoformat()}|"
            f"{self.signal_id}|{self.ticker}|{self.action}|"
            f"{self.reason}|{json.dumps(self.details, sort_keys=True)}|"
            f"{previous_hash}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


class AuditQueryResult(BaseModel):
    """Result of an audit trail query."""
    entries: list[AuditEntry] = Field(default_factory=list)
    total_count: int = 0
    query_filters: dict[str, Any] = Field(default_factory=dict)


# ── Engine ───────────────────────────────────────────────────────────────────

class AuditTrail:
    """
    Append-only audit trail for compliance.

    Features:
      - Hash chain: each entry includes hash of previous (tamper detection)
      - JSON Lines storage: one file per day, human-readable
      - Query: filter by type, signal_id, ticker, date range
      - Config snapshots: record full system state for reproducibility

    Parameters
    ----------
    storage_dir : str | Path | None
        Directory for .jsonl files. If None, in-memory only.
    """

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        self._storage_dir = Path(storage_dir) if storage_dir else None
        self._entries: list[AuditEntry] = []
        self._last_hash: str = "genesis"

        if self._storage_dir:
            self._storage_dir.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        entry_type: AuditEntryType,
        action: str,
        reason: str = "",
        signal_id: str | None = None,
        ticker: str | None = None,
        actor: str = "system",
        details: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """
        Record an audit entry.

        Returns the recorded entry with hash chain.
        """
        entry = AuditEntry(
            entry_type=entry_type,
            action=action,
            reason=reason,
            signal_id=signal_id,
            ticker=ticker,
            actor=actor,
            details=details or {},
            previous_hash=self._last_hash,
        )

        # Compute hash chain
        entry.entry_hash = entry.compute_hash(self._last_hash)
        entry.entry_id = f"AUD-{entry.entry_hash}"
        self._last_hash = entry.entry_hash

        # Store
        self._entries.append(entry)

        if self._storage_dir:
            self._persist(entry)

        logger.info(
            "AUDIT: [%s] %s | %s | %s",
            entry.entry_type.value, entry.action,
            entry.signal_id or "", entry.reason[:80],
        )

        return entry

    def record_decision(
        self,
        signal_id: str,
        action: str,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Shortcut: record a governance decision."""
        return self.record(
            entry_type=AuditEntryType.GOVERNANCE_DECISION,
            action=action,
            reason=reason,
            signal_id=signal_id,
            details=details or {},
        )

    def record_rebalance(
        self,
        old_weights: dict[str, float],
        new_weights: dict[str, float],
        reason: str = "scheduled",
        actor: str = "system",
    ) -> AuditEntry:
        """Shortcut: record a portfolio rebalance."""
        # Compute turnover
        all_tickers = set(old_weights) | set(new_weights)
        turnover = sum(
            abs(new_weights.get(t, 0) - old_weights.get(t, 0))
            for t in all_tickers
        ) / 2

        return self.record(
            entry_type=AuditEntryType.REBALANCE,
            action="rebalance",
            reason=reason,
            actor=actor,
            details={
                "old_weights": old_weights,
                "new_weights": new_weights,
                "turnover": round(turnover, 4),
                "positions_added": [
                    t for t in new_weights if t not in old_weights
                ],
                "positions_removed": [
                    t for t in old_weights if t not in new_weights
                ],
            },
        )

    def record_config_snapshot(
        self,
        config: dict[str, Any],
        version: str = "",
    ) -> AuditEntry:
        """Snapshot full system configuration for reproducibility."""
        return self.record(
            entry_type=AuditEntryType.CONFIG_SNAPSHOT,
            action="config_snapshot",
            reason=f"System configuration v{version}" if version else "config_snapshot",
            details={"config": config, "version": version},
        )

    def query(
        self,
        entry_type: AuditEntryType | None = None,
        signal_id: str | None = None,
        ticker: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> AuditQueryResult:
        """Query audit entries with filters."""
        results = self._entries

        if entry_type:
            results = [e for e in results if e.entry_type == entry_type]
        if signal_id:
            results = [e for e in results if e.signal_id == signal_id]
        if ticker:
            results = [e for e in results if e.ticker == ticker]
        if since:
            results = [e for e in results if e.timestamp >= since]
        if until:
            results = [e for e in results if e.timestamp <= until]

        total = len(results)
        results = results[-limit:]  # Most recent first

        filters: dict[str, Any] = {}
        if entry_type:
            filters["entry_type"] = entry_type.value
        if signal_id:
            filters["signal_id"] = signal_id
        if ticker:
            filters["ticker"] = ticker

        return AuditQueryResult(
            entries=results,
            total_count=total,
            query_filters=filters,
        )

    def verify_chain(self) -> tuple[bool, int]:
        """
        Verify hash chain integrity.

        Returns (is_valid, first_broken_index).
        """
        prev_hash = "genesis"
        for i, entry in enumerate(self._entries):
            expected = entry.compute_hash(prev_hash)
            if entry.entry_hash != expected:
                logger.error(
                    "AUDIT: Chain broken at entry %d (%s): "
                    "expected=%s, got=%s",
                    i, entry.entry_id, expected, entry.entry_hash,
                )
                return False, i
            prev_hash = entry.entry_hash

        return True, len(self._entries)

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def _persist(self, entry: AuditEntry) -> None:
        """Persist entry to daily .jsonl file."""
        day_str = entry.timestamp.strftime("%Y-%m-%d")
        filepath = self._storage_dir / f"audit_{day_str}.jsonl"

        with open(filepath, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
