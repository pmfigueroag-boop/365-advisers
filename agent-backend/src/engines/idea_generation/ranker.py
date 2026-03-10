"""
src/engines/idea_generation/ranker.py
──────────────────────────────────────────────────────────────────────────────
Priority ranking system for investment ideas.

Composite score formula (v3 — configurable via RankingWeights)
──────────────────────────────────────────────────────────────
priority_score = (signal_strength × detector_weight × w_signal)   # intensity
               + (alpha_score × w_alpha)                          # attractiveness
               + (confidence_score × w_confidence)                # reliability
               + multi_detector_bonus

Weights are configurable per strategy profile via RankingWeights.
Falls back to institutional defaults when no weights are provided.

Ideas are sorted by descending priority_score and assigned integer ranks.
"""

from __future__ import annotations

from src.engines.idea_generation.models import (
    IdeaCandidate,
    ConfidenceLevel,
)


# ── Weight constants — institutional defaults ─────────────────────────────────

W_SIGNAL = 0.40
W_ALPHA = 0.35
W_CONFIDENCE = 0.25
MULTI_DETECTOR_BONUS = 0.10


def rank_ideas(
    ideas: list[IdeaCandidate],
    detector_weights: dict[str, float] | None = None,
    ranking_weights=None,
) -> list[IdeaCandidate]:
    """
    Assign a priority rank to each idea based on composite scoring.

    Parameters
    ----------
    ideas : list[IdeaCandidate]
        Unranked ideas from the scan phase.
    detector_weights : dict | None
        Optional override for detector type weights (e.g. {"value": 1.2}).
    ranking_weights : RankingWeights | None
        Optional weight vector from a strategy profile.
        When None, uses the institutional default constants.

    Returns
    -------
    list[IdeaCandidate]
        Ideas sorted by priority (1 = highest).
    """
    weights = detector_weights or {}

    # Resolve ranking weights: profile → defaults
    if ranking_weights is not None:
        _w_signal = ranking_weights.w_signal
        _w_alpha = ranking_weights.w_alpha
        _w_confidence = ranking_weights.w_confidence
        _multi_bonus_value = ranking_weights.multi_detector_bonus
    else:
        _w_signal = W_SIGNAL
        _w_alpha = W_ALPHA
        _w_confidence = W_CONFIDENCE
        _multi_bonus_value = MULTI_DETECTOR_BONUS

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
        signal_component = idea.signal_strength * w * _w_signal

        # Alpha score from CASE pipeline (stored in metadata)
        raw_alpha = idea.metadata.get("composite_alpha_score", 0.0)
        alpha_score = float(raw_alpha) if raw_alpha else 0.0
        alpha_component = alpha_score * _w_alpha

        confidence_component = idea.confidence_score * _w_confidence

        multi_bonus = (
            _multi_bonus_value
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
