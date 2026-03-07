"""
src/engines/research_data/feature_store.py
─────────────────────────────────────────────────────────────────────────────
FeatureStore — save, load, and query versioned feature vectors.

Features are keyed by (ticker, date, feature_set). Each feature set is
independently versioned so different research pipelines can produce and
consume distinct feature schemas.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Optional

from src.data.database import SessionLocal
from .models import FeatureSnapshotRecord

logger = logging.getLogger(__name__)


class FeatureStore:
    """Versioned feature vector store for quant research."""

    # ── Write ────────────────────────────────────────────────────────────

    @staticmethod
    def save_snapshot(
        ticker: str,
        snapshot_date: date | str,
        feature_set: str,
        features: dict[str, float],
        version: str = "1.0.0",
        source_versions: dict | None = None,
    ) -> int:
        """Persist a single feature snapshot. Returns the record ID."""
        date_str = snapshot_date if isinstance(snapshot_date, str) else snapshot_date.isoformat()

        with SessionLocal() as session:
            record = FeatureSnapshotRecord(
                ticker=ticker.upper(),
                snapshot_date=date_str,
                feature_set=feature_set,
                version=version,
                features_json=json.dumps(features),
                source_versions_json=json.dumps(source_versions or {}),
                row_count=len(features),
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            logger.debug("FeatureStore: saved %s/%s/%s (%d features)", ticker, date_str, feature_set, len(features))
            return record.id

    @staticmethod
    def save_bulk(
        snapshots: list[dict],
        feature_set: str,
        version: str = "1.0.0",
    ) -> int:
        """Bulk-save feature snapshots.

        Each dict in `snapshots` must have: ticker, date, features.
        Returns count of inserted rows.
        """
        with SessionLocal() as session:
            records = []
            for snap in snapshots:
                records.append(FeatureSnapshotRecord(
                    ticker=snap["ticker"].upper(),
                    snapshot_date=snap["date"] if isinstance(snap["date"], str) else snap["date"].isoformat(),
                    feature_set=feature_set,
                    version=version,
                    features_json=json.dumps(snap["features"]),
                    source_versions_json=json.dumps(snap.get("source_versions", {})),
                    row_count=len(snap["features"]),
                ))
            session.add_all(records)
            session.commit()
            logger.info("FeatureStore: bulk-saved %d snapshots for %s", len(records), feature_set)
            return len(records)

    # ── Read ─────────────────────────────────────────────────────────────

    @staticmethod
    def get_snapshot(
        ticker: str,
        snapshot_date: date | str,
        feature_set: str,
    ) -> dict[str, float] | None:
        """Get the latest feature vector for (ticker, date, feature_set)."""
        date_str = snapshot_date if isinstance(snapshot_date, str) else snapshot_date.isoformat()

        with SessionLocal() as session:
            record = (
                session.query(FeatureSnapshotRecord)
                .filter_by(ticker=ticker.upper(), snapshot_date=date_str, feature_set=feature_set)
                .order_by(FeatureSnapshotRecord.created_at.desc())
                .first()
            )
            if record:
                return json.loads(record.features_json)
            return None

    @staticmethod
    def get_time_series(
        ticker: str,
        feature_set: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        """Get feature time series for a ticker.

        Returns list of {date, features} dicts sorted ascending.
        """
        with SessionLocal() as session:
            query = (
                session.query(FeatureSnapshotRecord)
                .filter_by(ticker=ticker.upper(), feature_set=feature_set)
            )
            if start_date:
                query = query.filter(FeatureSnapshotRecord.snapshot_date >= start_date)
            if end_date:
                query = query.filter(FeatureSnapshotRecord.snapshot_date <= end_date)

            records = query.order_by(FeatureSnapshotRecord.snapshot_date.asc()).all()
            return [
                {"date": r.snapshot_date, "features": json.loads(r.features_json)}
                for r in records
            ]

    @staticmethod
    def list_feature_sets() -> list[dict]:
        """List all available feature sets with metadata."""
        with SessionLocal() as session:
            from sqlalchemy import func, distinct
            results = (
                session.query(
                    FeatureSnapshotRecord.feature_set,
                    FeatureSnapshotRecord.version,
                    func.count(distinct(FeatureSnapshotRecord.ticker)).label("tickers"),
                    func.count(FeatureSnapshotRecord.id).label("snapshots"),
                    func.min(FeatureSnapshotRecord.snapshot_date).label("min_date"),
                    func.max(FeatureSnapshotRecord.snapshot_date).label("max_date"),
                )
                .group_by(FeatureSnapshotRecord.feature_set, FeatureSnapshotRecord.version)
                .all()
            )
            return [
                {
                    "feature_set": r.feature_set,
                    "version": r.version,
                    "tickers": r.tickers,
                    "snapshots": r.snapshots,
                    "date_range": [r.min_date, r.max_date],
                }
                for r in results
            ]

    # ── Delete ───────────────────────────────────────────────────────────

    @staticmethod
    def delete_feature_set(feature_set: str) -> int:
        """Delete all snapshots for a feature set. Returns count deleted."""
        with SessionLocal() as session:
            count = (
                session.query(FeatureSnapshotRecord)
                .filter_by(feature_set=feature_set)
                .delete()
            )
            session.commit()
            logger.info("FeatureStore: deleted %d records for feature_set=%s", count, feature_set)
            return count
