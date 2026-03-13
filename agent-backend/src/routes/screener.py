"""
src/routes/screener.py
──────────────────────────────────────────────────────────────────────────────
REST API for the composable Screener Engine.

Endpoints:
  POST /analysis/screener          — Run screener with custom filters
  GET  /analysis/screener/filters  — List available filter fields
  GET  /analysis/screener/presets  — Pre-built screen configurations
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from src.engines.screener.contracts import ScreenerRequest
from src.engines.screener.engine import ScreenerEngine

logger = logging.getLogger("365advisers.routes.screener")

router = APIRouter(tags=["Screener"])

# Singleton engine — lazy init on first request
_engine: ScreenerEngine | None = None


def _get_engine() -> ScreenerEngine:
    global _engine
    if _engine is None:
        _engine = ScreenerEngine.default()
    return _engine


@router.post("/analysis/screener")
async def run_screener(request: ScreenerRequest):
    """
    Run the multi-criteria stock screener.

    Body:
    ```json
    {
        "filters": [
            {"field": "pe_ratio", "operator": "lte", "value": 20},
            {"field": "roic", "operator": "gte", "value": 0.15}
        ],
        "universe": "sp500",
        "limit": 20
    }
    ```
    """
    engine = _get_engine()

    if not request.filters and not request.preset:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one filter or a preset name.",
        )

    try:
        result = await asyncio.to_thread(engine.screen, request)
        return result.model_dump(mode="json")
    except Exception as exc:
        logger.error(f"Screener error: {exc}")
        raise HTTPException(status_code=500, detail=f"Screener failed: {str(exc)}")


@router.get("/analysis/screener/filters")
async def list_screener_filters():
    """Return all available filter fields grouped by category."""
    engine = _get_engine()
    fields = engine.available_fields()

    # Group by category
    grouped: dict[str, list[dict]] = {}
    for f in fields:
        cat = f.get("category", "other")
        grouped.setdefault(cat, []).append(f)

    return {
        "fields": fields,
        "categories": grouped,
        "total_fields": len(fields),
    }


@router.get("/analysis/screener/presets")
async def list_screener_presets():
    """Return pre-built screen configurations."""
    engine = _get_engine()
    presets = engine.get_presets()
    return {
        "presets": {
            name: {
                "label": cfg["label"],
                "description": cfg["description"],
                "filter_count": len(cfg["filters"]),
                "filters": cfg["filters"],
            }
            for name, cfg in presets.items()
        },
        "total": len(presets),
    }
