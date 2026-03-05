"""
src/routes/signals.py
──────────────────────────────────────────────────────────────────────────────
API routes for the Alpha Signals Library.

Endpoints:
  GET  /signals/{ticker}          — Evaluate and return current signal profile
  GET  /signals/{ticker}/history  — Historical signal snapshots
  GET  /signals/registry          — List all registered signals
  POST /signals/registry/toggle   — Enable/disable signals
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.engines.alpha_signals.evaluator import SignalEvaluator
from src.engines.alpha_signals.combiner import SignalCombiner
from src.engines.alpha_signals.registry import registry
from src.engines.alpha_signals.models import SignalCategory
from src.engines.composite_alpha.engine import CompositeAlphaEngine
from src.engines.composite_alpha.models import CompositeAlphaResult
from src.data.database import SessionLocal, SignalSnapshot, CompositeAlphaHistory

# Reuse existing data fetching and feature extraction
from src.engines.idea_generation.engine import IdeaGenerationEngine

logger = logging.getLogger("365advisers.routes.signals")

router = APIRouter(prefix="/signals", tags=["Alpha Signals"])

# Singletons
_evaluator = SignalEvaluator()
_combiner = SignalCombiner()
_composite_alpha_engine = CompositeAlphaEngine()
_ige = IdeaGenerationEngine()


# ── Request / Response Schemas ────────────────────────────────────────────────

class ToggleRequest(BaseModel):
    signal_ids: list[str] = Field(..., min_length=1)
    enabled: bool


class SignalRegistryEntry(BaseModel):
    id: str
    name: str
    category: str
    description: str
    feature_path: str
    direction: str
    threshold: float
    enabled: bool
    weight: float
    tags: list[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/{ticker}",
    summary="Evaluate alpha signals for a ticker",
)
async def evaluate_signals(ticker: str):
    """
    Fetch market data, extract features, and evaluate all enabled alpha
    signals for the given ticker.  Returns the full SignalProfile + CompositeScore.
    """
    import asyncio

    symbol = ticker.upper().strip()
    logger.info(f"SIGNAL-API: Evaluating signals for {symbol}")

    # Reuse IGE's data fetching helpers
    fundamental_features = None
    technical_features = None

    try:
        from src.data.market_data import fetch_fundamental_data
        fund_raw = await asyncio.to_thread(fetch_fundamental_data, symbol)
        if fund_raw and "error" not in fund_raw:
            fundamental_features = _ige._build_fundamental_features(symbol, fund_raw)
    except Exception as exc:
        logger.debug(f"SIGNAL-API: Fundamental fetch failed for {symbol}: {exc}")

    try:
        from src.data.market_data import fetch_technical_data
        tech_raw = await asyncio.to_thread(fetch_technical_data, symbol)
        if tech_raw and "error" not in tech_raw:
            technical_features = _ige._build_technical_features(symbol, tech_raw)
    except Exception as exc:
        logger.debug(f"SIGNAL-API: Technical fetch failed for {symbol}: {exc}")

    if fundamental_features is None and technical_features is None:
        raise HTTPException(
            status_code=404,
            detail=f"No market data available for {symbol}",
        )

    # Evaluate signals
    profile = _evaluator.evaluate(symbol, fundamental_features, technical_features)
    composite = _combiner.combine(profile)

    # Compute Composite Alpha Score
    case_result = _composite_alpha_engine.compute(profile)

    # Persist snapshots and CASE history
    _persist_snapshots(symbol, profile)
    _persist_case_history(symbol, case_result)

    return {
        "ticker": symbol,
        "evaluated_at": profile.evaluated_at.isoformat(),
        "total_signals": profile.total_signals,
        "fired_signals": profile.fired_signals,
        "signals": [s.model_dump() for s in profile.signals if s.fired],
        "category_summary": {
            k: v.model_dump() for k, v in profile.category_summary.items()
        },
        "composite": composite.model_dump(),
        "composite_alpha": {
            "score": case_result.composite_alpha_score,
            "environment": case_result.signal_environment.value,
            "subscores": {
                k: v.model_dump() for k, v in case_result.subscores.items()
            },
            "active_categories": case_result.active_categories,
            "convergence_bonus": case_result.convergence_bonus,
            "cross_category_conflicts": case_result.cross_category_conflicts,
        },
    }


@router.get(
    "/{ticker}/history",
    summary="Get signal evaluation history",
)
async def get_signal_history(
    ticker: str,
    category: str | None = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=200),
):
    """Return historical signal snapshots for a ticker."""
    symbol = ticker.upper().strip()

    with SessionLocal() as db:
        query = db.query(SignalSnapshot).filter(
            SignalSnapshot.ticker == symbol,
        )
        if category:
            query = query.filter(SignalSnapshot.category == category)

        rows = (
            query.order_by(SignalSnapshot.evaluated_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": r.id,
                "ticker": r.ticker,
                "evaluated_at": r.evaluated_at.isoformat() if r.evaluated_at else None,
                "category": r.category,
                "composite_strength": r.composite_strength,
                "confidence": r.confidence,
                "fired_count": r.fired_count,
                "total_count": r.total_count,
                "signals": json.loads(r.signals_json or "[]"),
            }
            for r in rows
        ]


@router.get(
    "/registry/list",
    summary="List all registered signals",
)
async def list_registry():
    """Return all registered signal definitions with their enabled status."""
    signals = registry.get_all()
    return {
        "total": len(signals),
        "enabled": len([s for s in signals if s.enabled]),
        "summary": registry.summary(),
        "signals": [
            SignalRegistryEntry(
                id=s.id,
                name=s.name,
                category=s.category.value,
                description=s.description,
                feature_path=s.feature_path,
                direction=s.direction.value,
                threshold=s.threshold,
                enabled=s.enabled,
                weight=s.weight,
                tags=s.tags,
            ).model_dump()
            for s in signals
        ],
    }


@router.post(
    "/registry/toggle",
    summary="Enable or disable signals",
)
async def toggle_signals(body: ToggleRequest):
    """Enable or disable specific signals by their IDs."""
    registry.set_enabled_bulk(body.signal_ids, body.enabled)
    action = "enabled" if body.enabled else "disabled"
    logger.info(f"SIGNAL-REGISTRY: {action} {len(body.signal_ids)} signals")
    return {
        "status": action,
        "signal_ids": body.signal_ids,
        "registry_summary": registry.summary(),
    }


# ── Persistence helper ────────────────────────────────────────────────────────

def _persist_snapshots(ticker: str, profile):
    """Save per-category signal snapshots to the database."""
    try:
        with SessionLocal() as db:
            for cat_key, cat_score in profile.category_summary.items():
                cat_signals = [
                    s for s in profile.signals
                    if s.category.value == cat_key
                ]
                record = SignalSnapshot(
                    ticker=ticker,
                    category=cat_key,
                    signals_json=json.dumps(
                        [s.model_dump() for s in cat_signals]
                    ),
                    composite_strength=cat_score.composite_strength,
                    confidence=cat_score.confidence.value,
                    fired_count=cat_score.fired,
                    total_count=cat_score.total,
                )
                db.add(record)
            db.commit()
    except Exception as exc:
        logger.warning(f"SIGNAL-API: Failed to persist snapshots for {ticker}: {exc}")


def _persist_case_history(ticker: str, case_result: CompositeAlphaResult):
    """Save a Composite Alpha Score entry to the database."""
    try:
        subscores_data = {
            k: v.model_dump() for k, v in case_result.subscores.items()
        }
        with SessionLocal() as db:
            record = CompositeAlphaHistory(
                ticker=ticker,
                score=case_result.composite_alpha_score,
                environment=case_result.signal_environment.value,
                subscores_json=json.dumps(subscores_data),
                active_categories=case_result.active_categories,
                conflicts_json=json.dumps(case_result.cross_category_conflicts),
            )
            db.add(record)
            db.commit()
    except Exception as exc:
        logger.warning(f"SIGNAL-API: Failed to persist CASE for {ticker}: {exc}")
