"""
src/routes/stat_arb.py
──────────────────────────────────────────────────────────────────────────────
API endpoints for the Statistical Arbitrage / Pairs Trading Engine.

Provides:
  POST /alpha/stat-arb/scan   → Scan universe for cointegrated pairs
  POST /alpha/stat-arb/test   → Test cointegration for a specific pair
  GET  /alpha/stat-arb/evaluate/{a}/{b} → Evaluate a pair with current signal
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.engines.stat_arb.scanner import PairScanner
from src.engines.stat_arb.engine import StatArbEngine
from src.engines.stat_arb.cointegration import engle_granger_test

logger = logging.getLogger("365advisers.routes.stat_arb")

router = APIRouter(prefix="/alpha/stat-arb", tags=["Alpha: Stat Arb"])


# ── Request schemas ──────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    """Request to scan a universe for cointegrated pairs."""
    universe_prices: dict[str, list[float]] = Field(
        ..., description="Dict mapping ticker → list of daily close prices"
    )
    sector_map: dict[str, str] = Field(
        default_factory=dict, description="Dict mapping ticker → sector"
    )
    min_correlation: float = Field(0.60, ge=0.0, le=1.0)
    max_pvalue: float = Field(0.05, ge=0.001, le=0.20)
    max_half_life: float = Field(60.0, ge=1.0, le=252.0)
    top_n: int = Field(20, ge=1, le=100)


class PairTestRequest(BaseModel):
    """Request to test cointegration for a specific pair."""
    prices_a: list[float] = Field(..., min_length=30)
    prices_b: list[float] = Field(..., min_length=30)
    ticker_a: str = "A"
    ticker_b: str = "B"


class EvaluateRequest(BaseModel):
    """Request to evaluate a specific pair."""
    ticker_a: str
    ticker_b: str
    prices_a: list[float] = Field(..., min_length=30)
    prices_b: list[float] = Field(..., min_length=30)
    entry_threshold: float = Field(2.0, ge=0.5, le=5.0)
    exit_threshold: float = Field(0.5, ge=0.1, le=2.0)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/scan")
async def scan_universe(req: ScanRequest):
    """Scan a universe of equities for cointegrated pairs."""
    try:
        result = PairScanner.scan(
            universe_prices=req.universe_prices,
            sector_map=req.sector_map if req.sector_map else None,
            min_correlation=req.min_correlation,
            max_pvalue=req.max_pvalue,
            max_half_life=req.max_half_life,
            top_n=req.top_n,
        )
        return result.model_dump()
    except Exception as e:
        logger.error("Pair scan failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test")
async def test_cointegration(req: PairTestRequest):
    """Run an Engle-Granger cointegration test on a specific pair."""
    try:
        result = engle_granger_test(req.prices_a, req.prices_b)
        result.ticker_a = req.ticker_a
        result.ticker_b = req.ticker_b
        return result.model_dump()
    except Exception as e:
        logger.error("Cointegration test failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate")
async def evaluate_pair(req: EvaluateRequest):
    """Evaluate a specific pair: cointegration + z-score + trading signal."""
    try:
        pair = StatArbEngine.evaluate_pair(
            ticker_a=req.ticker_a,
            ticker_b=req.ticker_b,
            prices_a=req.prices_a,
            prices_b=req.prices_b,
            entry_threshold=req.entry_threshold,
            exit_threshold=req.exit_threshold,
        )

        # Also construct a hypothetical trade
        trade = StatArbEngine.construct_trade(pair)

        return {
            "pair": pair.model_dump(),
            "trade": trade,
        }
    except Exception as e:
        logger.error("Pair evaluation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
