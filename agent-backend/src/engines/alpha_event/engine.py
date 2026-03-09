"""
src/engines/alpha_event/engine.py
──────────────────────────────────────────────────────────────────────────────
Alpha Event Engine — detects and scores corporate events that create
trading opportunities.

Data Sources: SEC EDGAR, GDELT, QuiverQuant (via EDPL)
Extends: event_intelligence/ (calendar, catalyst, deal tracking)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.alpha_event.models import (
    EventType, EventSeverity, DetectedEvent, EventScore,
    EventTimeline, EventDashboard,
)

logger = logging.getLogger("365advisers.alpha_event.engine")

# Impact weights by event type
_IMPACT: dict[EventType, float] = {
    EventType.MERGER: 80, EventType.ACQUISITION: 75,
    EventType.INSIDER_BUY: 40, EventType.INSIDER_SELL: -30,
    EventType.EARNINGS_BEAT: 50, EventType.EARNINGS_MISS: -50,
    EventType.REGULATORY_ACTION: -60, EventType.ACTIVIST_CAMPAIGN: 55,
    EventType.BUYBACK: 35, EventType.DIVIDEND_CHANGE: 25,
    EventType.MANAGEMENT_CHANGE: 20, EventType.GUIDANCE_RAISE: 45,
    EventType.GUIDANCE_CUT: -45,
}


class AlphaEventEngine:
    """
    Detects corporate events from structured data and produces
    opportunity scores.

    Usage::

        engine = AlphaEventEngine()
        events = engine.detect_events("AAPL", event_data_list)
        score = engine.score_ticker("AAPL", events)
        dashboard = engine.build_dashboard(all_scores, all_events)
    """

    def detect_events(self, ticker: str, raw_events: list[dict]) -> list[DetectedEvent]:
        """
        Parse raw event dicts into typed DetectedEvent objects.

        Parameters
        ----------
        raw_events : list[dict]
            Keys per event: event_type, headline, description, source,
                            severity, metadata, timestamp
        """
        detected = []
        for ev in raw_events:
            etype_str = ev.get("event_type", "").lower()
            try:
                etype = EventType(etype_str)
            except ValueError:
                continue
            sev_str = ev.get("severity", "moderate").lower()
            try:
                sev = EventSeverity(sev_str)
            except ValueError:
                sev = EventSeverity.MODERATE

            impact = _IMPACT.get(etype, 0)
            # Scale by severity
            sev_mult = {"critical": 1.5, "high": 1.2, "moderate": 1.0, "low": 0.6}
            impact *= sev_mult.get(sev.value, 1.0)
            impact = min(max(impact, -100), 100)

            detected.append(DetectedEvent(
                event_type=etype, ticker=ticker,
                headline=ev.get("headline", ""),
                description=ev.get("description", ""),
                severity=sev,
                impact_score=round(impact, 1),
                source=ev.get("source", ""),
                metadata=ev.get("metadata", {}),
            ))
        detected.sort(key=lambda e: abs(e.impact_score), reverse=True)
        return detected

    def score_ticker(self, ticker: str, events: list[DetectedEvent]) -> EventScore:
        """Compute aggregate event score for a ticker."""
        if not events:
            return EventScore(ticker=ticker)

        bullish = sum(1 for e in events if e.impact_score > 0)
        bearish = sum(1 for e in events if e.impact_score < 0)
        total_impact = sum(e.impact_score for e in events)
        # Normalize: average impact clamped to -100..100
        composite = total_impact / len(events) if events else 0
        composite = min(max(composite, -100), 100)

        signals = []
        most_sig = events[0] if events else None
        if most_sig:
            signals.append(f"{most_sig.event_type.value}: {most_sig.headline}")
        if bullish > bearish + 1:
            signals.append(f"Net bullish events ({bullish} vs {bearish})")
        elif bearish > bullish + 1:
            signals.append(f"Net bearish events ({bearish} vs {bullish})")

        # Insider clustering
        insider_buys = sum(1 for e in events if e.event_type == EventType.INSIDER_BUY)
        if insider_buys >= 3:
            signals.append(f"Insider buying cluster: {insider_buys} transactions")

        return EventScore(
            ticker=ticker, composite_score=round(composite, 1),
            event_count=len(events), bullish_events=bullish,
            bearish_events=bearish, most_significant=most_sig,
            signals=signals,
        )

    def build_dashboard(
        self,
        scores: list[EventScore],
        timelines: list[EventTimeline] | None = None,
    ) -> EventDashboard:
        """Build event intelligence dashboard."""
        # Top movers by absolute composite score
        sorted_scores = sorted(scores, key=lambda s: abs(s.composite_score), reverse=True)
        top_movers = [s.ticker for s in sorted_scores if abs(s.composite_score) > 20][:10]

        # Active alerts: high/critical severity events
        alerts = []
        for tl in (timelines or []):
            for ev in tl.events:
                if ev.severity in (EventSeverity.CRITICAL, EventSeverity.HIGH):
                    alerts.append(ev)
        alerts.sort(key=lambda e: abs(e.impact_score), reverse=True)

        return EventDashboard(
            scores=sorted_scores, timelines=timelines or [],
            active_alerts=alerts[:20], top_movers=top_movers,
        )
