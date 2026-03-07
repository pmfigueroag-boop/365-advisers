"""
src/engines/scorecard/tracker.py
─────────────────────────────────────────────────────────────────────────────
PerformanceTracker — Captures entry prices at signal/idea generation time
and schedules forward return updates.

This module coordinates with the existing OpportunityPerformanceRecord and
SignalPerformanceEventRecord tables to ensure live P&L tracking.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.data.database import SessionLocal

logger = logging.getLogger("365advisers.scorecard.tracker")


class PerformanceTracker:
    """Tracks entry prices and fills forward returns for live P&L."""

    def record_signal_fire(
        self,
        signal_id: str,
        signal_name: str,
        ticker: str,
        strength: str,
        confidence: float,
        price: float,
    ) -> int:
        """Record a live signal fire with entry price for future P&L calc.

        Returns the record ID.
        """
        from src.data.database import LiveSignalTrackingRecord

        with SessionLocal() as db:
            record = LiveSignalTrackingRecord(
                signal_id=signal_id,
                signal_name=signal_name,
                ticker=ticker,
                strength=strength,
                confidence=confidence,
                entry_price=price,
                fired_at=datetime.now(timezone.utc),
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            record_id = record.id

        logger.info("Tracked signal fire: %s on %s @ $%.2f", signal_id, ticker, price)
        return record_id

    def update_forward_returns(self, current_prices: dict[str, float]) -> int:
        """Update forward returns for all tracked signals using current prices.

        Args:
            current_prices: Dict of ticker → current price.

        Returns:
            Number of records updated.
        """
        from src.data.database import LiveSignalTrackingRecord

        updated = 0
        now = datetime.now(timezone.utc)

        with SessionLocal() as db:
            # Get all incomplete tracking records
            records = (
                db.query(LiveSignalTrackingRecord)
                .filter(LiveSignalTrackingRecord.tracking_complete == False)
                .all()
            )

            for record in records:
                price = current_prices.get(record.ticker)
                if price is None or record.entry_price is None:
                    continue

                entry = record.entry_price
                ret = (price - entry) / entry if entry > 0 else 0.0

                days_elapsed = (now - record.fired_at).days if record.fired_at else 0

                # Fill in the appropriate horizon
                if days_elapsed >= 1 and record.return_1d is None:
                    record.return_1d = ret
                    updated += 1
                if days_elapsed >= 5 and record.return_5d is None:
                    record.return_5d = ret
                    updated += 1
                if days_elapsed >= 20 and record.return_20d is None:
                    record.return_20d = ret
                    updated += 1
                if days_elapsed >= 60 and record.return_60d is None:
                    record.return_60d = ret
                    updated += 1

                # Mark complete when all horizons are filled
                if all([
                    record.return_1d is not None,
                    record.return_5d is not None,
                    record.return_20d is not None,
                    record.return_60d is not None,
                ]):
                    record.tracking_complete = True

                record.last_updated = now

            db.commit()

        logger.info("Updated forward returns: %d fields across %d records", updated, len(records))
        return updated

    def get_pending_tickers(self) -> list[str]:
        """Return list of tickers that need price updates."""
        from src.data.database import LiveSignalTrackingRecord

        with SessionLocal() as db:
            rows = (
                db.query(LiveSignalTrackingRecord.ticker)
                .filter(LiveSignalTrackingRecord.tracking_complete == False)
                .distinct()
                .all()
            )
            return [r[0] for r in rows]
