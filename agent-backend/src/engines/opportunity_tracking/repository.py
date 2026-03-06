"""
src/engines/opportunity_tracking/repository.py
──────────────────────────────────────────────────────────────────────────────
CRUD operations for OpportunityPerformanceRecord.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from src.data.database import (
    OpportunityPerformanceRecord,
    SessionLocal,
)

logger = logging.getLogger("365advisers.opportunity_tracking.repository")


class OpportunityRepository:
    """Data access layer for opportunity performance tracking."""

    # ── Write ─────────────────────────────────────────────────────────────

    @staticmethod
    def save_opportunity(
        idea_uid: str,
        ticker: str,
        idea_type: str,
        confidence: str,
        signal_strength: float,
        price_at_gen: float,
        generated_at: datetime,
        opportunity_score: float | None = None,
        suggested_alloc: float | None = None,
    ) -> int:
        """Insert a new tracking record. Returns the record ID."""
        with SessionLocal() as db:
            record = OpportunityPerformanceRecord(
                idea_uid=idea_uid,
                ticker=ticker,
                idea_type=idea_type,
                confidence=confidence,
                signal_strength=signal_strength,
                opportunity_score=opportunity_score,
                suggested_alloc=suggested_alloc,
                price_at_gen=price_at_gen,
                generated_at=generated_at,
                tracking_status="pending",
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            logger.info(
                "OPP-REPO: Saved opportunity %s (%s) @ $%.2f",
                idea_uid, ticker, price_at_gen,
            )
            return record.id

    @staticmethod
    def update_returns(
        idea_uid: str,
        return_1d: float | None = None,
        return_5d: float | None = None,
        return_20d: float | None = None,
        return_60d: float | None = None,
        benchmark_return_20d: float | None = None,
        excess_return_20d: float | None = None,
        tracking_status: str = "partial",
    ) -> bool:
        """Update forward returns for a tracked idea."""
        with SessionLocal() as db:
            record = (
                db.query(OpportunityPerformanceRecord)
                .filter(OpportunityPerformanceRecord.idea_uid == idea_uid)
                .first()
            )
            if not record:
                return False

            if return_1d is not None:
                record.return_1d = return_1d
            if return_5d is not None:
                record.return_5d = return_5d
            if return_20d is not None:
                record.return_20d = return_20d
            if return_60d is not None:
                record.return_60d = return_60d
            if benchmark_return_20d is not None:
                record.benchmark_return_20d = benchmark_return_20d
            if excess_return_20d is not None:
                record.excess_return_20d = excess_return_20d

            record.tracking_status = tracking_status
            record.last_updated = datetime.now(timezone.utc)
            db.commit()
            return True

    # ── Read ──────────────────────────────────────────────────────────────

    @staticmethod
    def get_pending_updates(max_age_days: int = 90) -> list[OpportunityPerformanceRecord]:
        """Fetch records that still need forward return updates."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        with SessionLocal() as db:
            records = (
                db.query(OpportunityPerformanceRecord)
                .filter(
                    OpportunityPerformanceRecord.tracking_status.in_(["pending", "partial"]),
                    OpportunityPerformanceRecord.generated_at >= cutoff,
                )
                .order_by(OpportunityPerformanceRecord.generated_at.asc())
                .all()
            )
            # Detach from session
            return [_detach(r, db) for r in records]

    @staticmethod
    def get_by_type(
        idea_type: str | None = None,
        min_age_days: int = 20,
    ) -> list[OpportunityPerformanceRecord]:
        """Query records with sufficient age for performance summary."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=min_age_days)
        with SessionLocal() as db:
            query = db.query(OpportunityPerformanceRecord).filter(
                OpportunityPerformanceRecord.generated_at <= cutoff,
            )
            if idea_type:
                query = query.filter(
                    OpportunityPerformanceRecord.idea_type == idea_type,
                )
            records = query.order_by(
                OpportunityPerformanceRecord.generated_at.desc()
            ).limit(500).all()
            return [_detach(r, db) for r in records]

    @staticmethod
    def get_all_complete(min_age_days: int = 20) -> list[OpportunityPerformanceRecord]:
        """All records with complete 20D history."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=min_age_days)
        with SessionLocal() as db:
            records = (
                db.query(OpportunityPerformanceRecord)
                .filter(
                    OpportunityPerformanceRecord.generated_at <= cutoff,
                    OpportunityPerformanceRecord.return_20d.isnot(None),
                )
                .order_by(OpportunityPerformanceRecord.generated_at.desc())
                .limit(500)
                .all()
            )
            return [_detach(r, db) for r in records]

    @staticmethod
    def get_by_idea_uid(idea_uid: str) -> OpportunityPerformanceRecord | None:
        """Get tracking record for a specific idea."""
        with SessionLocal() as db:
            record = (
                db.query(OpportunityPerformanceRecord)
                .filter(OpportunityPerformanceRecord.idea_uid == idea_uid)
                .first()
            )
            if record:
                db.expunge(record)
            return record

    @staticmethod
    def count_all() -> int:
        """Total tracked opportunities."""
        with SessionLocal() as db:
            return db.query(OpportunityPerformanceRecord).count()


def _detach(record: OpportunityPerformanceRecord, db) -> OpportunityPerformanceRecord:
    """Detach a record from the session so it can be used outside."""
    db.expunge(record)
    return record
