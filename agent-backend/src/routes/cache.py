"""
src/routes/cache.py
──────────────────────────────────────────────────────────────────────────────
Cache management endpoints — extracted from main.py.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException

from src.services.cache_manager import cache_manager
from src.data.database import get_score_history

logger = logging.getLogger("365advisers.routes.cache")

router = APIRouter(tags=["Cache"])

cache = cache_manager.analysis
tech_cache = cache_manager.technical
fund_cache = cache_manager.fundamental


@router.get("/score-history")
def score_history(ticker: str, type: str = "fundamental", limit: int = 90):
    """Return the last N score records for a ticker."""
    if type not in ("fundamental", "technical"):
        raise HTTPException(status_code=400,
                            detail="type must be 'fundamental' or 'technical'")
    data = get_score_history(ticker, type, min(limit, 365))
    return {"ticker": ticker.upper(), "analysis_type": type, "history": data}


@router.get("/cache/status")
def cache_status_detail():
    """Return what's currently in both caches."""
    return {
        "fundamental": fund_cache.status(),
        "technical": tech_cache.status(),
    }


@router.delete("/cache/technical/{ticker}")
def invalidate_technical_cache(ticker: str):
    """Invalidate the technical cache for a specific ticker."""
    removed = tech_cache.invalidate(ticker)
    return {"ticker": ticker.upper(), "invalidated": removed}


@router.delete("/cache/fundamental/{ticker}")
def invalidate_fundamental_cache(ticker: str):
    """Invalidate the fundamental cache for a specific ticker."""
    removed = fund_cache.invalidate(ticker)
    return {"ticker": ticker.upper(), "invalidated": removed}


@router.delete("/cache/{ticker}")
def invalidate_cache(ticker: str):
    """Invalidate all caches for a specific ticker."""
    removed = cache.invalidate(ticker)
    return {"ticker": ticker.upper(), "invalidated": removed}


@router.get("/cache/legacy/status")
def cache_legacy_status():
    """Legacy cache status (analysis cache)."""
    return {"entries": cache.status(), "ttl_analysis_s": cache.TTL_ANALYSIS}
