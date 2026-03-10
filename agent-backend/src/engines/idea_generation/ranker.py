"""
src/engines/idea_generation/ranker.py
──────────────────────────────────────────────────────────────────────────────
Priority ranking system for investment ideas.

Composite score formula (v2 — with confidence_score)
────────────────────────────────────────────────────
priority_score = (signal_strength × detector_weight × 0.40)   # intensity
               + (alpha_score × 0.35)                          # attractiveness
               + (confidence_score × 0.25)                     # reliability
               + multi_detector_bonus

This separates three independent dimensions:

    signal_strength — how intense is the signal right now?
    alpha_score     — how attractive is the opportunity overall?
    confidence_score — how reliable/credible is this detection?

An idea with high alpha but low confidence will rank below one with
moderately high alpha and very high confidence.

Ideas are sorted by descending priority_score and assigned integer ranks.
"""

from __future__ import annotations

from src.engines.idea_generation.models import (
    IdeaCandidate,
    ConfidenceLevel,
)


# ── Weight constants — easy to calibrate later ────────────────────────────────

W_SIGNAL = 0.40
W_ALPHA = 0.35
W_CONFIDENCE = 0.25
MULTI_DETECTOR_BONUS = 0.10


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

        # ── Three-dimensional composite score ──────────────────────────
        signal_component = idea.signal_strength * w * W_SIGNAL

        # Alpha score from CASE pipeline (stored in metadata)
        raw_alpha = idea.metadata.get("composite_alpha_score", 0.0)
        alpha_score = float(raw_alpha) if raw_alpha else 0.0
        alpha_component = alpha_score * W_ALPHA

        confidence_component = idea.confidence_score * W_CONFIDENCE

        multi_bonus = (
            MULTI_DETECTOR_BONUS
            if ticker_detector_count.get(idea.ticker, 0) >= 2
            else 0.0
        )

        composite = (
            signal_component
            + alpha_component
            + confidence_component
            + multi_bonus
        )
        scored.append((composite, idea))

    # Sort descending by composite score
    scored.sort(key=lambda x: x[0], reverse=True)

    # Assign integer priority ranks
    ranked: list[IdeaCandidate] = []
    for rank, (_, idea) in enumerate(scored, start=1):
        idea.priority = rank
        ranked.append(idea)

    return ranked
