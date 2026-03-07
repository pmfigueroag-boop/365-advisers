"""
src/engines/research_data/dataset_builder.py
─────────────────────────────────────────────────────────────────────────────
DatasetBuilder — compose research-ready datasets from features + signals.

Combines FeatureStore and SignalStore data into versioned, reproducible
research datasets that can be used by the Signal Lab and Strategy Backtester.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from src.data.database import SessionLocal
from .models import ResearchDatasetRecord, ResearchDatasetMemberRecord
from .feature_store import FeatureStore
from .signal_store import SignalStore

logger = logging.getLogger(__name__)


class DatasetBuilder:
    """Compose and manage research datasets."""

    # ── Create ───────────────────────────────────────────────────────────

    @staticmethod
    def create_dataset(
        name: str,
        tickers: list[str],
        date_start: str,
        date_end: str,
        feature_sets: list[str] | None = None,
        signals: list[str] | None = None,
        description: str = "",
        version: str = "1.0.0",
        author: str = "system",
        tags: list[str] | None = None,
        ticker_metadata: list[dict] | None = None,
    ) -> dict:
        """Create a new research dataset definition.

        Args:
            name: Human-readable dataset name
            tickers: List of tickers in the dataset
            date_start: Start date (ISO format)
            date_end: End date (ISO format)
            feature_sets: Feature set names to include
            signals: Signal IDs to include
            description: Dataset description
            version: Semantic version
            author: Creator identifier
            tags: Categorization tags
            ticker_metadata: Optional list of {ticker, sector, market_cap}

        Returns:
            Dataset summary dict with dataset_id.
        """
        dataset_id = str(uuid.uuid4())[:16]
        tickers_upper = [t.upper() for t in tickers]

        with SessionLocal() as session:
            record = ResearchDatasetRecord(
                dataset_id=dataset_id,
                name=name,
                version=version,
                description=description,
                tickers_json=json.dumps(tickers_upper),
                date_start=date_start,
                date_end=date_end,
                feature_sets_json=json.dumps(feature_sets or []),
                signals_json=json.dumps(signals or []),
                ticker_count=len(tickers_upper),
                row_count=0,
                tags_json=json.dumps(tags or []),
                author=author,
            )
            session.add(record)

            # Add ticker members
            meta_map = {}
            if ticker_metadata:
                meta_map = {m["ticker"].upper(): m for m in ticker_metadata}

            for ticker in tickers_upper:
                meta = meta_map.get(ticker, {})
                member = ResearchDatasetMemberRecord(
                    dataset_id=dataset_id,
                    ticker=ticker,
                    sector=meta.get("sector", ""),
                    market_cap=meta.get("market_cap"),
                )
                session.add(member)

            session.commit()
            logger.info("DatasetBuilder: created dataset '%s' v%s (%d tickers)", name, version, len(tickers_upper))

        return {
            "dataset_id": dataset_id,
            "name": name,
            "version": version,
            "tickers": tickers_upper,
            "date_range": [date_start, date_end],
            "feature_sets": feature_sets or [],
            "signals": signals or [],
            "ticker_count": len(tickers_upper),
        }

    # ── Load ─────────────────────────────────────────────────────────────

    @staticmethod
    def load_dataset(dataset_id: str) -> dict | None:
        """Load a dataset definition by ID."""
        with SessionLocal() as session:
            record = (
                session.query(ResearchDatasetRecord)
                .filter_by(dataset_id=dataset_id)
                .first()
            )
            if not record:
                return None

            members = (
                session.query(ResearchDatasetMemberRecord)
                .filter_by(dataset_id=dataset_id)
                .all()
            )

            return {
                "dataset_id": record.dataset_id,
                "name": record.name,
                "version": record.version,
                "description": record.description,
                "tickers": json.loads(record.tickers_json),
                "date_range": [record.date_start, record.date_end],
                "feature_sets": json.loads(record.feature_sets_json),
                "signals": json.loads(record.signals_json),
                "ticker_count": record.ticker_count,
                "row_count": record.row_count,
                "tags": json.loads(record.tags_json),
                "author": record.author,
                "status": record.status,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "members": [
                    {"ticker": m.ticker, "sector": m.sector, "market_cap": m.market_cap}
                    for m in members
                ],
            }

    # ── Materialize ──────────────────────────────────────────────────────

    @staticmethod
    def materialize(dataset_id: str) -> dict:
        """Build the actual data matrix for a dataset.

        Pulls features and signals from their stores and assembles them
        into a combined dict ready for research consumption.

        Returns:
            {
                "dataset_id": ...,
                "rows": [ {ticker, date, features: {...}, signals: [...]} ],
                "row_count": int,
                "feature_columns": [...],
            }
        """
        ds = DatasetBuilder.load_dataset(dataset_id)
        if not ds:
            return {"error": f"Dataset {dataset_id} not found"}

        tickers = ds["tickers"]
        date_start, date_end = ds["date_range"]
        feature_sets = ds["feature_sets"]
        signal_ids = ds["signals"]

        rows = []
        feature_columns: set[str] = set()

        for ticker in tickers:
            # Collect features per date
            date_features: dict[str, dict] = {}
            for fs in feature_sets:
                series = FeatureStore.get_time_series(ticker, fs, date_start, date_end)
                for entry in series:
                    d = entry["date"]
                    if d not in date_features:
                        date_features[d] = {}
                    date_features[d].update(entry["features"])
                    feature_columns.update(entry["features"].keys())

            # Collect signal fires
            fires = SignalStore.get_fires_for_ticker(ticker, date_start, date_end)
            fire_by_date: dict[str, list] = {}
            for fire in fires:
                if signal_ids and fire["signal_id"] not in signal_ids:
                    continue
                fd = fire["fire_date"]
                fire_by_date.setdefault(fd, []).append(fire)

            # Merge into rows
            all_dates = sorted(set(list(date_features.keys()) + list(fire_by_date.keys())))
            for d in all_dates:
                rows.append({
                    "ticker": ticker,
                    "date": d,
                    "features": date_features.get(d, {}),
                    "signals": fire_by_date.get(d, []),
                })

        # Update row count
        with SessionLocal() as session:
            record = session.query(ResearchDatasetRecord).filter_by(dataset_id=dataset_id).first()
            if record:
                record.row_count = len(rows)
                session.commit()

        return {
            "dataset_id": dataset_id,
            "rows": rows,
            "row_count": len(rows),
            "feature_columns": sorted(feature_columns),
        }

    # ── List ─────────────────────────────────────────────────────────────

    @staticmethod
    def list_datasets(status: str = "active") -> list[dict]:
        """List all datasets with optional status filter."""
        with SessionLocal() as session:
            query = session.query(ResearchDatasetRecord)
            if status:
                query = query.filter_by(status=status)

            records = query.order_by(ResearchDatasetRecord.created_at.desc()).all()
            return [
                {
                    "dataset_id": r.dataset_id,
                    "name": r.name,
                    "version": r.version,
                    "ticker_count": r.ticker_count,
                    "row_count": r.row_count,
                    "date_range": [r.date_start, r.date_end],
                    "tags": json.loads(r.tags_json) if r.tags_json else [],
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in records
            ]

    # ── Archive ──────────────────────────────────────────────────────────

    @staticmethod
    def archive_dataset(dataset_id: str) -> bool:
        """Archive a dataset (soft-delete)."""
        with SessionLocal() as session:
            record = session.query(ResearchDatasetRecord).filter_by(dataset_id=dataset_id).first()
            if not record:
                return False
            record.status = "archived"
            session.commit()
            return True
