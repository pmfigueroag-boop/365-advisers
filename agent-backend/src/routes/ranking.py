"""
src/routes/ranking.py
──────────────────────────────────────────────────────────────────────────────
REST API endpoints for the Global Opportunity Ranking Engine.

POST /ranking/compute           → Compute ranking from provided data
GET  /ranking/global            → Latest global ranking
GET  /ranking/sector/{sector}   → Ranking for a sector
GET  /ranking/strategy/{type}   → Ranking for a strategy
GET  /ranking/top               → Top N with allocations
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.engines.ranking.engine import RankingEngine
from src.engines.ranking.models import RankingConfig

logger = logging.getLogger("365advisers.routes.ranking")

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/ranking", tags=["ranking"], dependencies=[Depends(get_current_user)])

# Shared engine and cached result
_engine = RankingEngine()
_latest_result = None


# ─── Request Models ─────────────────────────────────────────────────────────

class RankingComputeRequest(BaseModel):
    """Request to compute a ranking."""
    ideas: list[dict] = Field(
        ..., min_length=1,
        description="List of idea dicts with ticker, name, sector, etc.",
    )
    case_scores: dict[str, float] = Field(
        default_factory=dict,
        description="{ticker: CASE score 0-100}",
    )
    opp_scores: dict[str, float] = Field(
        default_factory=dict,
        description="{ticker: opportunity score 0-10}",
    )
    config: RankingConfig | None = None


# ─── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/compute")
async def compute_ranking(request: RankingComputeRequest):
    """Compute a new global ranking from provided data."""
    global _latest_result

    engine = RankingEngine(config=request.config) if request.config else _engine

    result = engine.rank(
        ideas=request.ideas,
        case_scores=request.case_scores,
        opp_scores=request.opp_scores,
    )

    _latest_result = result

    return {
        "universe_size": result.universe_size,
        "top_n": [r.model_dump() for r in result.top_n],
        "global_ranking": [r.model_dump() for r in result.global_ranking],
        "sectors": list(result.by_sector.keys()),
        "strategies": list(result.by_strategy.keys()),
        "computed_at": result.computed_at.isoformat(),
    }


@router.get("/global")
async def get_global_ranking():
    """Get the latest global ranking."""
    if not _latest_result:
        raise HTTPException(
            status_code=404,
            detail="No ranking computed yet. POST /ranking/compute first.",
        )
    return {
        "ranking": [r.model_dump() for r in _latest_result.global_ranking],
        "universe_size": _latest_result.universe_size,
        "computed_at": _latest_result.computed_at.isoformat(),
    }


@router.get("/sector/{sector}")
async def get_sector_ranking(sector: str):
    """Get ranking for a specific sector."""
    if not _latest_result:
        raise HTTPException(status_code=404, detail="No ranking computed yet.")

    sector_data = _latest_result.by_sector.get(sector)
    if not sector_data:
        available = list(_latest_result.by_sector.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Sector '{sector}' not found. Available: {available}",
        )
    return {
        "sector": sector,
        "ranking": [r.model_dump() for r in sector_data],
        "count": len(sector_data),
    }


@router.get("/strategy/{strategy_type}")
async def get_strategy_ranking(strategy_type: str):
    """Get ranking for a specific strategy type."""
    if not _latest_result:
        raise HTTPException(status_code=404, detail="No ranking computed yet.")

    strategy_data = _latest_result.by_strategy.get(strategy_type)
    if not strategy_data:
        available = list(_latest_result.by_strategy.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Strategy '{strategy_type}' not found. Available: {available}",
        )
    return {
        "strategy": strategy_type,
        "ranking": [r.model_dump() for r in strategy_data],
        "count": len(strategy_data),
    }


@router.get("/top")
async def get_top_opportunities():
    """Get top N opportunities with suggested allocations."""
    if not _latest_result:
        raise HTTPException(status_code=404, detail="No ranking computed yet.")
    return {
        "top": [r.model_dump() for r in _latest_result.top_n],
        "count": len(_latest_result.top_n),
        "computed_at": _latest_result.computed_at.isoformat(),
    }
