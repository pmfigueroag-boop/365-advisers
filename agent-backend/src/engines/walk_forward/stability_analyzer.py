"""
src/engines/walk_forward/stability_analyzer.py
──────────────────────────────────────────────────────────────────────────────
Computes cross-fold stability scores for walk-forward validated signals.

Stability Score formula:
  0.40 × consistency_ratio   — % of folds with OOS hit rate > 50%
  0.30 × sharpe_stability    — 1 − CV(OOS Sharpe across folds)
  0.20 × alpha_persistence   — % of folds with OOS alpha > 0
  0.10 × qualification_rate  — % of folds where signal qualified
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict

from src.engines.alpha_signals.models import SignalCategory
from src.engines.walk_forward.models import (
    StabilityClassification,
    WFSignalFoldResult,
    WFSignalSummary,
)

logger = logging.getLogger("365advisers.walk_forward.stability_analyzer")


def _classify_stability(score: float) -> StabilityClassification:
    """Map a raw stability score to a classification."""
    if score >= 0.75:
        return StabilityClassification.ROBUST
    if score >= 0.50:
        return StabilityClassification.MODERATE
    if score >= 0.25:
        return StabilityClassification.WEAK
    return StabilityClassification.OVERFIT


class StabilityAnalyzer:
    """
    Compute cross-fold stability scores from walk-forward fold results.

    Usage::

        analyzer = StabilityAnalyzer()
        summaries = analyzer.analyze(fold_results, signal_categories)
    """

    # ── Weight vector ─────────────────────────────────────────────────────
    W_CONSISTENCY = 0.40
    W_SHARPE_STABILITY = 0.30
    W_ALPHA_PERSISTENCE = 0.20
    W_QUALIFICATION = 0.10

    def analyze(
        self,
        fold_results: list[WFSignalFoldResult],
        signal_meta: dict[str, tuple[str, SignalCategory]],
        total_folds: int,
    ) -> list[WFSignalSummary]:
        """
        Aggregate per-fold results into cross-fold summaries.

        Parameters
        ----------
        fold_results : list[WFSignalFoldResult]
            All fold results across all signals.
        signal_meta : dict[str, tuple[str, SignalCategory]]
            Mapping signal_id → (signal_name, category).
        total_folds : int
            Total number of folds in the run.

        Returns
        -------
        list[WFSignalSummary]
            One summary per signal, sorted by stability_score descending.
        """
        # Group results by signal_id
        by_signal: dict[str, list[WFSignalFoldResult]] = defaultdict(list)
        for r in fold_results:
            by_signal[r.signal_id].append(r)

        summaries: list[WFSignalSummary] = []

        for signal_id, results in by_signal.items():
            name, category = signal_meta.get(signal_id, (signal_id, SignalCategory.MOMENTUM))

            qualified_results = [r for r in results if r.qualified]
            oos_results = [
                r for r in qualified_results
                if r.oos_hit_rate is not None
            ]

            qualified_folds = len(qualified_results)
            qualification_rate = qualified_folds / total_folds if total_folds > 0 else 0.0

            if oos_results:
                oos_hit_rates = [r.oos_hit_rate for r in oos_results]  # type: ignore[arg-type]
                oos_sharpes = [r.oos_sharpe for r in oos_results]      # type: ignore[arg-type]
                oos_alphas = [r.oos_alpha for r in oos_results]        # type: ignore[arg-type]

                avg_oos_hit_rate = sum(oos_hit_rates) / len(oos_hit_rates)
                avg_oos_sharpe = sum(oos_sharpes) / len(oos_sharpes)
                avg_oos_alpha = sum(oos_alphas) / len(oos_alphas)
                total_oos_firings = sum(r.oos_firings for r in oos_results)

                consistency = self._consistency_ratio(oos_hit_rates)
                sharpe_stab = self._sharpe_stability(oos_sharpes)
                alpha_pers = self._alpha_persistence(oos_alphas)
            else:
                avg_oos_hit_rate = 0.0
                avg_oos_sharpe = 0.0
                avg_oos_alpha = 0.0
                total_oos_firings = 0
                consistency = 0.0
                sharpe_stab = 0.0
                alpha_pers = 0.0

            stability_score = (
                self.W_CONSISTENCY * consistency
                + self.W_SHARPE_STABILITY * sharpe_stab
                + self.W_ALPHA_PERSISTENCE * alpha_pers
                + self.W_QUALIFICATION * qualification_rate
            )

            summaries.append(WFSignalSummary(
                signal_id=signal_id,
                signal_name=name,
                category=category,
                total_folds=total_folds,
                qualified_folds=qualified_folds,
                avg_oos_hit_rate=round(avg_oos_hit_rate, 4),
                avg_oos_sharpe=round(avg_oos_sharpe, 4),
                avg_oos_alpha=round(avg_oos_alpha, 6),
                total_oos_firings=total_oos_firings,
                stability_score=round(stability_score, 4),
                stability_class=_classify_stability(stability_score),
                consistency_ratio=round(consistency, 4),
                sharpe_stability=round(sharpe_stab, 4),
                alpha_persistence=round(alpha_pers, 4),
                qualification_rate=round(qualification_rate, 4),
                fold_results=sorted(results, key=lambda r: r.fold_index),
            ))

        summaries.sort(key=lambda s: s.stability_score, reverse=True)

        robust = [s for s in summaries if s.stability_class == StabilityClassification.ROBUST]
        overfit = [s for s in summaries if s.stability_class == StabilityClassification.OVERFIT]
        logger.info(
            "STABILITY-ANALYZER: %d signals — %d ROBUST, %d OVERFIT",
            len(summaries), len(robust), len(overfit),
        )
        return summaries

    # ── Component metrics ─────────────────────────────────────────────────

    @staticmethod
    def _consistency_ratio(oos_hit_rates: list[float]) -> float:
        """Fraction of folds where OOS hit rate exceeds 50%."""
        if not oos_hit_rates:
            return 0.0
        above = sum(1 for hr in oos_hit_rates if hr > 0.50)
        return above / len(oos_hit_rates)

    @staticmethod
    def _sharpe_stability(oos_sharpes: list[float]) -> float:
        """1 − coefficient_of_variation(OOS Sharpe), clamped to [0, 1]."""
        if len(oos_sharpes) < 2:
            return 0.0
        mean = sum(oos_sharpes) / len(oos_sharpes)
        if abs(mean) < 1e-9:
            return 0.0
        variance = sum((s - mean) ** 2 for s in oos_sharpes) / (len(oos_sharpes) - 1)
        std = math.sqrt(variance)
        cv = std / abs(mean)
        return max(0.0, min(1.0, 1.0 - cv))

    @staticmethod
    def _alpha_persistence(oos_alphas: list[float]) -> float:
        """Fraction of folds where OOS alpha is positive."""
        if not oos_alphas:
            return 0.0
        positive = sum(1 for a in oos_alphas if a > 0)
        return positive / len(oos_alphas)
