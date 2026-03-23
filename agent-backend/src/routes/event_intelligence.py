"""
src/routes/event_intelligence.py
──────────────────────────────────────────────────────────────────────────────
API endpoints for the Structured Event Intelligence Engine.

Provides:
  GET  /alpha/events/calendar           → Event calendar view
  GET  /alpha/events/catalyst/{ticker}  → Catalyst score for a ticker
  GET  /alpha/events/deals              → Active M&A deals with spreads
  POST /alpha/events/deals              → Register a new M&A deal
  POST /alpha/events/analyze            → Full event intelligence report
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.engines.event_intelligence.engine import EventIntelligenceEngine
from src.engines.event_intelligence.models import (
    CorporateEvent,
    EventType,
    EventStatus,
    ImpactLevel,
)

logger = logging.getLogger("365advisers.routes.event_intelligence")

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/alpha/events", tags=["Alpha: Event Intelligence"], dependencies=[Depends(get_current_user)])

# Shared engine instance (in production, this would use dependency injection)
_engine = EventIntelligenceEngine()

# Seed FOMC meetings on import
_engine.calendar.seed_fed_meetings(2026)


# ── Request schemas ──────────────────────────────────────────────────────────

class AddEventRequest(BaseModel):
    ticker: str
    event_type: str = "earnings"
    event_date: str = Field(description="ISO-8601 date string")
    title: str = ""
    description: str = ""
    expected_impact: str = "unknown"
    historical_avg_move_pct: float | None = None


class AddDealRequest(BaseModel):
    acquirer: str
    target: str
    deal_price: float = Field(ge=0.0)
    current_price: float = Field(ge=0.0)
    expected_close_date: str | None = Field(None, description="ISO-8601 date string")
    deal_type: str = "cash"
    risk_factors: list[str] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=1)
    lookforward_days: int = Field(30, ge=1, le=365)


class SeedEarningsRequest(BaseModel):
    ticker: str
    year: int = 2026
    quarter_end_months: list[int] = Field(default_factory=lambda: [3, 6, 9, 12])


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/calendar")
async def get_calendar(
    days_ahead: int = Query(30, ge=1, le=365),
    ticker: str | None = Query(None),
):
    """Get event calendar for upcoming events."""
    try:
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)
        tickers = [ticker] if ticker else _engine.calendar.tickers_with_events
        entries = _engine.calendar.get_calendar_view(now, end, tickers)
        return {
            "entries": [e.model_dump() for e in entries],
            "total_tickers": len(entries),
            "total_events": sum(len(e.events) for e in entries),
        }
    except Exception as e:
        logger.error("Calendar fetch failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalyst/{ticker}")
async def get_catalyst_score(ticker: str, days_ahead: int = Query(30, ge=1, le=365)):
    """Get catalyst score for a specific ticker."""
    try:
        upcoming = _engine.calendar.get_upcoming(ticker.upper(), days_ahead=days_ahead)
        score = _engine.catalyst_scorer.score(
            ticker=ticker.upper(),
            upcoming_events=upcoming,
            lookforward_days=days_ahead,
        )
        return score.model_dump()
    except Exception as e:
        logger.error("Catalyst score failed for %s: %s", ticker, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/deals")
async def get_active_deals():
    """Get all active M&A deals with current spreads."""
    try:
        deals = _engine.deals.get_active_deals()
        return {
            "deals": [d.model_dump() for d in deals],
            "total_active": len(deals),
        }
    except Exception as e:
        logger.error("Deals fetch failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deals")
async def register_deal(req: AddDealRequest):
    """Register a new M&A deal for spread tracking."""
    try:
        close_date = None
        if req.expected_close_date:
            close_date = datetime.fromisoformat(req.expected_close_date).replace(tzinfo=timezone.utc)

        deal = _engine.deals.add_deal(
            acquirer=req.acquirer.upper(),
            target=req.target.upper(),
            deal_price=req.deal_price,
            current_price=req.current_price,
            expected_close_date=close_date,
            deal_type=req.deal_type,
            risk_factors=req.risk_factors,
        )
        return deal.model_dump()
    except Exception as e:
        logger.error("Deal registration failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def analyze_events(req: AnalyzeRequest):
    """Generate a comprehensive event intelligence report for a set of tickers."""
    try:
        report = _engine.analyze(
            tickers=[t.upper() for t in req.tickers],
            lookforward_days=req.lookforward_days,
        )
        return report.model_dump()
    except Exception as e:
        logger.error("Event analysis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calendar/add")
async def add_event(req: AddEventRequest):
    """Add a custom event to the calendar."""
    try:
        event_type = EventType(req.event_type) if req.event_type else EventType.OTHER
        impact = ImpactLevel(req.expected_impact) if req.expected_impact else ImpactLevel.UNKNOWN

        event = CorporateEvent(
            ticker=req.ticker.upper(),
            event_type=event_type,
            event_date=datetime.fromisoformat(req.event_date).replace(tzinfo=timezone.utc),
            title=req.title,
            description=req.description,
            expected_impact=impact,
            historical_avg_move_pct=req.historical_avg_move_pct,
        )
        event_id = _engine.calendar.add_event(event)
        return {"event_id": event_id, "status": "added"}
    except Exception as e:
        logger.error("Event add failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calendar/seed-earnings")
async def seed_earnings(req: SeedEarningsRequest):
    """Seed estimated quarterly earnings dates for a ticker."""
    try:
        count = _engine.calendar.seed_quarterly_earnings(
            ticker=req.ticker.upper(),
            fiscal_quarter_end_months=req.quarter_end_months,
            year=req.year,
        )
        return {"ticker": req.ticker.upper(), "events_seeded": count}
    except Exception as e:
        logger.error("Earnings seed failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
