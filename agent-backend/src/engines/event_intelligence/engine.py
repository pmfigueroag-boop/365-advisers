"""
src/engines/event_intelligence/engine.py
──────────────────────────────────────────────────────────────────────────────
Event Intelligence Orchestrator.

Aggregates the Event Calendar, Catalyst Scorer, and Deal Tracker
into a unified intelligence report for a set of tickers.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from src.engines.event_intelligence.models import (
    EventIntelligenceReport,
    EventCalendarEntry,
    CatalystScore,
    DealSpread,
)
from src.engines.event_intelligence.calendar import EventCalendar
from src.engines.event_intelligence.catalyst import CatalystScorer
from src.engines.event_intelligence.deal_spread import DealTracker

logger = logging.getLogger("365advisers.event_intelligence.engine")


class EventIntelligenceEngine:
    """
    Orchestrates event intelligence analysis across all sub-modules.

    Usage:
        engine = EventIntelligenceEngine()
        # Populate calendar and deals...
        engine.calendar.add_event(...)
        engine.deals.add_deal(...)
        # Run analysis
        report = engine.analyze(["AAPL", "MSFT", "GOOGL"])
    """

    def __init__(self) -> None:
        self.calendar = EventCalendar()
        self.catalyst_scorer = CatalystScorer()
        self.deals = DealTracker()

    def analyze(
        self,
        tickers: list[str],
        lookforward_days: int = 30,
    ) -> EventIntelligenceReport:
        """
        Generate a comprehensive event intelligence report.

        Args:
            tickers: List of ticker symbols to analyze.
            lookforward_days: Time horizon for event scanning.

        Returns:
            EventIntelligenceReport with calendar, catalyst scores, and active deals.
        """
        now = datetime.now(timezone.utc)
        end_date = now + timedelta(days=lookforward_days)

        # 1. Build calendar view
        calendar_entries: list[EventCalendarEntry] = []
        total_upcoming = 0
        for ticker in tickers:
            upcoming = self.calendar.get_upcoming(ticker, days_ahead=lookforward_days)
            next_evt = upcoming[0] if upcoming else None
            days_to = next_evt.days_until if next_evt else None

            entry = EventCalendarEntry(
                ticker=ticker,
                events=upcoming,
                next_event=next_evt,
                days_to_next_event=days_to,
                total_upcoming=len(upcoming),
            )
            calendar_entries.append(entry)
            total_upcoming += len(upcoming)

        # Also include macro events (Fed meetings, etc.)
        macro_upcoming = self.calendar.get_upcoming("MACRO", days_ahead=lookforward_days)
        if macro_upcoming:
            calendar_entries.append(EventCalendarEntry(
                ticker="MACRO",
                events=macro_upcoming,
                next_event=macro_upcoming[0],
                days_to_next_event=macro_upcoming[0].days_until,
                total_upcoming=len(macro_upcoming),
            ))
            total_upcoming += len(macro_upcoming)

        # 2. Compute catalyst scores
        catalyst_scores: list[CatalystScore] = []
        for ticker in tickers:
            upcoming = self.calendar.get_upcoming(ticker, days_ahead=lookforward_days)
            score = self.catalyst_scorer.score(
                ticker=ticker,
                upcoming_events=upcoming,
                lookforward_days=lookforward_days,
            )
            catalyst_scores.append(score)

        # Sort by score descending
        catalyst_scores.sort(key=lambda s: s.combined_catalyst_score, reverse=True)

        # 3. Collect active deals
        active_deals = self.deals.get_active_deals()
        # Filter to relevant tickers if possible
        relevant_deals = [
            d for d in active_deals
            if d.target in tickers or d.acquirer in tickers
        ] or active_deals  # Fall back to all if none match

        report = EventIntelligenceReport(
            calendar=calendar_entries,
            catalyst_scores=catalyst_scores,
            active_deals=relevant_deals,
            total_tickers_analyzed=len(tickers),
            total_upcoming_events=total_upcoming,
        )

        logger.info(
            "Event intelligence: %d tickers → %d events, %d catalysts, %d deals",
            len(tickers), total_upcoming,
            sum(1 for s in catalyst_scores if s.combined_catalyst_score > 0),
            len(relevant_deals),
        )

        return report
