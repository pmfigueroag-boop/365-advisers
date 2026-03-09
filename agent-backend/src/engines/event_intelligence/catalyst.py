"""
src/engines/event_intelligence/catalyst.py
──────────────────────────────────────────────────────────────────────────────
Catalyst probability scoring.

Computes a composite catalyst score (0–100) based on event density,
historical price reaction, and event type weighting.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from src.engines.event_intelligence.models import (
    CorporateEvent,
    CatalystScore,
    EventType,
    ImpactLevel,
)

logger = logging.getLogger("365advisers.event_intelligence.catalyst")


class CatalystScorer:
    """
    Scores the catalyst intensity for a ticker based on upcoming events.

    Factors:
        1. Event density (events per 30-day window) — 30% weight
        2. Historical price reaction magnitude    — 40% weight
        3. Event type importance weight            — 30% weight
    """

    # Event type weights (higher = more impactful)
    EVENT_TYPE_WEIGHTS: dict[EventType, float] = {
        EventType.FDA_APPROVAL: 2.0,
        EventType.MERGER_ACQUISITION: 1.8,
        EventType.SPINOFF: 1.5,
        EventType.RESTRUCTURING: 1.4,
        EventType.EARNINGS: 1.0,
        EventType.GUIDANCE_UPDATE: 0.9,
        EventType.IPO_LOCKUP: 0.8,
        EventType.ANALYST_DAY: 0.7,
        EventType.BUYBACK: 0.5,
        EventType.INDEX_REBALANCE: 0.4,
        EventType.DIVIDEND: 0.3,
        EventType.FED_MEETING: 0.6,
        EventType.OTHER: 0.3,
    }

    # Default historical average moves per event type (%)
    DEFAULT_AVG_MOVES: dict[EventType, float] = {
        EventType.FDA_APPROVAL: 8.0,
        EventType.MERGER_ACQUISITION: 6.0,
        EventType.SPINOFF: 4.5,
        EventType.RESTRUCTURING: 3.5,
        EventType.EARNINGS: 3.5,
        EventType.GUIDANCE_UPDATE: 2.5,
        EventType.IPO_LOCKUP: 2.0,
        EventType.ANALYST_DAY: 1.5,
        EventType.BUYBACK: 1.0,
        EventType.INDEX_REBALANCE: 0.8,
        EventType.DIVIDEND: 0.5,
        EventType.FED_MEETING: 1.2,
        EventType.OTHER: 1.0,
    }

    @classmethod
    def score(
        cls,
        ticker: str,
        upcoming_events: list[CorporateEvent],
        lookforward_days: int = 30,
    ) -> CatalystScore:
        """
        Compute catalyst score for a ticker.

        Args:
            ticker: Stock ticker.
            upcoming_events: List of upcoming corporate events.
            lookforward_days: Time horizon for density calculation.

        Returns:
            CatalystScore with composite score (0–100).
        """
        if not upcoming_events:
            return CatalystScore(ticker=ticker)

        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=lookforward_days)

        # Filter to lookforward window
        in_window = [
            e for e in upcoming_events
            if now <= e.event_date.replace(tzinfo=timezone.utc) <= cutoff
        ]

        if not in_window:
            return CatalystScore(ticker=ticker)

        # 1. Event density
        density = len(in_window) / (lookforward_days / 30.0)
        density_score = min(100, density * 25)  # 4 events/30d → 100

        # 2. Historical reaction magnitude
        avg_moves = []
        for e in in_window:
            move = e.historical_avg_move_pct or cls.DEFAULT_AVG_MOVES.get(e.event_type, 1.0)
            avg_moves.append(move)
        avg_reaction = sum(avg_moves) / len(avg_moves) if avg_moves else 0
        reaction_score = min(100, avg_reaction * 12.5)  # 8% avg → 100

        # 3. Event type importance
        type_weights = [
            cls.EVENT_TYPE_WEIGHTS.get(e.event_type, 0.3)
            for e in in_window
        ]
        avg_type_weight = sum(type_weights) / len(type_weights) if type_weights else 0
        type_score = min(100, avg_type_weight * 50)  # 2.0 weight → 100

        # Composite
        composite = 0.30 * density_score + 0.40 * reaction_score + 0.30 * type_score
        composite = round(min(100, max(0, composite)), 1)

        # Find highest impact event
        highest = max(in_window, key=lambda e: cls.EVENT_TYPE_WEIGHTS.get(e.event_type, 0))

        event_types = list(set(e.event_type.value for e in in_window))

        return CatalystScore(
            ticker=ticker,
            catalyst_density=round(density, 2),
            upcoming_events_count=len(in_window),
            event_types=event_types,
            avg_expected_impact=round(avg_reaction, 2),
            combined_catalyst_score=composite,
            highest_impact_event=highest.title or highest.event_type.value,
        )
