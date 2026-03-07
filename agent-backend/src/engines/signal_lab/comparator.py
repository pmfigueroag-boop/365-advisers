"""
src/engines/signal_lab/comparator.py
─────────────────────────────────────────────────────────────────────────────
SignalComparator — pairwise comparison, correlation matrix, and marginal value.

Given evaluated signals, computes:
  - Pairwise co-fire correlation
  - Overlap matrix (how often two signals fire on the same ticker/date)
  - Marginal IC contribution
"""

from __future__ import annotations

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class SignalComparator:
    """Compare multiple signals for redundancy and synergy analysis."""

    @staticmethod
    def compute_overlap_matrix(
        signal_fires: dict[str, list[dict]],
    ) -> dict:
        """Build an overlap matrix showing co-firing frequency.

        Args:
            signal_fires: {signal_id: [fire_dicts]} from SignalStore

        Returns:
            {
                "signals": [signal_ids],
                "matrix": [[overlap_count]],
                "normalized_matrix": [[overlap_pct]],
            }
        """
        signal_ids = sorted(signal_fires.keys())
        n = len(signal_ids)

        # Build fire-set per signal: set of (ticker, date)
        fire_sets: dict[str, set] = {}
        for sid in signal_ids:
            fire_sets[sid] = {
                (f["ticker"], f["fire_date"]) for f in signal_fires[sid]
            }

        # Compute overlap matrix
        matrix = [[0] * n for _ in range(n)]
        normalized = [[0.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = len(fire_sets[signal_ids[i]])
                    normalized[i][j] = 1.0
                else:
                    overlap = len(fire_sets[signal_ids[i]] & fire_sets[signal_ids[j]])
                    matrix[i][j] = overlap
                    denom = min(len(fire_sets[signal_ids[i]]), len(fire_sets[signal_ids[j]]))
                    normalized[i][j] = round(overlap / denom, 4) if denom > 0 else 0.0

        return {
            "signals": signal_ids,
            "matrix": matrix,
            "normalized_matrix": normalized,
        }

    @staticmethod
    def find_redundant_pairs(
        signal_fires: dict[str, list[dict]],
        threshold: float = 0.7,
    ) -> list[dict]:
        """Identify signal pairs with high overlap (potential redundancy).

        Args:
            signal_fires: {signal_id: [fire_dicts]}
            threshold: Overlap fraction above which signals are flagged

        Returns:
            List of {signal_a, signal_b, overlap_pct, overlap_count}
        """
        overlap = SignalComparator.compute_overlap_matrix(signal_fires)
        signals = overlap["signals"]
        norm = overlap["normalized_matrix"]
        pairs = []

        for i in range(len(signals)):
            for j in range(i + 1, len(signals)):
                if norm[i][j] >= threshold:
                    pairs.append({
                        "signal_a": signals[i],
                        "signal_b": signals[j],
                        "overlap_pct": norm[i][j],
                        "overlap_count": overlap["matrix"][i][j],
                    })

        pairs.sort(key=lambda p: p["overlap_pct"], reverse=True)
        return pairs

    @staticmethod
    def compute_marginal_value(
        evaluations: list[dict],
        signal_fires: dict[str, list[dict]],
    ) -> list[dict]:
        """Rank signals by marginal information value.

        Uses a greedy approach: start with the best-performing signal,
        then add signals that provide the most novel coverage.

        Args:
            evaluations: List of evaluation dicts from SignalEvaluator
            signal_fires: {signal_id: [fire_dicts]}

        Returns:
            Ranked list of {signal_id, marginal_tickers, cumulative_coverage, rank}
        """
        if not evaluations:
            return []

        # Sort by confidence descending as proxy for quality
        sorted_evals = sorted(evaluations, key=lambda e: e.get("avg_confidence", 0), reverse=True)

        fire_sets = {}
        for sid, fires in signal_fires.items():
            fire_sets[sid] = {(f["ticker"], f["fire_date"]) for f in fires}

        covered: set = set()
        result = []

        for rank, ev in enumerate(sorted_evals, 1):
            sid = ev["signal_id"]
            if sid not in fire_sets:
                continue

            fires = fire_sets[sid]
            novel = fires - covered
            covered |= fires

            result.append({
                "signal_id": sid,
                "signal_name": ev.get("signal_name", sid),
                "total_fires": len(fires),
                "novel_fires": len(novel),
                "marginal_pct": round(len(novel) / len(fires), 4) if fires else 0.0,
                "cumulative_coverage": len(covered),
                "rank": rank,
            })

        return result
