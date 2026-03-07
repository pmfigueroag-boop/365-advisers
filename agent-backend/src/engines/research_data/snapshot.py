"""
src/engines/research_data/snapshot.py
─────────────────────────────────────────────────────────────────────────────
PointInTimeSnapshot — prevent lookahead bias in feature construction.

Ensures that when building features for date T, only data available on or
before T is used, regardless of when the data was persisted.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from src.data.database import SessionLocal
from .models import FeatureSnapshotRecord, SignalHistoryRecord

logger = logging.getLogger(__name__)


class PointInTimeSnapshot:
    """Point-in-time data access to prevent lookahead bias.

    All queries are filtered by `as_of_date` to ensure only data
    that would have been available at that point in time is returned.
    """

    @staticmethod
    def get_features_as_of(
        ticker: str,
        as_of_date: str,
        feature_set: str,
    ) -> dict[str, float]:
        """Get the most recent feature vector available on or before `as_of_date`.

        This prevents lookahead bias by never returning data from the future.
        """
        with SessionLocal() as session:
            record = (
                session.query(FeatureSnapshotRecord)
                .filter_by(ticker=ticker.upper(), feature_set=feature_set)
                .filter(FeatureSnapshotRecord.snapshot_date <= as_of_date)
                .order_by(FeatureSnapshotRecord.snapshot_date.desc())
                .first()
            )
            if record:
                return json.loads(record.features_json)
            return {}

    @staticmethod
    def get_signals_as_of(
        ticker: str,
        as_of_date: str,
        category: Optional[str] = None,
        min_decay: float = 0.1,
    ) -> list[dict]:
        """Get all signals that fired on or before `as_of_date` and are still active.

        Filters by decay_factor to exclude fully expired signals.
        """
        with SessionLocal() as session:
            query = (
                session.query(SignalHistoryRecord)
                .filter_by(ticker=ticker.upper())
                .filter(SignalHistoryRecord.fire_date <= as_of_date)
                .filter(SignalHistoryRecord.decay_factor >= min_decay)
            )
            if category:
                query = query.filter_by(category=category)

            records = query.order_by(SignalHistoryRecord.fire_date.desc()).all()
            return [
                {
                    "signal_id": r.signal_id,
                    "signal_name": r.signal_name,
                    "fire_date": r.fire_date,
                    "strength": r.strength,
                    "confidence": r.confidence,
                    "direction": r.direction,
                    "category": r.category,
                    "decay_factor": r.decay_factor,
                    "value": r.value,
                }
                for r in records
            ]

    @staticmethod
    def build_snapshot(
        ticker: str,
        as_of_date: str,
        feature_sets: list[str],
    ) -> dict:
        """Build a complete point-in-time snapshot for a ticker.

        Returns:
            {
                "ticker": str,
                "as_of_date": str,
                "features": {feature_name: value, ...},
                "active_signals": [{...}],
                "feature_sets_used": [str],
            }
        """
        all_features: dict[str, float] = {}
        sets_used: list[str] = []

        for fs in feature_sets:
            features = PointInTimeSnapshot.get_features_as_of(ticker, as_of_date, fs)
            if features:
                all_features.update(features)
                sets_used.append(fs)

        active_signals = PointInTimeSnapshot.get_signals_as_of(ticker, as_of_date)

        return {
            "ticker": ticker.upper(),
            "as_of_date": as_of_date,
            "features": all_features,
            "active_signals": active_signals,
            "feature_sets_used": sets_used,
        }

    @staticmethod
    def build_panel(
        tickers: list[str],
        as_of_date: str,
        feature_sets: list[str],
    ) -> list[dict]:
        """Build point-in-time snapshots for multiple tickers.

        Returns list of snapshot dicts.
        """
        return [
            PointInTimeSnapshot.build_snapshot(ticker, as_of_date, feature_sets)
            for ticker in tickers
        ]
