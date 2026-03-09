"""
src/engines/event_intelligence/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic data contracts for the Structured Event Intelligence subsystem.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ── Enumerations ─────────────────────────────────────────────────────────────

class EventType(str, Enum):
    """Types of corporate and market events."""
    EARNINGS = "earnings"
    MERGER_ACQUISITION = "merger_acquisition"
    DIVIDEND = "dividend"
    BUYBACK = "buyback"
    SPINOFF = "spinoff"
    FDA_APPROVAL = "fda_approval"
    FED_MEETING = "fed_meeting"
    IPO_LOCKUP = "ipo_lockup"
    ANALYST_DAY = "analyst_day"
    INDEX_REBALANCE = "index_rebalance"
    GUIDANCE_UPDATE = "guidance_update"
    RESTRUCTURING = "restructuring"
    OTHER = "other"


class EventStatus(str, Enum):
    """Current status of a tracked event."""
    UPCOMING = "upcoming"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DealStatus(str, Enum):
    """Status of an M&A deal."""
    ANNOUNCED = "announced"
    REGULATORY_REVIEW = "regulatory_review"
    SHAREHOLDER_VOTE = "shareholder_vote"
    APPROVED = "approved"
    CLOSED = "closed"
    TERMINATED = "terminated"


class ImpactLevel(str, Enum):
    """Expected or actual market impact magnitude."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


# ── Core Event Model ─────────────────────────────────────────────────────────

class CorporateEvent(BaseModel):
    """A single corporate or market event."""
    event_id: str = Field(default="", description="Unique event identifier")
    ticker: str
    event_type: EventType
    event_date: datetime
    status: EventStatus = EventStatus.UPCOMING
    title: str = ""
    description: str = ""
    expected_impact: ImpactLevel = ImpactLevel.UNKNOWN
    actual_impact: ImpactLevel | None = None
    historical_avg_move_pct: float | None = Field(
        None,
        description="Average absolute price move around this event type (%)",
    )
    metadata: dict = Field(default_factory=dict)

    @property
    def days_until(self) -> int:
        """Days until the event (negative if past)."""
        now = datetime.now(timezone.utc)
        delta = self.event_date.replace(tzinfo=timezone.utc) - now
        return delta.days


# ── Calendar Entry ───────────────────────────────────────────────────────────

class EventCalendarEntry(BaseModel):
    """Calendar view for a single ticker."""
    ticker: str
    events: list[CorporateEvent] = Field(default_factory=list)
    next_event: CorporateEvent | None = None
    days_to_next_event: int | None = None
    total_upcoming: int = 0


# ── Catalyst Score ───────────────────────────────────────────────────────────

class CatalystScore(BaseModel):
    """Composite catalyst intensity score for a ticker."""
    ticker: str
    catalyst_density: float = Field(
        0.0, ge=0.0,
        description="Events per 30-day window",
    )
    upcoming_events_count: int = 0
    event_types: list[str] = Field(default_factory=list)
    avg_expected_impact: float = Field(
        0.0, ge=0.0,
        description="Average historical move (%) across upcoming events",
    )
    combined_catalyst_score: float = Field(
        0.0, ge=0.0, le=100.0,
        description="Composite catalyst score (0–100)",
    )
    highest_impact_event: str = ""
    scored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Deal Spread ──────────────────────────────────────────────────────────────

class DealSpread(BaseModel):
    """M&A deal-spread tracking."""
    deal_id: str = ""
    acquirer: str
    target: str
    announced_date: datetime
    expected_close_date: datetime | None = None
    deal_price: float = Field(ge=0.0, description="Offer price per share")
    current_price: float = Field(ge=0.0, description="Current market price of target")
    spread_pct: float = Field(
        0.0,
        description="(deal_price - current_price) / current_price × 100",
    )
    annualized_spread_pct: float = Field(
        0.0,
        description="Spread annualized based on expected time to close",
    )
    deal_status: DealStatus = DealStatus.ANNOUNCED
    deal_type: str = "cash"  # cash, stock, mixed
    risk_factors: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


# ── Report Output ────────────────────────────────────────────────────────────

class EventIntelligenceReport(BaseModel):
    """Complete event intelligence report for a set of tickers."""
    calendar: list[EventCalendarEntry] = Field(default_factory=list)
    catalyst_scores: list[CatalystScore] = Field(default_factory=list)
    active_deals: list[DealSpread] = Field(default_factory=list)
    total_tickers_analyzed: int = 0
    total_upcoming_events: int = 0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
