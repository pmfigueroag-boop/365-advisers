"""
src/routes/ideas.py
──────────────────────────────────────────────────────────────────────────────
API routes for the Idea Generation Engine.

Endpoints:
  POST /ideas/scan         — Run a full universe scan
  GET  /ideas              — Get active ideas (ranked)
  GET  /ideas/history      — Historical ideas
  POST /ideas/{id}/analyze — Trigger full pipeline for an idea
  POST /ideas/{id}/dismiss — Dismiss an idea
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.engines.idea_generation.engine import IdeaGenerationEngine
from src.engines.idea_generation.models import IdeaStatus
from src.data.database import SessionLocal, IdeaRecord
from src.engines.idea_generation.metrics import get_collector
from src.engines.idea_generation.strategy_profiles import (
    default_profile_registry,
)
from src.engines.idea_generation.universe_discovery import (
    UniverseRequest,
    UniverseSource,
    default_universe_service,
)

logger = logging.getLogger("365advisers.routes.ideas")

router = APIRouter(prefix="/ideas", tags=["Ideas"])

# ── Request / Response Schemas ────────────────────────────────────────────────

class ScanRequest(BaseModel):
    """Request body for universe scan."""
    tickers: list[str] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of ticker symbols to scan (max 500 for local mode; use /scan/distributed for larger universes)",
    )
    strategy_profile: str | None = Field(
        None,
        description="Strategy profile key (e.g. 'buy_and_hold', 'swing', 'deep_value'). None uses institutional defaults.",
    )


class ScanResponse(BaseModel):
    scan_id: str
    universe_size: int
    ideas_found: int
    scan_duration_ms: float
    detector_stats: dict
    ideas: list[dict]
    strategy_profile: str | None = None


class IdeaSummary(BaseModel):
    id: str
    idea_uid: str
    ticker: str
    name: str
    sector: str
    idea_type: str
    confidence: str
    signal_strength: float
    confidence_score: float = 0.0
    priority: int
    signals: list[dict]
    status: str
    generated_at: str


# ── Engine factory ───────────────────────────────────────────────────────────────

_engine: IdeaGenerationEngine | None = None


def get_engine(strategy_profile_key: str | None = None) -> IdeaGenerationEngine:
    """Factory — creates an engine, optionally profile-driven.

    When a profile key is provided, a fresh engine is created with
    the profile's detectors, weights, and filters.
    When None, returns the default singleton engine.
    """
    global _engine
    if strategy_profile_key is not None:
        profile = default_profile_registry.get_or_raise(strategy_profile_key)
        return IdeaGenerationEngine(strategy_profile=profile)
    if _engine is None:
        _engine = IdeaGenerationEngine()
    return _engine


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/scan", response_model=ScanResponse, summary="Scan universe for ideas")
async def scan_universe(body: ScanRequest):
    """
    Run all opportunity detectors across the provided ticker universe.
    Results are persisted and returned as a ranked list.
    """
    get_collector().increment("scans_started_total", tags={
        "mode": "local", "endpoint": "/ideas/scan",
    })
    logger.info(
        "scan_requested",
        extra={
            "endpoint": "/ideas/scan",
            "ticker_count": len(body.tickers),
            "scan_mode": "local",
        },
    )

    result = await get_engine(strategy_profile_key=body.strategy_profile).scan(
        tickers=body.tickers,
    )

    get_collector().increment("scans_completed_total", tags={
        "mode": "local", "endpoint": "/ideas/scan",
    })
    get_collector().gauge("scan_ideas_total", len(result.ideas), tags={
        "mode": "local",
    })

    # Persist to DB
    persisted_count = 0
    with SessionLocal() as db:
        for idea in result.ideas:
            try:
                record = IdeaRecord(
                    idea_uid=idea.id,
                    ticker=idea.ticker,
                    name=idea.name,
                    sector=idea.sector,
                    idea_type=idea.idea_type.value,
                    confidence=idea.confidence.value,
                    signal_strength=idea.signal_strength,
                    priority=idea.priority,
                    signals_json=json.dumps(
                        [s.model_dump() for s in idea.signals]
                    ),
                    status=idea.status.value,
                    generated_at=idea.generated_at,
                    expires_at=idea.expires_at,
                    metadata_json=json.dumps(idea.metadata),
                )
                db.add(record)
                persisted_count += 1
            except Exception as exc:
                logger.warning(f"IDEA-SCAN: Failed to persist idea {idea.ticker}: {exc}")
        db.commit()

    logger.info(
        f"IDEA-SCAN: Complete — {len(result.ideas)} ideas found, "
        f"{persisted_count} persisted, {result.scan_duration_ms:.0f}ms"
    )

    return ScanResponse(
        scan_id=result.scan_id,
        universe_size=result.universe_size,
        ideas_found=len(result.ideas),
        scan_duration_ms=result.scan_duration_ms,
        detector_stats=result.detector_stats,
        ideas=[
            {
                "id": idea.id,
                "ticker": idea.ticker,
                "name": idea.name,
                "sector": idea.sector,
                "idea_type": idea.idea_type.value,
                "confidence": idea.confidence.value,
                "signal_strength": idea.signal_strength,
                "confidence_score": idea.confidence_score,
                "priority": idea.priority,
                "signals": [s.model_dump() for s in idea.signals],
                "status": idea.status.value,
                "generated_at": idea.generated_at.isoformat(),
                "metadata": idea.metadata,
            }
            for idea in result.ideas
        ],
        strategy_profile=body.strategy_profile,
    )


@router.get("/profiles", summary="List available strategy profiles")
async def list_profiles():
    """Return all active strategy profiles with their configuration."""
    profiles = default_profile_registry.list_active()
    return {
        "profiles": [p.to_dict() for p in profiles],
        "total": len(profiles),
        "default": None,
    }


@router.get("", summary="Get active ideas")
async def get_ideas(
    status: str = Query("active", description="Filter by status: active, analyzed, dismissed"),
    idea_type: str | None = Query(None, description="Filter by type: value, quality, growth, momentum, reversal, event"),
    limit: int = Query(50, ge=1, le=200),
):
    """Return persisted ideas, ordered by priority."""
    with SessionLocal() as db:
        query = db.query(IdeaRecord).filter(IdeaRecord.status == status)
        if idea_type:
            query = query.filter(IdeaRecord.idea_type == idea_type)
        rows = query.order_by(IdeaRecord.priority.asc()).limit(limit).all()

        return [
            {
                "id": str(r.id),
                "idea_uid": r.idea_uid,
                "ticker": r.ticker,
                "name": r.name,
                "sector": r.sector,
                "idea_type": r.idea_type,
                "confidence": r.confidence,
                "signal_strength": r.signal_strength,
                "confidence_score": r.signal_strength * 0.8,  # approx from DB (no stored field yet)
                "priority": r.priority,
                "signals": json.loads(r.signals_json or "[]"),
                "status": r.status,
                "generated_at": r.generated_at.isoformat() if r.generated_at else None,
                "metadata": json.loads(r.metadata_json or "{}"),
            }
            for r in rows
        ]


@router.get("/history", summary="Get idea history")
async def get_idea_history(
    ticker: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Return historical ideas across all statuses."""
    with SessionLocal() as db:
        query = db.query(IdeaRecord)
        if ticker:
            query = query.filter(IdeaRecord.ticker == ticker.upper())
        rows = (
            query.order_by(IdeaRecord.generated_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": str(r.id),
                "idea_uid": r.idea_uid,
                "ticker": r.ticker,
                "name": r.name,
                "idea_type": r.idea_type,
                "confidence": r.confidence,
                "signal_strength": r.signal_strength,
                "priority": r.priority,
                "status": r.status,
                "generated_at": r.generated_at.isoformat() if r.generated_at else None,
                "analyzed_at": r.analyzed_at.isoformat() if r.analyzed_at else None,
            }
            for r in rows
        ]


@router.post("/{idea_id}/dismiss", summary="Dismiss an idea")
async def dismiss_idea(idea_id: int):
    """Mark an idea as dismissed so it no longer appears in active list."""
    with SessionLocal() as db:
        record = db.query(IdeaRecord).filter(IdeaRecord.id == idea_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Idea not found")
        record.status = IdeaStatus.DISMISSED.value
        db.commit()
        return {"status": "dismissed", "id": idea_id}


@router.post("/{idea_id}/analyze", summary="Mark idea as analyzed")
async def mark_analyzed(idea_id: int):
    """
    Mark an idea as analyzed (called after the user triggers a full
    pipeline analysis from the Ideas Panel).
    """
    with SessionLocal() as db:
        record = db.query(IdeaRecord).filter(IdeaRecord.id == idea_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Idea not found")
        record.status = IdeaStatus.ANALYZED.value
        record.analyzed_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "status": "analyzed",
            "id": idea_id,
            "ticker": record.ticker,
        }


class StatusUpdateRequest(BaseModel):
    """Request body for status transition."""
    status: str = Field(
        ...,
        description="New status: active, analyzed, validated, in_portfolio, dismissed",
    )


@router.patch("/{idea_id}/status", summary="Update idea status")
async def update_idea_status(idea_id: int, body: StatusUpdateRequest):
    """Transition an idea to a new status in the tracking pipeline."""
    # Validate status value
    try:
        new_status = IdeaStatus(body.status)
    except ValueError:
        valid = [s.value for s in IdeaStatus]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{body.status}'. Valid: {valid}",
        )

    with SessionLocal() as db:
        record = db.query(IdeaRecord).filter(IdeaRecord.id == idea_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Idea not found")
        record.status = new_status.value
        if new_status == IdeaStatus.ANALYZED:
            record.analyzed_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "id": idea_id,
            "ticker": record.ticker,
            "status": new_status.value,
        }


# ── Distributed Scanning ─────────────────────────────────────────────────────

class DistributedScanRequest(BaseModel):
    """Request body for distributed universe scan."""
    tickers: list[str] = Field(
        ..., min_length=1, max_length=5000,
        description="Full universe of tickers to scan (supports up to 5000)",
    )
    chunk_size: int = Field(50, ge=10, le=200)
    fallback_to_local: bool = Field(True)


@router.post("/scan/distributed", summary="Start distributed scan")
async def start_distributed_scan(body: DistributedScanRequest):
    """
    Submit a large universe scan for distributed processing.
    Returns a scan job ID for status polling.
    """
    from src.engines.idea_generation.distributed.dispatcher import ScanDispatcher
    from src.engines.idea_generation.distributed.models import (
        DistributedScanConfig,
        ScanStatus,
    )

    config = DistributedScanConfig(
        chunk_size=body.chunk_size,
        fallback_to_local=body.fallback_to_local,
    )
    dispatcher = ScanDispatcher(config=config)
    job = dispatcher.dispatch(tickers=body.tickers)

    # If fell back to local, run immediately
    if job.status == ScanStatus.PROCESSING and not job.task_ids:
        result = await get_engine().scan(tickers=body.tickers)
        job.status = ScanStatus.COMPLETE
        job.total_ideas = len(result.ideas)
        return {
            "scan_id": job.scan_id,
            "status": job.status.value,
            "mode": "local_fallback",
            "ideas_found": len(result.ideas),
            "scan_duration_ms": result.scan_duration_ms,
            "ideas": [
                {
                    "ticker": i.ticker,
                    "idea_type": i.idea_type.value,
                    "signal_strength": i.signal_strength,
                    "confidence": i.confidence.value,
                }
                for i in result.ideas[:20]
            ],
        }

    return {
        "scan_id": job.scan_id,
        "status": job.status.value,
        "mode": "distributed",
        "total_tickers": job.total_tickers,
        "total_chunks": job.total_chunks,
        "chunk_size": body.chunk_size,
    }


@router.get("/scan/{scan_id}/status", summary="Poll scan status")
async def get_scan_status(scan_id: str):
    """Poll the progress of a distributed scan."""
    from src.engines.idea_generation.distributed.aggregator import ResultAggregator

    aggregator = ResultAggregator()
    status = aggregator.get_status(scan_id)
    if not status:
        raise HTTPException(status_code=404, detail="Scan not found")
    return status


@router.get("/scan/{scan_id}/results", summary="Get scan results")
async def get_scan_results(scan_id: str):
    """Get aggregated results from a distributed scan."""
    from src.engines.idea_generation.distributed.aggregator import ResultAggregator

    aggregator = ResultAggregator()
    result = aggregator.collect(scan_id)
    if not result:
        raise HTTPException(status_code=404, detail="Scan not found")
    return {
        "universe_size": result.universe_size,
        "ideas_found": len(result.ideas),
        "scan_duration_ms": result.scan_duration_ms,
        "detector_stats": result.detector_stats,
        "ideas": [
            {
                "ticker": i.ticker,
                "idea_type": i.idea_type.value,
                "signal_strength": i.signal_strength,
                "confidence": i.confidence.value,
                "priority": i.priority,
            }
            for i in result.ideas
        ],
    }


@router.delete("/scan/{scan_id}", summary="Cancel a scan")
async def cancel_scan(scan_id: str):
    """Cancel a running distributed scan."""
    from src.engines.idea_generation.distributed.dispatcher import ScanDispatcher

    dispatcher = ScanDispatcher()
    success = dispatcher.cancel_job(scan_id)
    if not success:
        raise HTTPException(status_code=404, detail="Scan not found or already complete")
    return {"status": "cancelled", "scan_id": scan_id}


# ── Universe Discovery Endpoints ─────────────────────────────────────────────


class AutoScanRequest(BaseModel):
    """Request body for auto-discovery scan."""
    sources: list[str] = Field(
        default=["static_index"],
        description="Universe sources to use: static_index, portfolio, idea_history, screener, sector_rotation, custom",
    )
    strategy_profile: str | None = Field(
        None,
        description="Strategy profile key (e.g. 'swing', 'deep_value')",
    )
    max_tickers: int = Field(300, ge=1, le=500)
    custom_tickers: list[str] = Field(
        default_factory=list,
        description="Explicit tickers when 'custom' source is included",
    )
    index_name: str = Field("sp500", description="Index for static_index source")


@router.post("/scan/auto", summary="Auto-discover universe and scan")
async def auto_scan(body: AutoScanRequest):
    """Auto-discover the ticker universe and run a full scan."""
    # Parse sources
    try:
        sources = [UniverseSource(s) for s in body.sources]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    universe_request = UniverseRequest(
        sources=sources,
        max_tickers=body.max_tickers,
        custom_tickers=body.custom_tickers,
        index_name=body.index_name,
        strategy_profile=body.strategy_profile,
    )

    engine = get_engine(strategy_profile_key=body.strategy_profile)
    result = await engine.auto_scan(universe_request=universe_request)

    return {
        "scan_id": result.scan_id,
        "universe_size": result.universe_size,
        "ideas_found": len(result.ideas),
        "scan_duration_ms": result.scan_duration_ms,
        "detector_stats": result.detector_stats,
        "strategy_profile": body.strategy_profile,
        "ideas": [
            {
                "id": idea.id,
                "ticker": idea.ticker,
                "name": idea.name,
                "sector": idea.sector,
                "idea_type": idea.idea_type.value,
                "confidence": idea.confidence.value,
                "signal_strength": idea.signal_strength,
                "confidence_score": idea.confidence_score,
                "priority": idea.priority,
                "signals": [s.model_dump() for s in idea.signals],
                "status": idea.status.value,
                "generated_at": idea.generated_at.isoformat(),
                "metadata": idea.metadata,
            }
            for idea in result.ideas
        ],
    }


@router.get("/universe/sources", summary="List universe sources")
async def list_universe_sources():
    """Return all available universe discovery sources."""
    return {
        "sources": default_universe_service._registry.list_sources(),
        "total": len(default_universe_service._registry),
    }


class UniversePreviewRequest(BaseModel):
    """Request body for universe preview."""
    sources: list[str] = Field(
        default=["static_index"],
        description="Universe sources to use",
    )
    max_tickers: int = Field(50, ge=1, le=500)
    custom_tickers: list[str] = Field(default_factory=list)
    index_name: str = Field("sp500")


@router.post("/universe/preview", summary="Preview discovered tickers")
async def preview_universe(body: UniversePreviewRequest):
    """Preview the tickers that would be discovered without running a scan."""
    try:
        sources = [UniverseSource(s) for s in body.sources]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    request = UniverseRequest(
        sources=sources,
        max_tickers=body.max_tickers,
        custom_tickers=body.custom_tickers,
        index_name=body.index_name,
    )

    result = default_universe_service.discover(request)
    return result.to_dict()
