"""
src/engines/signal_lab/report.py
─────────────────────────────────────────────────────────────────────────────
LabReport — generate structured lab evaluation reports.

Combines results from Evaluator, Comparator, Stability, and Redundancy
into a single comprehensive report for a set of signals.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from .evaluator import SignalEvaluator
from .comparator import SignalComparator
from .stability import StabilityAnalyzer
from .redundancy import RedundancyDetector

logger = logging.getLogger(__name__)


class LabReport:
    """Generate comprehensive signal lab reports."""

    @staticmethod
    def generate(
        signal_fires: dict[str, list[dict]],
        run_stability: bool = True,
        overlap_threshold: float = 0.7,
    ) -> dict:
        """Generate a full lab report for a set of signals.

        Args:
            signal_fires: {signal_id: [fire_dicts]} from SignalStore
            run_stability: Whether to run bootstrap stability (slower)
            overlap_threshold: Threshold for redundancy detection

        Returns:
            Comprehensive report dict with evaluations, comparisons,
            stability, redundancy, and overall scores.
        """
        generated_at = datetime.now(timezone.utc).isoformat()

        # ── Evaluate each signal ─────────────────────────────────────────
        evaluations: dict[str, dict] = {}
        for signal_id, fires in signal_fires.items():
            evaluations[signal_id] = SignalEvaluator.evaluate(fires)

        # ── Stability analysis ───────────────────────────────────────────
        stability: dict[str, dict] = {}
        if run_stability:
            for signal_id, fires in signal_fires.items():
                if len(fires) >= 10:
                    stability[signal_id] = {
                        "bootstrap": StabilityAnalyzer.bootstrap_stability(fires),
                        "temporal": StabilityAnalyzer.temporal_stability(fires),
                    }

        # ── Comparisons ──────────────────────────────────────────────────
        overlap = SignalComparator.compute_overlap_matrix(signal_fires)
        redundant_pairs = SignalComparator.find_redundant_pairs(signal_fires, overlap_threshold)
        marginal_ranking = SignalComparator.compute_marginal_value(
            list(evaluations.values()), signal_fires
        )

        # ── Redundancy ───────────────────────────────────────────────────
        redundancy = RedundancyDetector.analyze(signal_fires, evaluations, overlap_threshold)

        # ── Library-wide scores ──────────────────────────────────────────
        avg_confidence = 0.0
        total_fires_all = 0
        all_tickers: set = set()

        for ev in evaluations.values():
            avg_confidence += ev.get("avg_confidence", 0.0)
            total_fires_all += ev.get("total_fires", 0)

        for fires in signal_fires.values():
            for f in fires:
                all_tickers.add(f.get("ticker", ""))

        n_signals = len(evaluations)
        library_quality = round(avg_confidence / n_signals, 4) if n_signals > 0 else 0.0

        # Diversity score: inverse of redundancy
        diversity = round(1.0 - redundancy["redundancy_score"], 4)

        return {
            "report_type": "signal_lab",
            "generated_at": generated_at,
            "signal_count": n_signals,
            "total_fires": total_fires_all,
            "unique_tickers": len(all_tickers),

            # Scores
            "library_quality": library_quality,
            "diversity_score": diversity,
            "redundancy_score": redundancy["redundancy_score"],

            # Details
            "evaluations": evaluations,
            "stability": stability,
            "overlap_matrix": overlap,
            "redundant_pairs": redundant_pairs,
            "marginal_ranking": marginal_ranking,
            "redundancy_analysis": redundancy,
        }

    @staticmethod
    def generate_summary(report: dict) -> dict:
        """Generate a compact summary from a full lab report."""
        # Top signals by confidence
        evaluations = report.get("evaluations", {})
        top_signals = sorted(
            evaluations.values(),
            key=lambda e: e.get("avg_confidence", 0),
            reverse=True,
        )[:10]

        # Most redundant pairs
        redundant = report.get("redundant_pairs", [])[:5]

        return {
            "signal_count": report.get("signal_count", 0),
            "library_quality": report.get("library_quality", 0),
            "diversity_score": report.get("diversity_score", 0),
            "top_signals": [
                {"signal_id": s["signal_id"], "confidence": s["avg_confidence"], "fires": s["total_fires"]}
                for s in top_signals
            ],
            "redundant_pairs_count": len(report.get("redundant_pairs", [])),
            "top_redundancies": redundant,
            "generated_at": report.get("generated_at"),
        }
