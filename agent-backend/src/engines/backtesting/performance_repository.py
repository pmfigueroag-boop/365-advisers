"""
src/engines/backtesting/performance_repository.py
──────────────────────────────────────────────────────────────────────────────
Persistence layer for signal performance events and calibration history.

Extends the BacktestRepository with event-level storage and calibration
audit trail.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone

from src.data.database import (
    SessionLocal,
    SignalPerformanceEventRecord,
    SignalCalibrationHistoryRecord,
)
from src.engines.backtesting.models import (
    CalibrationRecord,
    SignalEvent,
    SignalPerformanceEvent,
)

logger = logging.getLogger("365advisers.backtesting.performance_repository")


class SignalPerformanceRepository:
    """CRUD for signal performance events and calibration history."""

    # ── Events ────────────────────────────────────────────────────────────

    @staticmethod
    def save_events(
        events: list[SignalEvent],
        run_id: str,
        signal_names: dict[str, str] | None = None,
    ) -> int:
        """
        Batch-insert signal firing events.

        Parameters
        ----------
        events : list[SignalEvent]
            Signal events from the backtesting engine.
        run_id : str
            The backtest run ID.
        signal_names : dict | None
            Optional {signal_id: name} lookup.

        Returns
        -------
        int
            Number of events persisted.
        """
        if not events:
            return 0

        names = signal_names or {}
        with SessionLocal() as db:
            rows = []
            for e in events:
                rows.append(SignalPerformanceEventRecord(
                    signal_id=e.signal_id,
                    signal_name=names.get(e.signal_id, ""),
                    ticker=e.ticker,
                    fired_date=e.fired_date.isoformat(),
                    strength=e.strength.value if hasattr(e.strength, "value") else str(e.strength),
                    confidence=e.confidence,
                    value=e.value,
                    price_at_fire=e.price_at_fire,
                    forward_returns_json=json.dumps(
                        {str(k): round(v, 6) for k, v in e.forward_returns.items()}
                    ),
                    benchmark_returns_json=json.dumps(
                        {str(k): round(v, 6) for k, v in e.benchmark_returns.items()}
                    ),
                    excess_returns_json=json.dumps(
                        {str(k): round(v, 6) for k, v in e.excess_returns.items()}
                    ),
                    run_id=run_id,
                ))

            db.bulk_save_objects(rows)
            db.commit()
            count = len(rows)

        logger.info(f"PERF-REPO: Saved {count} events for run {run_id}")
        return count

    @staticmethod
    def get_events(
        signal_id: str,
        ticker: str | None = None,
        limit: int = 500,
    ) -> list[SignalPerformanceEvent]:
        """Query events for a signal, optionally filtered by ticker."""
        with SessionLocal() as db:
            query = (
                db.query(SignalPerformanceEventRecord)
                .filter(SignalPerformanceEventRecord.signal_id == signal_id)
            )
            if ticker:
                query = query.filter(
                    SignalPerformanceEventRecord.ticker == ticker.upper()
                )
            rows = (
                query
                .order_by(SignalPerformanceEventRecord.fired_date.desc())
                .limit(limit)
                .all()
            )
            return [SignalPerformanceRepository._row_to_event(r) for r in rows]

    @staticmethod
    def get_events_by_ticker(
        ticker: str,
        limit: int = 500,
    ) -> list[SignalPerformanceEvent]:
        """All signal events for a ticker."""
        with SessionLocal() as db:
            rows = (
                db.query(SignalPerformanceEventRecord)
                .filter(SignalPerformanceEventRecord.ticker == ticker.upper())
                .order_by(SignalPerformanceEventRecord.fired_date.desc())
                .limit(limit)
                .all()
            )
            return [SignalPerformanceRepository._row_to_event(r) for r in rows]

    @staticmethod
    def count_events(signal_id: str) -> int:
        """Count total events for a signal."""
        with SessionLocal() as db:
            return (
                db.query(SignalPerformanceEventRecord)
                .filter(SignalPerformanceEventRecord.signal_id == signal_id)
                .count()
            )

    # ── Calibration ───────────────────────────────────────────────────────

    @staticmethod
    def save_calibration(record: CalibrationRecord) -> None:
        """Log a calibration change."""
        with SessionLocal() as db:
            row = SignalCalibrationHistoryRecord(
                signal_id=record.signal_id,
                parameter=record.parameter,
                old_value=record.old_value,
                new_value=record.new_value,
                evidence=record.evidence,
                run_id=record.run_id,
                applied_by=record.applied_by,
            )
            db.add(row)
            db.commit()
        logger.info(
            f"PERF-REPO: Calibration logged for {record.signal_id} "
            f"({record.parameter}: {record.old_value} → {record.new_value})"
        )

    @staticmethod
    def get_calibration_history(
        signal_id: str | None = None,
        limit: int = 100,
    ) -> list[CalibrationRecord]:
        """Calibration audit trail, optionally filtered by signal."""
        with SessionLocal() as db:
            query = db.query(SignalCalibrationHistoryRecord)
            if signal_id:
                query = query.filter(
                    SignalCalibrationHistoryRecord.signal_id == signal_id
                )
            rows = (
                query
                .order_by(SignalCalibrationHistoryRecord.applied_at.desc())
                .limit(limit)
                .all()
            )
            return [
                CalibrationRecord(
                    signal_id=r.signal_id,
                    parameter=r.parameter,
                    old_value=r.old_value,
                    new_value=r.new_value,
                    evidence=r.evidence or "",
                    run_id=r.run_id or "",
                    applied_at=r.applied_at or datetime.now(timezone.utc),
                    applied_by=r.applied_by or "auto",
                )
                for r in rows
            ]

    @staticmethod
    def get_last_calibration_date(signal_id: str) -> datetime | None:
        """Get the most recent calibration timestamp for a signal."""
        with SessionLocal() as db:
            row = (
                db.query(SignalCalibrationHistoryRecord)
                .filter(SignalCalibrationHistoryRecord.signal_id == signal_id)
                .order_by(SignalCalibrationHistoryRecord.applied_at.desc())
                .first()
            )
            return row.applied_at if row else None

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_event(row: SignalPerformanceEventRecord) -> SignalPerformanceEvent:
        """Convert a DB row to a Pydantic model."""
        def _load(raw: str) -> dict[int, float]:
            data = json.loads(raw or "{}")
            return {int(k): float(v) for k, v in data.items()}

        return SignalPerformanceEvent(
            signal_id=row.signal_id,
            signal_name=row.signal_name or "",
            ticker=row.ticker,
            fired_date=date.fromisoformat(row.fired_date),
            strength=row.strength,
            confidence=row.confidence or 0.0,
            value=row.value or 0.0,
            price_at_fire=row.price_at_fire or 0.0,
            forward_returns=_load(row.forward_returns_json),
            benchmark_returns=_load(row.benchmark_returns_json),
            excess_returns=_load(row.excess_returns_json),
            run_id=row.run_id or "",
        )
