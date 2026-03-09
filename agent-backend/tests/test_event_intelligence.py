"""
tests/test_event_intelligence.py
──────────────────────────────────────────────────────────────────────────────
Tests for the Structured Event Intelligence engine.
"""

from datetime import datetime, timezone, timedelta

import pytest

from src.engines.event_intelligence.models import (
    EventType,
    EventStatus,
    CorporateEvent,
    EventCalendarEntry,
    CatalystScore,
    DealSpread,
    DealStatus,
    ImpactLevel,
    EventIntelligenceReport,
)
from src.engines.event_intelligence.calendar import EventCalendar
from src.engines.event_intelligence.catalyst import CatalystScorer
from src.engines.event_intelligence.deal_spread import DealTracker
from src.engines.event_intelligence.engine import EventIntelligenceEngine


# ── Helpers ──────────────────────────────────────────────────────────────────

def _future(days: int = 10) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


def _past(days: int = 5) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _make_event(ticker="AAPL", etype=EventType.EARNINGS, days_ahead=10, impact=ImpactLevel.HIGH):
    return CorporateEvent(
        ticker=ticker,
        event_type=etype,
        event_date=_future(days_ahead),
        title=f"{ticker} {etype.value}",
        expected_impact=impact,
        historical_avg_move_pct=3.5,
    )


# ── Calendar Tests ───────────────────────────────────────────────────────────

class TestEventCalendar:
    def test_add_and_query(self):
        cal = EventCalendar()
        evt = _make_event("AAPL", days_ahead=5)
        cal.add_event(evt)
        upcoming = cal.get_upcoming("AAPL", days_ahead=10)
        assert len(upcoming) == 1
        assert upcoming[0].ticker == "AAPL"

    def test_filter_by_horizon(self):
        cal = EventCalendar()
        cal.add_event(_make_event("AAPL", days_ahead=5))
        cal.add_event(_make_event("AAPL", days_ahead=45))
        # Only first should be within 30 days
        upcoming = cal.get_upcoming("AAPL", days_ahead=30)
        assert len(upcoming) == 1

    def test_multiple_tickers(self):
        cal = EventCalendar()
        cal.add_event(_make_event("AAPL", days_ahead=5))
        cal.add_event(_make_event("MSFT", days_ahead=8))
        assert cal.total_events == 2
        assert len(cal.tickers_with_events) == 2

    def test_seed_fed_meetings(self):
        cal = EventCalendar()
        count = cal.seed_fed_meetings(2026)
        assert count == 8
        assert cal.total_events == 8

    def test_seed_quarterly_earnings(self):
        cal = EventCalendar()
        count = cal.seed_quarterly_earnings("AAPL", year=2026)
        assert count == 4

    def test_remove_event(self):
        cal = EventCalendar()
        evt = _make_event("AAPL")
        eid = cal.add_event(evt)
        assert cal.total_events == 1
        cal.remove_event("AAPL", eid)
        assert cal.total_events == 0

    def test_calendar_view(self):
        cal = EventCalendar()
        cal.add_event(_make_event("AAPL", days_ahead=5))
        cal.add_event(_make_event("MSFT", days_ahead=8))

        now = datetime.now(timezone.utc)
        end = now + timedelta(days=30)
        view = cal.get_calendar_view(now, end)
        assert len(view) == 2


# ── Catalyst Scorer Tests ────────────────────────────────────────────────────

class TestCatalystScorer:
    def test_no_events_zero_score(self):
        score = CatalystScorer.score("AAPL", [])
        assert score.combined_catalyst_score == 0
        assert score.upcoming_events_count == 0

    def test_earnings_event_scores(self):
        events = [_make_event("AAPL", EventType.EARNINGS, days_ahead=10)]
        score = CatalystScorer.score("AAPL", events)
        assert score.combined_catalyst_score > 0
        assert score.upcoming_events_count == 1

    def test_ma_scores_higher_than_dividend(self):
        ma_events = [_make_event("X", EventType.MERGER_ACQUISITION, days_ahead=10)]
        div_events = [_make_event("Y", EventType.DIVIDEND, days_ahead=10)]
        ma_score = CatalystScorer.score("X", ma_events)
        div_score = CatalystScorer.score("Y", div_events)
        assert ma_score.combined_catalyst_score > div_score.combined_catalyst_score

    def test_density_increases_score(self):
        # 1 event
        single = CatalystScorer.score("A", [_make_event("A", days_ahead=10)])
        # 3 events
        multi = CatalystScorer.score("A", [
            _make_event("A", days_ahead=5),
            _make_event("A", EventType.BUYBACK, days_ahead=10),
            _make_event("A", EventType.ANALYST_DAY, days_ahead=15),
        ])
        assert multi.combined_catalyst_score >= single.combined_catalyst_score

    def test_score_range(self):
        events = [
            _make_event("A", EventType.FDA_APPROVAL, days_ahead=5),
            _make_event("A", EventType.MERGER_ACQUISITION, days_ahead=10),
        ]
        score = CatalystScorer.score("A", events)
        assert 0 <= score.combined_catalyst_score <= 100


# ── Deal Spread Tests ────────────────────────────────────────────────────────

class TestDealTracker:
    def test_add_deal(self):
        tracker = DealTracker()
        deal = tracker.add_deal("AVGO", "VMW", deal_price=142.50, current_price=135.0)
        assert deal.acquirer == "AVGO"
        assert deal.target == "VMW"
        assert deal.spread_pct > 0  # positive spread = profit potential

    def test_spread_calculation(self):
        tracker = DealTracker()
        deal = tracker.add_deal("A", "B", deal_price=100.0, current_price=95.0)
        # Spread = (100 - 95) / 95 ≈ 5.26%
        assert deal.spread_pct == pytest.approx(5.0 / 95.0, abs=0.001)

    def test_annualized_spread(self):
        tracker = DealTracker()
        now = datetime.now(timezone.utc)
        deal = tracker.add_deal(
            "A", "B",
            deal_price=100.0, current_price=95.0,
            expected_close_date=now + timedelta(days=90),
        )
        # Annualized = raw_spread × (365/90)
        raw = 5.0 / 95.0
        expected_annual = raw * (365.0 / 90)
        assert deal.annualized_spread_pct == pytest.approx(expected_annual, abs=0.01)

    def test_update_price(self):
        tracker = DealTracker()
        deal = tracker.add_deal("A", "B", deal_price=100.0, current_price=95.0)
        initial_spread = deal.spread_pct
        updated = tracker.update_price(deal.deal_id, 98.0)
        assert updated is not None
        assert updated.current_price == 98.0
        # Spread should be smaller since 98 is closer to deal price of 100
        assert updated.spread_pct < initial_spread
        assert updated.spread_pct > 0  # still positive (98 < 100)

    def test_active_deals(self):
        tracker = DealTracker()
        tracker.add_deal("A", "B", deal_price=100.0, current_price=95.0)
        tracker.add_deal("C", "D", deal_price=50.0, current_price=47.0)
        assert len(tracker.get_active_deals()) == 2

    def test_deal_status_update(self):
        tracker = DealTracker()
        deal = tracker.add_deal("A", "B", deal_price=100.0, current_price=95.0)
        tracker.update_status(deal.deal_id, DealStatus.CLOSED)
        # Closed deals should not appear in active
        assert len(tracker.get_active_deals()) == 0


# ── Engine Orchestrator Tests ────────────────────────────────────────────────

class TestEventIntelligenceEngine:
    def test_analyze_empty(self):
        engine = EventIntelligenceEngine()
        report = engine.analyze(["AAPL", "MSFT"])
        assert isinstance(report, EventIntelligenceReport)
        assert report.total_tickers_analyzed == 2
        assert report.total_upcoming_events == 0

    def test_analyze_with_events(self):
        engine = EventIntelligenceEngine()
        engine.calendar.add_event(_make_event("AAPL", days_ahead=10))
        engine.calendar.add_event(_make_event("MSFT", EventType.BUYBACK, days_ahead=15))
        report = engine.analyze(["AAPL", "MSFT"])
        assert report.total_upcoming_events >= 2
        assert len(report.catalyst_scores) == 2

    def test_analyze_includes_deals(self):
        engine = EventIntelligenceEngine()
        engine.deals.add_deal("AVGO", "VMW", deal_price=142.5, current_price=135.0)
        report = engine.analyze(["VMW"])
        assert len(report.active_deals) >= 1

    def test_catalyst_scores_sorted(self):
        engine = EventIntelligenceEngine()
        engine.calendar.add_event(_make_event("AAPL", EventType.FDA_APPROVAL, days_ahead=5))
        engine.calendar.add_event(_make_event("MSFT", EventType.DIVIDEND, days_ahead=10))
        report = engine.analyze(["AAPL", "MSFT"])
        scores = report.catalyst_scores
        # Should be sorted by score descending
        if len(scores) >= 2 and scores[0].combined_catalyst_score > 0:
            assert scores[0].combined_catalyst_score >= scores[1].combined_catalyst_score


# ── Model Validation Tests ───────────────────────────────────────────────────

class TestModelValidation:
    def test_event_days_until(self):
        evt = CorporateEvent(
            ticker="AAPL",
            event_type=EventType.EARNINGS,
            event_date=_future(15),
        )
        assert 14 <= evt.days_until <= 16  # allow 1 day tolerance

    def test_deal_spread_model(self):
        deal = DealSpread(
            acquirer="A", target="B",
            announced_date=datetime.now(timezone.utc),
            deal_price=100.0,
            current_price=95.0,
            spread_pct=0.0526,
        )
        assert deal.spread_pct > 0

    def test_catalyst_score_range(self):
        score = CatalystScore(ticker="X", combined_catalyst_score=55.5)
        assert 0 <= score.combined_catalyst_score <= 100
