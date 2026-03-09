"""
src/engines/event_intelligence/
──────────────────────────────────────────────────────────────────────────────
Structured Event Intelligence Engine.

Provides:
  • Corporate event calendar (earnings, M&A, dividends, Fed, etc.)
  • Catalyst probability scoring
  • M&A deal-spread tracking
  • Event intelligence orchestration
"""

from src.engines.event_intelligence.models import (
    EventType,
    EventStatus,
    CorporateEvent,
    EventCalendarEntry,
    CatalystScore,
    DealSpread,
    EventIntelligenceReport,
)
from src.engines.event_intelligence.calendar import EventCalendar
from src.engines.event_intelligence.catalyst import CatalystScorer
from src.engines.event_intelligence.deal_spread import DealTracker
from src.engines.event_intelligence.engine import EventIntelligenceEngine

__all__ = [
    "EventType",
    "EventStatus",
    "CorporateEvent",
    "EventCalendarEntry",
    "CatalystScore",
    "DealSpread",
    "EventIntelligenceReport",
    "EventCalendar",
    "CatalystScorer",
    "DealTracker",
    "EventIntelligenceEngine",
]
