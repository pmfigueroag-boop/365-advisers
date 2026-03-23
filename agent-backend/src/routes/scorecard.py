"""
src/routes/scorecard.py
─────────────────────────────────────────────────────────────────────────────
REST API for the Live Performance Scorecard.

Endpoints:
  Scorecard:    Full scorecard, signal-level, idea-level metrics
  Attribution:  Alpha attribution by signal and category
  Tracking:     Pending tickers for forward-return fill
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from src.engines.scorecard import (
    AttributionEngine,
    PnLCalculator,
    PerformanceTracker,
    ScorecardAggregator,
)

logger = logging.getLogger("365advisers.routes.scorecard")

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/scorecard", tags=["scorecard"], dependencies=[Depends(get_current_user)])

# ── Singletons ────────────────────────────────────────────────────────────────

_tracker = PerformanceTracker()
_pnl = PnLCalculator()
_attribution = AttributionEngine()
_aggregator = ScorecardAggregator()


# ═══════════════════════════════════════════════════════════════════════════════
#  SCORECARD
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/summary")
def get_scorecard_summary(horizon: str = Query(default="20d", pattern="^(1d|5d|20d|60d)$")):
    """Get the full consolidated scorecard."""
    scorecard = _aggregator.generate_scorecard(horizon)
    return scorecard.model_dump()


@router.get("/signals")
def get_signal_scorecards(horizon: str = Query(default="20d", pattern="^(1d|5d|20d|60d)$")):
    """Get performance metrics for all tracked signals."""
    metrics = _pnl.compute_all_signals(horizon)
    return {"horizon": horizon, "signals": metrics, "count": len(metrics)}


@router.get("/signals/{signal_id}")
def get_signal_scorecard(
    signal_id: str,
    horizon: str = Query(default="20d", pattern="^(1d|5d|20d|60d)$"),
):
    """Get performance metrics for a specific signal."""
    return _pnl.compute_signal_metrics(signal_id, horizon)


# ═══════════════════════════════════════════════════════════════════════════════
#  ATTRIBUTION
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/attribution/signals")
def get_signal_attribution(horizon: str = Query(default="20d", pattern="^(1d|5d|20d|60d)$")):
    """Get alpha attribution by signal."""
    return _attribution.compute_signal_attribution(horizon)


@router.get("/attribution/ideas")
def get_idea_attribution(horizon: str = Query(default="20d", pattern="^(1d|5d|20d|60d)$")):
    """Get alpha attribution by idea type."""
    return _attribution.compute_idea_attribution(horizon)


# ═══════════════════════════════════════════════════════════════════════════════
#  TRACKING
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/tracking/pending")
def get_pending_tracking():
    """Get list of tickers requiring price updates for P&L tracking."""
    tickers = _tracker.get_pending_tickers()
    return {"tickers": tickers, "count": len(tickers)}


@router.post("/tracking/update")
def update_tracking(prices: dict[str, float]):
    """Update forward returns with current prices.

    Body: {"AAPL": 185.50, "MSFT": 420.00, ...}
    """
    updated = _tracker.update_forward_returns(prices)
    return {"updated_fields": updated}
