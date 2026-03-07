"""
src/engines/scorecard/aggregator.py
─────────────────────────────────────────────────────────────────────────────
ScorecardAggregator — Top-level aggregation that combines signal metrics,
idea metrics, and attribution into a single dashboard-ready scorecard.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from .models import IdeaScorecard, ScorecardSummary, SignalScorecard
from .pnl import PnLCalculator
from .attribution import AttributionEngine

logger = logging.getLogger("365advisers.scorecard.aggregator")


class ScorecardAggregator:
    """Produces the consolidated live performance scorecard."""

    def __init__(self) -> None:
        self._pnl = PnLCalculator()
        self._attribution = AttributionEngine()

    def generate_scorecard(self, horizon: str = "20d") -> ScorecardSummary:
        """Generate the full scorecard with signal and idea breakdowns."""

        # ── Signal metrics ────────────────────────────────────────────────
        signal_metrics = self._pnl.compute_all_signals(horizon)
        attribution = self._attribution.compute_signal_attribution(horizon)

        signal_cards: list[SignalScorecard] = []
        for m in signal_metrics:
            if m.get("error"):
                continue
            card = SignalScorecard(
                signal_id=m["signal_id"],
                total_firings=m["total_firings"],
                hit_rate=m["hit_rate"],
                avg_return=m["avg_return"],
                avg_excess_return=m["avg_excess_return"],
                information_ratio=m["information_ratio"],
                signal_stability=m["signal_stability"],
                pnl_contribution=m["pnl_contribution_bps"],
                metrics_by_horizon={horizon: m},
            )

            # Enrich from attribution
            for attr_sig in attribution.get("signal_contributions", []):
                if attr_sig["signal_id"] == m["signal_id"]:
                    card.signal_name = attr_sig.get("signal_name", "")
                    card.category = attr_sig.get("category", "")
                    break

            signal_cards.append(card)

        # Sort by information ratio descending
        signal_cards.sort(key=lambda c: c.information_ratio, reverse=True)

        # ── Idea metrics ──────────────────────────────────────────────────
        idea_attribution = self._attribution.compute_idea_attribution(horizon)
        idea_cards: list[IdeaScorecard] = []
        for ia in idea_attribution.get("idea_contributions", []):
            idea_cards.append(
                IdeaScorecard(
                    idea_type=ia["idea_type"],
                    total_ideas=ia["count"],
                    hit_rate=ia["hit_rate"],
                    avg_excess_return=ia["avg_excess_return"],
                    quality_score=round(ia["hit_rate"] * 10, 2),
                )
            )

        # ── Summary ───────────────────────────────────────────────────────
        active_signals = [c for c in signal_cards if c.total_firings > 0]
        all_hit_rates = [c.hit_rate for c in active_signals]
        all_ir = [c.information_ratio for c in active_signals]

        summary = ScorecardSummary(
            total_signals_tracked=len(signal_cards),
            total_ideas_tracked=sum(ic.total_ideas for ic in idea_cards),
            overall_hit_rate=(
                sum(all_hit_rates) / len(all_hit_rates) if all_hit_rates else 0.0
            ),
            overall_information_ratio=(
                sum(all_ir) / len(all_ir) if all_ir else 0.0
            ),
            overall_alpha_bps=attribution.get("total_alpha_bps", 0.0),
            best_signal=(
                signal_cards[0].signal_id if signal_cards else ""
            ),
            worst_signal=(
                signal_cards[-1].signal_id if signal_cards else ""
            ),
            signals_above_threshold=sum(
                1 for c in active_signals if c.hit_rate >= 0.55
            ),
            signals_below_threshold=sum(
                1 for c in active_signals if c.hit_rate < 0.45
            ),
            last_updated=datetime.now(timezone.utc),
            signal_scorecards=signal_cards,
            idea_scorecards=idea_cards,
        )

        logger.info(
            "Scorecard generated: %d signals, %d ideas, alpha=%.2f bps",
            summary.total_signals_tracked,
            summary.total_ideas_tracked,
            summary.overall_alpha_bps,
        )
        return summary
