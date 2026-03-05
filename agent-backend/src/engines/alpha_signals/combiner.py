"""
src/engines/alpha_signals/combiner.py
──────────────────────────────────────────────────────────────────────────────
Combines per-category signal scores into an overall CompositeScore.

The combiner takes a SignalProfile (output of the Evaluator) and produces
a cross-category assessment with multi-category convergence detection.
"""

from __future__ import annotations

from src.engines.alpha_signals.models import (
    SignalProfile,
    CompositeScore,
    CategoryScore,
    SignalCategory,
    ConfidenceLevel,
)


# Multi-category bonus threshold: activate when N+ categories fire
_MULTI_CATEGORY_THRESHOLD = 3
_MULTI_CATEGORY_BONUS = 0.15


class SignalCombiner:
    """
    Produce a CompositeScore from a SignalProfile.

    Usage::

        combiner = SignalCombiner()
        composite = combiner.combine(profile)
    """

    def combine(self, profile: SignalProfile) -> CompositeScore:
        """
        Compute cross-category composite score.

        1. Collect category composite_strength values.
        2. Find dominant category.
        3. Apply multi-category bonus if 3+ categories fire.
        4. Compute overall strength and confidence.
        """
        cat_scores = profile.category_summary
        if not cat_scores:
            return CompositeScore()

        # Active categories = those with at least one fired signal
        active = {
            k: v for k, v in cat_scores.items()
            if v.fired > 0
        }
        active_count = len(active)

        if active_count == 0:
            return CompositeScore(
                overall_strength=0.0,
                overall_confidence=ConfidenceLevel.LOW,
                category_scores=cat_scores,
                multi_category_bonus=False,
                dominant_category=None,
                active_categories=0,
            )

        # Compute mean strength across active categories
        strengths = [v.composite_strength for v in active.values()]
        mean_strength = sum(strengths) / len(strengths)

        # Multi-category bonus
        multi_bonus = active_count >= _MULTI_CATEGORY_THRESHOLD
        if multi_bonus:
            mean_strength = min(mean_strength + _MULTI_CATEGORY_BONUS, 1.0)

        # Dominant category: highest composite strength
        dominant_key = max(active, key=lambda k: active[k].composite_strength)
        dominant_category = SignalCategory(dominant_key)

        # Overall confidence from active category ratio
        total_categories = len(cat_scores)
        cat_ratio = active_count / max(total_categories, 1)
        if cat_ratio >= 0.5 and mean_strength >= 0.5:
            overall_conf = ConfidenceLevel.HIGH
        elif cat_ratio >= 0.3 or mean_strength >= 0.4:
            overall_conf = ConfidenceLevel.MEDIUM
        else:
            overall_conf = ConfidenceLevel.LOW

        return CompositeScore(
            overall_strength=round(mean_strength, 3),
            overall_confidence=overall_conf,
            category_scores=cat_scores,
            multi_category_bonus=multi_bonus,
            dominant_category=dominant_category,
            active_categories=active_count,
        )
