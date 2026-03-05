"""
src/engines/idea_generation/ranker.py
──────────────────────────────────────────────────────────────────────────────
Priority ranking system for investment ideas.

Composite score formula:
  priority_score = (signal_strength × detector_weight)
                 + confidence_bonus
                 + multi_detector_bonus

Ideas are sorted by descending priority_score and assigned integer ranks.
"""

from __future__ import annotations

from src.engines.idea_generation.models import (
    IdeaCandidate,
    ConfidenceLevel,
)


# ── Bonus mappings ────────────────────────────────────────────────────────────

_CONFIDENCE_BONUS = {
    ConfidenceLevel.HIGH: 0.30,
    ConfidenceLevel.MEDIUM: 0.10,
    ConfidenceLevel.LOW: 0.0,
}


def rank_ideas(
    ideas: list[IdeaCandidate],
    detector_weights: dict[str, float] | None = None,
) -> list[IdeaCandidate]:
    """
    Assign a priority rank to each idea based on composite scoring.

    Parameters
    ----------
    ideas : list[IdeaCandidate]
        Unranked ideas from the scan phase.
    detector_weights : dict | None
        Optional override for detector type weights (e.g. {"value": 1.2}).

    Returns
    -------
    list[IdeaCandidate]
        Ideas sorted by priority (1 = highest).
    """
    weights = detector_weights or {}

    # Count how many detectors fired per ticker (multi-detector bonus)
    ticker_detector_count: dict[str, int] = {}
    for idea in ideas:
        ticker_detector_count[idea.ticker] = (
            ticker_detector_count.get(idea.ticker, 0) + 1
        )

    scored: list[tuple[float, IdeaCandidate]] = []
    for idea in ideas:
        w = weights.get(idea.idea_type.value, 1.0)
        base = idea.signal_strength * w
        conf_bonus = _CONFIDENCE_BONUS.get(idea.confidence, 0.0)
        multi_bonus = 0.5 if ticker_detector_count.get(idea.ticker, 0) >= 2 else 0.0

        composite = base + conf_bonus + multi_bonus
        scored.append((composite, idea))

    # Sort descending by composite score
    scored.sort(key=lambda x: x[0], reverse=True)

    # Assign integer priority ranks
    ranked: list[IdeaCandidate] = []
    for rank, (_, idea) in enumerate(scored, start=1):
        idea.priority = rank
        ranked.append(idea)

    return ranked
