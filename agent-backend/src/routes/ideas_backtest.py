"""
src/routes/ideas_backtest.py
──────────────────────────────────────────────────────────────────────────────
API routes for the IDEA Backtesting + Calibration layer.

Endpoints:
  GET  /ideas/backtest/summary           — Overall analytics summary
  GET  /ideas/backtest/detectors         — Per-detector performance
  GET  /ideas/backtest/calibration       — Calibration report
  GET  /ideas/backtest/decay             — Alpha decay analysis
  GET  /ideas/backtest/snapshots/{id}    — Single snapshot detail
  POST /ideas/backtest/evaluate          — Evaluate specific snapshots
  POST /ideas/backtest/evaluate/pending  — Evaluate all pending snapshots
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.engines.idea_generation.backtest.models import (
    BacktestConfig,
    EvaluationHorizon,
    IdeaSnapshot,
    IdeaSnapshotRecord,
    SnapshotOutcomeRecord,
    OutcomeResult,
    GroupMetrics,
    CalibrationReport,
    DecayProfile,
)
from src.engines.idea_generation.backtest.analytics_service import (
    analytics_by_detector,
    analytics_by_idea_type,
    analytics_by_confidence_bucket,
    analytics_by_signal_strength_bucket,
    analytics_summary,
)
from src.engines.idea_generation.backtest.calibration_service import compute_calibration
from src.engines.idea_generation.backtest.decay_analysis import (
    decay_by_detector,
    decay_summary,
)
from src.engines.idea_generation.backtest.market_data_provider import FakeMarketDataProvider
from src.engines.idea_generation.backtest.outcome_evaluator import OutcomeEvaluator
from src.engines.idea_generation.metrics import get_collector

logger = logging.getLogger("365advisers.routes.ideas_backtest")

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/ideas/backtest", tags=["Ideas Backtest"], dependencies=[Depends(get_current_user)])


# ── Request / Response Schemas ────────────────────────────────────────────────


class EvaluateRequest(BaseModel):
    """Request to evaluate specific snapshots."""
    snapshot_ids: list[str] = Field(
        ..., min_length=1, max_length=100,
        description="Snapshot IDs to evaluate",
    )
    horizons: list[str] = Field(
        default_factory=lambda: ["1D", "5D", "20D", "60D"],
        description="Horizons to evaluate",
    )


class EvaluatePendingRequest(BaseModel):
    """Request to evaluate all pending snapshots."""
    limit: int = Field(100, ge=1, le=1000, description="Max snapshots to evaluate")
    horizons: list[str] = Field(
        default_factory=lambda: ["1D", "5D", "20D", "60D"],
        description="Horizons to evaluate",
    )


class BacktestSummaryResponse(BaseModel):
    overall: GroupMetrics
    by_detector: list[GroupMetrics]
    by_idea_type: list[GroupMetrics]
    by_confidence_bucket: list[GroupMetrics]
    by_signal_strength_bucket: list[GroupMetrics]
    total_snapshots: int
    total_evaluated: int
    generated_at: str


class DecayResponse(BaseModel):
    overall: DecayProfile
    by_detector: list[DecayProfile]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _load_snapshots(
    detector: str | None = None,
    idea_type: str | None = None,
    limit: int = 5000,
) -> list[IdeaSnapshot]:
    """Load snapshots from DB and convert to Pydantic models."""
    from src.data.database import SessionLocal

    with SessionLocal() as db:
        query = db.query(IdeaSnapshotRecord)
        if detector:
            query = query.filter(IdeaSnapshotRecord.detector == detector)
        if idea_type:
            query = query.filter(IdeaSnapshotRecord.idea_type == idea_type)
        records = query.order_by(IdeaSnapshotRecord.generated_at.desc()).limit(limit).all()

        return [
            IdeaSnapshot(
                snapshot_id=r.snapshot_id,
                generated_at=r.generated_at,
                scan_id=r.scan_id,
                ticker=r.ticker,
                detector=r.detector,
                idea_type=r.idea_type,
                source=r.source or "legacy",
                signal_strength=r.signal_strength,
                confidence_score=r.confidence_score,
                alpha_score=r.alpha_score or 0.0,
                rank_score=r.rank_score or 0.0,
                active_signals_count=r.active_signals_count or 0,
                strong_signals_count=r.strong_signals_count or 0,
                moderate_signals_count=r.moderate_signals_count or 0,
                weak_signals_count=r.weak_signals_count or 0,
                scan_mode=r.scan_mode or "local",
                registry_key=r.registry_key or "",
                name=r.name or "",
                sector=r.sector or "",
                confidence_level=r.confidence_level or "medium",
                price_at_signal=r.price_at_signal,
                market_metadata=json.loads(r.market_metadata_json or "{}"),
            )
            for r in records
        ]


def _load_outcomes(
    snapshot_ids: list[str] | None = None,
    horizon: str | None = None,
    detector: str | None = None,
    idea_type: str | None = None,
) -> list[OutcomeResult]:
    """Load outcomes from DB and convert to Pydantic models."""
    from src.data.database import SessionLocal

    with SessionLocal() as db:
        query = db.query(SnapshotOutcomeRecord)
        if snapshot_ids:
            query = query.filter(SnapshotOutcomeRecord.snapshot_id.in_(snapshot_ids))
        if horizon:
            query = query.filter(SnapshotOutcomeRecord.horizon == horizon)
        if detector:
            query = query.filter(SnapshotOutcomeRecord.detector == detector)
        if idea_type:
            query = query.filter(SnapshotOutcomeRecord.idea_type == idea_type)
        records = query.all()

        return [
            OutcomeResult(
                snapshot_id=r.snapshot_id,
                horizon=EvaluationHorizon(r.horizon),
                evaluated_at=r.evaluated_at,
                price_at_signal=r.price_at_signal,
                price_at_horizon=r.price_at_horizon,
                raw_return=r.raw_return,
                excess_return=r.excess_return,
                max_favorable_excursion=r.max_favorable_excursion,
                max_adverse_excursion=r.max_adverse_excursion,
                drawdown_from_signal=r.drawdown_from_signal,
                is_hit=r.is_hit or False,
                outcome_label=r.outcome_label or "neutral",
                data_available=r.data_available if r.data_available is not None else True,
            )
            for r in records
        ]


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/summary", response_model=BacktestSummaryResponse, summary="Backtest analytics summary")
async def get_backtest_summary(
    detector: str | None = Query(None, description="Filter by detector"),
    idea_type: str | None = Query(None, description="Filter by idea type"),
    horizon: str = Query("20D", description="Horizon for analytics: 1D, 5D, 20D, 60D"),
):
    """Get aggregated backtest analytics with breakdown by multiple dimensions."""
    try:
        snapshots = _load_snapshots(detector=detector, idea_type=idea_type)
        snap_ids = [s.snapshot_id for s in snapshots]
        outcomes = _load_outcomes(snapshot_ids=snap_ids, horizon=horizon)

        return BacktestSummaryResponse(
            overall=analytics_summary(snapshots, outcomes, horizon),
            by_detector=analytics_by_detector(snapshots, outcomes, horizon),
            by_idea_type=analytics_by_idea_type(snapshots, outcomes, horizon),
            by_confidence_bucket=analytics_by_confidence_bucket(snapshots, outcomes, horizon),
            by_signal_strength_bucket=analytics_by_signal_strength_bucket(snapshots, outcomes, horizon),
            total_snapshots=len(snapshots),
            total_evaluated=len([o for o in outcomes if o.data_available]),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        logger.error(f"backtest_summary_error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/detectors", summary="Per-detector backtest performance")
async def get_detector_performance(
    horizon: str = Query("20D", description="Horizon"),
):
    """Get performance metrics for each detector."""
    try:
        snapshots = _load_snapshots()
        snap_ids = [s.snapshot_id for s in snapshots]
        outcomes = _load_outcomes(snapshot_ids=snap_ids, horizon=horizon)
        return analytics_by_detector(snapshots, outcomes, horizon)
    except Exception as exc:
        logger.error(f"detector_performance_error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/calibration", response_model=CalibrationReport, summary="Confidence calibration report")
async def get_calibration(
    horizon: str = Query("20D", description="Horizon"),
    detector: str | None = Query(None),
    idea_type: str | None = Query(None),
):
    """Get calibration report comparing confidence scores to realized outcomes."""
    try:
        snapshots = _load_snapshots(detector=detector, idea_type=idea_type)
        snap_ids = [s.snapshot_id for s in snapshots]
        outcomes = _load_outcomes(snapshot_ids=snap_ids, horizon=horizon)
        return compute_calibration(snapshots, outcomes, horizon)
    except Exception as exc:
        logger.error(f"calibration_error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/decay", response_model=DecayResponse, summary="Alpha decay analysis")
async def get_decay_analysis(
    detector: str | None = Query(None),
    idea_type: str | None = Query(None),
):
    """Get alpha decay analysis across horizons."""
    try:
        snapshots = _load_snapshots(detector=detector, idea_type=idea_type)
        snap_ids = [s.snapshot_id for s in snapshots]
        outcomes = _load_outcomes(snapshot_ids=snap_ids)
        return DecayResponse(
            overall=decay_summary(snapshots, outcomes),
            by_detector=decay_by_detector(snapshots, outcomes),
        )
    except Exception as exc:
        logger.error(f"decay_analysis_error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/snapshots/{snapshot_id}", summary="Get a single snapshot")
async def get_snapshot(snapshot_id: str):
    """Get details for a specific snapshot and its outcomes."""
    from src.data.database import SessionLocal

    with SessionLocal() as db:
        record = db.query(IdeaSnapshotRecord).filter(
            IdeaSnapshotRecord.snapshot_id == snapshot_id,
        ).first()
        if not record:
            raise HTTPException(status_code=404, detail="Snapshot not found")

        outcomes = db.query(SnapshotOutcomeRecord).filter(
            SnapshotOutcomeRecord.snapshot_id == snapshot_id,
        ).all()

        return {
            "snapshot": {
                "snapshot_id": record.snapshot_id,
                "ticker": record.ticker,
                "detector": record.detector,
                "idea_type": record.idea_type,
                "signal_strength": record.signal_strength,
                "confidence_score": record.confidence_score,
                "alpha_score": record.alpha_score,
                "rank_score": record.rank_score,
                "generated_at": record.generated_at.isoformat() if record.generated_at else None,
                "evaluation_status": record.evaluation_status,
                "name": record.name,
                "sector": record.sector,
                "scan_mode": record.scan_mode,
            },
            "outcomes": [
                {
                    "horizon": o.horizon,
                    "raw_return": o.raw_return,
                    "excess_return": o.excess_return,
                    "is_hit": o.is_hit,
                    "outcome_label": o.outcome_label,
                    "price_at_signal": o.price_at_signal,
                    "price_at_horizon": o.price_at_horizon,
                    "evaluated_at": o.evaluated_at.isoformat() if o.evaluated_at else None,
                }
                for o in outcomes
            ],
        }


@router.post("/evaluate", summary="Evaluate specific snapshots")
async def evaluate_snapshots(body: EvaluateRequest):
    """Evaluate specific snapshots against market data.

    Note: In production, connect a real MarketDataProvider.
    This endpoint uses FakeMarketDataProvider for demo/testing.
    """
    from src.data.database import SessionLocal

    config = BacktestConfig(
        horizons=[EvaluationHorizon(h) for h in body.horizons],
    )
    provider = FakeMarketDataProvider()
    evaluator = OutcomeEvaluator(provider=provider, config=config)

    with SessionLocal() as db:
        records = db.query(IdeaSnapshotRecord).filter(
            IdeaSnapshotRecord.snapshot_id.in_(body.snapshot_ids),
        ).all()

    if not records:
        raise HTTPException(status_code=404, detail="No snapshots found")

    snapshots = [
        IdeaSnapshot(
            snapshot_id=r.snapshot_id,
            generated_at=r.generated_at,
            ticker=r.ticker,
            detector=r.detector,
            idea_type=r.idea_type,
            signal_strength=r.signal_strength,
            confidence_score=r.confidence_score,
            alpha_score=r.alpha_score or 0.0,
            price_at_signal=r.price_at_signal,
        )
        for r in records
    ]

    all_outcomes = evaluator.evaluate_batch(snapshots)
    snap_map = {s.snapshot_id: s for s in snapshots}
    persisted = evaluator.persist_outcomes(all_outcomes, snap_map)

    return {
        "evaluated": len(snapshots),
        "outcomes_generated": len(all_outcomes),
        "outcomes_persisted": persisted,
    }


@router.post("/evaluate/pending", summary="Evaluate all pending snapshots")
async def evaluate_pending(body: EvaluatePendingRequest):
    """Evaluate all snapshots with status='pending'."""
    from src.data.database import SessionLocal

    config = BacktestConfig(
        horizons=[EvaluationHorizon(h) for h in body.horizons],
    )
    provider = FakeMarketDataProvider()
    evaluator = OutcomeEvaluator(provider=provider, config=config)

    with SessionLocal() as db:
        records = db.query(IdeaSnapshotRecord).filter(
            IdeaSnapshotRecord.evaluation_status == "pending",
        ).limit(body.limit).all()

    if not records:
        return {"evaluated": 0, "outcomes_generated": 0, "message": "No pending snapshots"}

    snapshots = [
        IdeaSnapshot(
            snapshot_id=r.snapshot_id,
            generated_at=r.generated_at,
            ticker=r.ticker,
            detector=r.detector,
            idea_type=r.idea_type,
            signal_strength=r.signal_strength,
            confidence_score=r.confidence_score,
            alpha_score=r.alpha_score or 0.0,
            price_at_signal=r.price_at_signal,
        )
        for r in records
    ]

    all_outcomes = evaluator.evaluate_batch(snapshots)
    snap_map = {s.snapshot_id: s for s in snapshots}
    persisted = evaluator.persist_outcomes(all_outcomes, snap_map)

    # Update evaluation_status
    with SessionLocal() as db:
        for r_id in [r.snapshot_id for r in records]:
            db.query(IdeaSnapshotRecord).filter(
                IdeaSnapshotRecord.snapshot_id == r_id,
            ).update({"evaluation_status": "complete"})
        db.commit()

    get_collector().gauge("pending_snapshots_gauge", 0)

    return {
        "evaluated": len(snapshots),
        "outcomes_generated": len(all_outcomes),
        "outcomes_persisted": persisted,
    }
