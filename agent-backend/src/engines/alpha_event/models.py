"""
src/engines/alpha_event/models.py
──────────────────────────────────────────────────────────────────────────────
Data contracts for the Alpha Event Engine.
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class EventType(str, Enum):
    MERGER = "merger"
    ACQUISITION = "acquisition"
    INSIDER_BUY = "insider_buy"
    INSIDER_SELL = "insider_sell"
    EARNINGS_BEAT = "earnings_beat"
    EARNINGS_MISS = "earnings_miss"
    REGULATORY_ACTION = "regulatory_action"
    ACTIVIST_CAMPAIGN = "activist_campaign"
    BUYBACK = "buyback"
    DIVIDEND_CHANGE = "dividend_change"
    MANAGEMENT_CHANGE = "management_change"
    GUIDANCE_RAISE = "guidance_raise"
    GUIDANCE_CUT = "guidance_cut"


class EventSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class DetectedEvent(BaseModel):
    """A single corporate event detected from data sources."""
    event_type: EventType
    ticker: str
    headline: str = ""
    description: str = ""
    severity: EventSeverity = EventSeverity.MODERATE
    impact_score: float = Field(0.0, ge=-100, le=100)
    source: str = ""
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = Field(default_factory=dict)


class EventScore(BaseModel):
    """Aggregate event score for a ticker."""
    ticker: str
    composite_score: float = Field(0.0, ge=-100, le=100)
    event_count: int = 0
    bullish_events: int = 0
    bearish_events: int = 0
    most_significant: DetectedEvent | None = None
    signals: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EventTimeline(BaseModel):
    """Chronological event stream for a ticker."""
    ticker: str
    events: list[DetectedEvent] = Field(default_factory=list)


class EventDashboard(BaseModel):
    """Complete event intelligence output."""
    scores: list[EventScore] = Field(default_factory=list)
    timelines: list[EventTimeline] = Field(default_factory=list)
    active_alerts: list[DetectedEvent] = Field(default_factory=list)
    top_movers: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
