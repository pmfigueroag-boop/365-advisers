"""
src/engines/event_intelligence/calendar.py
──────────────────────────────────────────────────────────────────────────────
Event Calendar Engine.

Manages a registry of corporate and market events, with querying
by ticker, date range, and event type. Can seed standard market
events (Fed meetings, index rebalances) and estimate earnings dates
from historical quarterly patterns.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from src.engines.event_intelligence.models import (
    CorporateEvent,
    EventCalendarEntry,
    EventStatus,
    EventType,
    ImpactLevel,
)

logger = logging.getLogger("365advisers.event_intelligence.calendar")


class EventCalendar:
    """
    In-memory event calendar with CRUD and querying.

    In a production system this would be backed by a database table;
    for now it uses an in-memory store keyed by ticker.
    """

    def __init__(self) -> None:
        self._events: dict[str, list[CorporateEvent]] = defaultdict(list)
        self._event_counter = 0

    # ── CRUD ─────────────────────────────────────────────────────────────

    def add_event(self, event: CorporateEvent) -> str:
        """Add an event to the calendar. Returns event_id."""
        self._event_counter += 1
        if not event.event_id:
            event.event_id = f"evt_{self._event_counter:06d}"
        self._events[event.ticker].append(event)
        logger.debug("Event added: %s %s %s", event.ticker, event.event_type, event.event_date)
        return event.event_id

    def add_events(self, events: list[CorporateEvent]) -> int:
        """Add multiple events. Returns count added."""
        for e in events:
            self.add_event(e)
        return len(events)

    def remove_event(self, ticker: str, event_id: str) -> bool:
        """Remove an event by ID."""
        events = self._events.get(ticker, [])
        for i, e in enumerate(events):
            if e.event_id == event_id:
                events.pop(i)
                return True
        return False

    # ── Queries ───────────────────────────────────────────────────────────

    def get_upcoming(
        self,
        ticker: str,
        days_ahead: int = 30,
    ) -> list[CorporateEvent]:
        """Get upcoming events for a ticker within a time horizon."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)
        events = self._events.get(ticker, [])
        return sorted(
            [
                e for e in events
                if e.status == EventStatus.UPCOMING
                and now <= e.event_date.replace(tzinfo=timezone.utc) <= cutoff
            ],
            key=lambda e: e.event_date,
        )

    def get_calendar_view(
        self,
        start_date: datetime,
        end_date: datetime,
        tickers: list[str] | None = None,
    ) -> list[EventCalendarEntry]:
        """Get a calendar view across multiple tickers for a date range."""
        results: list[EventCalendarEntry] = []
        target_tickers = tickers or list(self._events.keys())

        for ticker in target_tickers:
            events = self._events.get(ticker, [])
            in_range = [
                e for e in events
                if start_date <= e.event_date.replace(tzinfo=timezone.utc) <= end_date
            ]
            in_range.sort(key=lambda e: e.event_date)

            upcoming = [e for e in in_range if e.status == EventStatus.UPCOMING]
            next_evt = upcoming[0] if upcoming else None
            days_to = next_evt.days_until if next_evt else None

            results.append(EventCalendarEntry(
                ticker=ticker,
                events=in_range,
                next_event=next_evt,
                days_to_next_event=days_to,
                total_upcoming=len(upcoming),
            ))

        return results

    def get_all_events(self, ticker: str) -> list[CorporateEvent]:
        """Get all events for a ticker."""
        return sorted(self._events.get(ticker, []), key=lambda e: e.event_date)

    @property
    def total_events(self) -> int:
        """Total events across all tickers."""
        return sum(len(events) for events in self._events.values())

    @property
    def tickers_with_events(self) -> list[str]:
        """All tickers that have events registered."""
        return [t for t, events in self._events.items() if events]

    # ── Seed standard events ─────────────────────────────────────────────

    def seed_fed_meetings(self, year: int = 2026) -> int:
        """Seed the 8 annual FOMC meeting dates (approximate)."""
        # Approximate FOMC dates for 2026 (actual dates vary)
        fed_dates = [
            datetime(year, 1, 28, tzinfo=timezone.utc),
            datetime(year, 3, 18, tzinfo=timezone.utc),
            datetime(year, 5, 6, tzinfo=timezone.utc),
            datetime(year, 6, 17, tzinfo=timezone.utc),
            datetime(year, 7, 29, tzinfo=timezone.utc),
            datetime(year, 9, 16, tzinfo=timezone.utc),
            datetime(year, 11, 4, tzinfo=timezone.utc),
            datetime(year, 12, 16, tzinfo=timezone.utc),
        ]

        count = 0
        for date in fed_dates:
            event = CorporateEvent(
                ticker="MACRO",
                event_type=EventType.FED_MEETING,
                event_date=date,
                title=f"FOMC Meeting — {date.strftime('%b %d, %Y')}",
                description="Federal Open Market Committee interest rate decision.",
                expected_impact=ImpactLevel.HIGH,
                historical_avg_move_pct=1.2,
            )
            self.add_event(event)
            count += 1

        logger.info("Seeded %d Fed meetings for %d", count, year)
        return count

    def seed_quarterly_earnings(
        self,
        ticker: str,
        fiscal_quarter_end_months: list[int] | None = None,
        year: int = 2026,
    ) -> int:
        """
        Seed estimated quarterly earnings dates.

        Default pattern: report ~3 weeks after fiscal quarter end.
        """
        months = fiscal_quarter_end_months or [3, 6, 9, 12]
        count = 0
        for month in months:
            # Estimate: earnings ~21 days after quarter end
            q_end = datetime(year, month, 28, tzinfo=timezone.utc)
            earnings_date = q_end + timedelta(days=21)

            event = CorporateEvent(
                ticker=ticker,
                event_type=EventType.EARNINGS,
                event_date=earnings_date,
                title=f"{ticker} Q{months.index(month) + 1} {year} Earnings",
                description=f"Quarterly earnings report for {ticker}.",
                expected_impact=ImpactLevel.HIGH,
                historical_avg_move_pct=3.5,
            )
            self.add_event(event)
            count += 1

        logger.info("Seeded %d quarterly earnings for %s", count, ticker)
        return count
