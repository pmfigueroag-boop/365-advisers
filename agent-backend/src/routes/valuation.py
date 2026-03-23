"""
src/routes/valuation.py
──────────────────────────────────────────────────────────────────────────────
API endpoints for the Intrinsic Valuation Engine.

Provides:
  POST /alpha/valuation/dcf        → Run DCF on explicit inputs
  POST /alpha/valuation/comparable  → Run comparable analysis
  POST /alpha/valuation/full        → Full valuation report (DCF + Comps)
  GET  /alpha/valuation/margin      → Margin of safety for given values
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.engines.valuation.dcf import DCFModel
from src.engines.valuation.comparable import ComparableAnalysis
from src.engines.valuation.margin_of_safety import MarginCalculator
from src.engines.valuation.engine import ValuationEngine
from src.engines.valuation.models import (
    DCFInput,
    ComparableInput,
    PeerMultiple,
)

logger = logging.getLogger("365advisers.routes.valuation")

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/alpha/valuation", tags=["Alpha: Valuation"], dependencies=[Depends(get_current_user)])


# ── Request schemas ──────────────────────────────────────────────────────────

class FullValuationRequest(BaseModel):
    ticker: str
    current_price: float = Field(gt=0)
    eps: float | None = None
    book_value_per_share: float | None = None
    dcf_input: DCFInput | None = None
    peers: list[PeerMultiple] = Field(default_factory=list)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/dcf")
async def run_dcf(inputs: DCFInput):
    """Run a standalone DCF valuation."""
    try:
        result = DCFModel.calculate(inputs)
        return result.model_dump()
    except Exception as e:
        logger.error("DCF failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/comparable")
async def run_comparable(inputs: ComparableInput):
    """Run comparable company analysis."""
    try:
        result = ComparableAnalysis.analyze(inputs)
        return result.model_dump()
    except Exception as e:
        logger.error("Comparable failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/full")
async def full_valuation(req: FullValuationRequest):
    """Run a comprehensive valuation (DCF + Comparable + Margin of Safety)."""
    try:
        report = ValuationEngine.full_valuation(
            ticker=req.ticker.upper(),
            current_price=req.current_price,
            dcf_input=req.dcf_input,
            peers=req.peers if req.peers else None,
            eps=req.eps,
            book_value_per_share=req.book_value_per_share,
        )
        return report.model_dump()
    except Exception as e:
        logger.error("Full valuation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/margin")
async def margin_of_safety(
    ticker: str = Query(...),
    fair_value: float = Query(gt=0),
    current_price: float = Query(gt=0),
    eps: float | None = Query(None),
    book_value: float | None = Query(None),
):
    """Calculate margin of safety for a ticker."""
    try:
        result = MarginCalculator.calculate(
            ticker=ticker.upper(),
            fair_value=fair_value,
            current_price=current_price,
            eps=eps,
            book_value_per_share=book_value,
        )
        return result.model_dump()
    except Exception as e:
        logger.error("Margin calc failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
