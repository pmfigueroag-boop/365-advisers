"""
src/routes/research.py
─────────────────────────────────────────────────────────────────────────────
Research Dataset Layer API — CRUD for datasets, features, and signals.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.engines.research_data.dataset_builder import DatasetBuilder
from src.engines.research_data.feature_store import FeatureStore
from src.engines.research_data.signal_store import SignalStore
from src.engines.research_data.snapshot import PointInTimeSnapshot

logger = logging.getLogger(__name__)
from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/research", tags=["Research Data"], dependencies=[Depends(get_current_user)])


# ── Request / Response Models ────────────────────────────────────────────────

class CreateDatasetRequest(BaseModel):
    name: str
    tickers: list[str]
    date_start: str
    date_end: str
    feature_sets: list[str] | None = None
    signals: list[str] | None = None
    description: str = ""
    version: str = "1.0.0"
    author: str = "system"
    tags: list[str] | None = None


class SaveFeatureRequest(BaseModel):
    ticker: str
    snapshot_date: str
    feature_set: str
    features: dict[str, float]
    version: str = "1.0.0"


class RecordSignalRequest(BaseModel):
    signal_id: str
    ticker: str
    fire_date: str
    strength: str
    category: str
    signal_name: str = ""
    confidence: float = 0.0
    direction: str = "long"
    value: float | None = None
    decay_factor: float = 1.0
    half_life_days: float = 30.0
    price_at_fire: float | None = None


# ── Dataset Endpoints ────────────────────────────────────────────────────────

@router.post("/datasets")
async def create_dataset(req: CreateDatasetRequest):
    """Create a new research dataset definition."""
    result = DatasetBuilder.create_dataset(
        name=req.name,
        tickers=req.tickers,
        date_start=req.date_start,
        date_end=req.date_end,
        feature_sets=req.feature_sets,
        signals=req.signals,
        description=req.description,
        version=req.version,
        author=req.author,
        tags=req.tags,
    )
    return result


@router.get("/datasets")
async def list_datasets(status: str = Query("active")):
    """List all research datasets."""
    return DatasetBuilder.list_datasets(status=status)


@router.get("/datasets/{dataset_id}")
async def get_dataset(dataset_id: str):
    """Get a dataset definition by ID."""
    ds = DatasetBuilder.load_dataset(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return ds


@router.post("/datasets/{dataset_id}/materialize")
async def materialize_dataset(dataset_id: str):
    """Materialize a dataset — pull features + signals into a combined matrix."""
    result = DatasetBuilder.materialize(dataset_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/datasets/{dataset_id}/archive")
async def archive_dataset(dataset_id: str):
    """Archive (soft-delete) a dataset."""
    ok = DatasetBuilder.archive_dataset(dataset_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found")
    return {"status": "archived", "dataset_id": dataset_id}


# ── Feature Endpoints ────────────────────────────────────────────────────────

@router.post("/features")
async def save_feature(req: SaveFeatureRequest):
    """Save a feature snapshot."""
    record_id = FeatureStore.save_snapshot(
        ticker=req.ticker,
        snapshot_date=req.snapshot_date,
        feature_set=req.feature_set,
        features=req.features,
        version=req.version,
    )
    return {"id": record_id, "status": "saved"}


@router.get("/features/{ticker}")
async def get_features(
    ticker: str,
    feature_set: str = Query(...),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Get feature time series for a ticker."""
    series = FeatureStore.get_time_series(ticker, feature_set, start_date, end_date)
    return {"ticker": ticker.upper(), "feature_set": feature_set, "snapshots": series}


@router.get("/features")
async def list_feature_sets():
    """List all available feature sets."""
    return FeatureStore.list_feature_sets()


# ── Signal History Endpoints ─────────────────────────────────────────────────

@router.post("/signals/history")
async def record_signal(req: RecordSignalRequest):
    """Record a historical signal fire."""
    record_id = SignalStore.record_fire(
        signal_id=req.signal_id,
        ticker=req.ticker,
        fire_date=req.fire_date,
        strength=req.strength,
        category=req.category,
        signal_name=req.signal_name,
        confidence=req.confidence,
        direction=req.direction,
        value=req.value,
        decay_factor=req.decay_factor,
        half_life_days=req.half_life_days,
        price_at_fire=req.price_at_fire,
    )
    return {"id": record_id, "status": "recorded"}


@router.get("/signals/history/{ticker}")
async def get_signal_history(
    ticker: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
):
    """Get signal fire history for a ticker."""
    fires = SignalStore.get_fires_for_ticker(ticker, start_date, end_date, category)
    return {"ticker": ticker.upper(), "fires": fires, "count": len(fires)}


@router.get("/signals/history/by-signal/{signal_id}")
async def get_fires_by_signal(
    signal_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """Get all fires of a specific signal across tickers."""
    fires = SignalStore.get_fires_for_signal(signal_id, start_date, end_date)
    return {"signal_id": signal_id, "fires": fires, "count": len(fires)}


# ── Point-in-Time Snapshot Endpoints ─────────────────────────────────────────

@router.get("/snapshot/{ticker}")
async def get_pit_snapshot(
    ticker: str,
    as_of_date: str = Query(...),
    feature_sets: str = Query(""),  # comma-separated
):
    """Get a point-in-time snapshot for a ticker (no lookahead bias)."""
    fs_list = [s.strip() for s in feature_sets.split(",") if s.strip()]
    snapshot = PointInTimeSnapshot.build_snapshot(ticker, as_of_date, fs_list)
    return snapshot
