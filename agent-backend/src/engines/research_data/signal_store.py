"""
src/engines/research_data/signal_store.py
─────────────────────────────────────────────────────────────────────────────
SignalStore — historical record of signal fires with full context.

Provides query capabilities for research: by ticker, by signal, by date
range, by category. Used by Signal Lab and Strategy Backtester.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Optional

from src.data.database import SessionLocal
from .models import SignalHistoryRecord

logger = logging.getLogger(__name__)


class SignalStore:
    """Historical signal fire store for quant research."""

    # ── Write ────────────────────────────────────────────────────────────

    @staticmethod
    def record_fire(
        signal_id: str,
        ticker: str,
        fire_date: date | str,
        strength: str,
        category: str,
        *,
        signal_name: str = "",
        confidence: float = 0.0,
        direction: str = "long",
        value: float | None = None,
        decay_factor: float = 1.0,
        half_life_days: float = 30.0,
        price_at_fire: float | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Record a single signal fire. Returns record ID."""
        date_str = fire_date if isinstance(fire_date, str) else fire_date.isoformat()

        with SessionLocal() as session:
            record = SignalHistoryRecord(
                signal_id=signal_id,
                signal_name=signal_name,
                ticker=ticker.upper(),
                fire_date=date_str,
                strength=strength,
                confidence=confidence,
                direction=direction,
                category=category,
                value=value,
                decay_factor=decay_factor,
                half_life_days=half_life_days,
                price_at_fire=price_at_fire,
                metadata_json=json.dumps(metadata or {}),
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record.id

    @staticmethod
    def record_bulk(fires: list[dict]) -> int:
        """Bulk-record signal fires.

        Each dict must have: signal_id, ticker, fire_date, strength, category.
        Optional: signal_name, confidence, direction, value, decay_factor, etc.
        """
        with SessionLocal() as session:
            records = []
            for f in fires:
                fd = f["fire_date"]
                records.append(SignalHistoryRecord(
                    signal_id=f["signal_id"],
                    signal_name=f.get("signal_name", ""),
                    ticker=f["ticker"].upper(),
                    fire_date=fd if isinstance(fd, str) else fd.isoformat(),
                    strength=f["strength"],
                    confidence=f.get("confidence", 0.0),
                    direction=f.get("direction", "long"),
                    category=f["category"],
                    value=f.get("value"),
                    decay_factor=f.get("decay_factor", 1.0),
                    half_life_days=f.get("half_life_days", 30.0),
                    price_at_fire=f.get("price_at_fire"),
                    metadata_json=json.dumps(f.get("metadata", {})),
                ))
            session.add_all(records)
            session.commit()
            logger.info("SignalStore: bulk-recorded %d signal fires", len(records))
            return len(records)

    # ── Read ─────────────────────────────────────────────────────────────

    @staticmethod
    def get_fires_for_ticker(
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list[dict]:
        """Get all signal fires for a ticker within date range."""
        with SessionLocal() as session:
            query = session.query(SignalHistoryRecord).filter_by(ticker=ticker.upper())
            if start_date:
                query = query.filter(SignalHistoryRecord.fire_date >= start_date)
            if end_date:
                query = query.filter(SignalHistoryRecord.fire_date <= end_date)
            if category:
                query = query.filter_by(category=category)

            records = query.order_by(SignalHistoryRecord.fire_date.asc()).all()
            return [_serialize_fire(r) for r in records]

    @staticmethod
    def get_fires_for_signal(
        signal_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        """Get all fires of a specific signal across all tickers."""
        with SessionLocal() as session:
            query = session.query(SignalHistoryRecord).filter_by(signal_id=signal_id)
            if start_date:
                query = query.filter(SignalHistoryRecord.fire_date >= start_date)
            if end_date:
                query = query.filter(SignalHistoryRecord.fire_date <= end_date)

            records = query.order_by(SignalHistoryRecord.fire_date.asc()).all()
            return [_serialize_fire(r) for r in records]

    @staticmethod
    def get_active_signals(ticker: str, as_of_date: str, min_decay: float = 0.1) -> list[dict]:
        """Get signals that are still active (not fully decayed) as of a date."""
        with SessionLocal() as session:
            records = (
                session.query(SignalHistoryRecord)
                .filter_by(ticker=ticker.upper())
                .filter(SignalHistoryRecord.fire_date <= as_of_date)
                .filter(SignalHistoryRecord.decay_factor >= min_decay)
                .order_by(SignalHistoryRecord.fire_date.desc())
                .all()
            )
            return [_serialize_fire(r) for r in records]

    @staticmethod
    def count_by_category(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, int]:
        """Count signal fires by category."""
        from sqlalchemy import func
        with SessionLocal() as session:
            query = session.query(
                SignalHistoryRecord.category,
                func.count(SignalHistoryRecord.id).label("count"),
            )
            if start_date:
                query = query.filter(SignalHistoryRecord.fire_date >= start_date)
            if end_date:
                query = query.filter(SignalHistoryRecord.fire_date <= end_date)

            results = query.group_by(SignalHistoryRecord.category).all()
            return {r.category: r.count for r in results}


def _serialize_fire(r: SignalHistoryRecord) -> dict:
    return {
        "id": r.id,
        "signal_id": r.signal_id,
        "signal_name": r.signal_name,
        "ticker": r.ticker,
        "fire_date": r.fire_date,
        "strength": r.strength,
        "confidence": r.confidence,
        "direction": r.direction,
        "category": r.category,
        "value": r.value,
        "decay_factor": r.decay_factor,
        "half_life_days": r.half_life_days,
        "price_at_fire": r.price_at_fire,
        "metadata": json.loads(r.metadata_json) if r.metadata_json else {},
    }
