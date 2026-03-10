"""
src/engines/idea_generation/backtest/analytics_service.py
──────────────────────────────────────────────────────────────────────────────
Aggregated analytics for measuring idea generation quality.

Produces GroupMetrics by detector, idea_type, confidence bucket,
signal_strength bucket, and horizon. All functions are pure —
they take lists of snapshots/outcomes and return results.

Answers questions like:
  - What detector has the best hit rate at 20D?
  - What idea_type produces the best average return?
  - Does higher confidence actually predict better outcomes?
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from src.engines.idea_generation.backtest.models import (
    EvaluationHorizon,
    GroupMetrics,
    IdeaSnapshot,
    OutcomeResult,
)


# ─── Bucket Definitions ──────────────────────────────────────────────────────

CONFIDENCE_BUCKETS = [
    (0.0, 0.2, "0.0–0.2"),
    (0.2, 0.4, "0.2–0.4"),
    (0.4, 0.6, "0.4–0.6"),
    (0.6, 0.8, "0.6–0.8"),
    (0.8, 1.0, "0.8–1.0"),
]

SIGNAL_STRENGTH_BUCKETS = [
    (0.0, 0.2, "0.0–0.2"),
    (0.2, 0.4, "0.2–0.4"),
    (0.4, 0.6, "0.4–0.6"),
    (0.6, 0.8, "0.6–0.8"),
    (0.8, 1.0, "0.8–1.0"),
]


def _bucket_label(value: float, buckets: list[tuple[float, float, str]]) -> str:
    """Find which bucket a value falls into."""
    for low, high, label in buckets:
        if low <= value < high or (value == high and high == 1.0):
            return label
    return "unknown"


# ─── Core Aggregation ────────────────────────────────────────────────────────


def compute_group_metrics(
    snapshots: list[IdeaSnapshot],
    outcomes: list[OutcomeResult],
    group_key: str,
    group_value: str,
    horizon: str = "",
) -> GroupMetrics:
    """Compute aggregated metrics for a group of snapshots + outcomes.

    This is a pure function — no side effects, no DB access.
    """
    # Filter outcomes with available data
    valid_outcomes = [o for o in outcomes if o.data_available and o.raw_return is not None]

    total_ideas = len(snapshots)
    total_evaluated = len(valid_outcomes)

    if total_evaluated == 0:
        return GroupMetrics(
            group_key=group_key,
            group_value=group_value,
            horizon=horizon,
            total_ideas=total_ideas,
            total_evaluated=0,
            coverage_ratio=0.0,
            average_confidence=_safe_mean([s.confidence_score for s in snapshots]),
            average_alpha_score=_safe_mean([s.alpha_score for s in snapshots]),
            average_signal_strength=_safe_mean([s.signal_strength for s in snapshots]),
        )

    returns = [o.raw_return for o in valid_outcomes if o.raw_return is not None]
    excess = [o.excess_return for o in valid_outcomes if o.excess_return is not None]
    hits = sum(1 for o in valid_outcomes if o.is_hit)
    losses = sum(1 for o in valid_outcomes if o.outcome_label.value == "loss")

    hit_rate = hits / total_evaluated if total_evaluated > 0 else 0.0
    avg_return = _safe_mean(returns)
    med_return = _safe_median(returns)
    avg_excess = _safe_mean(excess) if excess else 0.0
    win_loss = hits / losses if losses > 0 else float(hits) if hits > 0 else 0.0
    fpr = losses / total_evaluated if total_evaluated > 0 else 0.0
    coverage = total_evaluated / total_ideas if total_ideas > 0 else 0.0

    return GroupMetrics(
        group_key=group_key,
        group_value=group_value,
        horizon=horizon,
        total_ideas=total_ideas,
        total_evaluated=total_evaluated,
        hit_rate=round(hit_rate, 4),
        average_return=round(avg_return, 6),
        median_return=round(med_return, 6),
        average_excess_return=round(avg_excess, 6),
        win_loss_ratio=round(win_loss, 4),
        average_confidence=round(
            _safe_mean([s.confidence_score for s in snapshots]), 4,
        ),
        average_alpha_score=round(
            _safe_mean([s.alpha_score for s in snapshots]), 4,
        ),
        average_signal_strength=round(
            _safe_mean([s.signal_strength for s in snapshots]), 4,
        ),
        false_positive_rate=round(fpr, 4),
        coverage_ratio=round(coverage, 4),
    )


# ─── Grouping Functions ─────────────────────────────────────────────────────


def analytics_by_detector(
    snapshots: list[IdeaSnapshot],
    outcomes: list[OutcomeResult],
    horizon: str = "",
) -> list[GroupMetrics]:
    """Compute analytics grouped by detector."""
    return _group_and_compute(
        snapshots, outcomes,
        key_fn=lambda s: s.detector,
        group_key="detector",
        horizon=horizon,
    )


def analytics_by_idea_type(
    snapshots: list[IdeaSnapshot],
    outcomes: list[OutcomeResult],
    horizon: str = "",
) -> list[GroupMetrics]:
    """Compute analytics grouped by idea_type."""
    return _group_and_compute(
        snapshots, outcomes,
        key_fn=lambda s: s.idea_type,
        group_key="idea_type",
        horizon=horizon,
    )


def analytics_by_detector_and_type(
    snapshots: list[IdeaSnapshot],
    outcomes: list[OutcomeResult],
    horizon: str = "",
) -> list[GroupMetrics]:
    """Compute analytics grouped by detector + idea_type."""
    return _group_and_compute(
        snapshots, outcomes,
        key_fn=lambda s: f"{s.detector}:{s.idea_type}",
        group_key="detector:idea_type",
        horizon=horizon,
    )


def analytics_by_confidence_bucket(
    snapshots: list[IdeaSnapshot],
    outcomes: list[OutcomeResult],
    horizon: str = "",
) -> list[GroupMetrics]:
    """Compute analytics grouped by confidence_score bucket."""
    return _group_and_compute(
        snapshots, outcomes,
        key_fn=lambda s: _bucket_label(s.confidence_score, CONFIDENCE_BUCKETS),
        group_key="confidence_bucket",
        horizon=horizon,
    )


def analytics_by_signal_strength_bucket(
    snapshots: list[IdeaSnapshot],
    outcomes: list[OutcomeResult],
    horizon: str = "",
) -> list[GroupMetrics]:
    """Compute analytics grouped by signal_strength bucket."""
    return _group_and_compute(
        snapshots, outcomes,
        key_fn=lambda s: _bucket_label(s.signal_strength, SIGNAL_STRENGTH_BUCKETS),
        group_key="signal_strength_bucket",
        horizon=horizon,
    )


def analytics_summary(
    snapshots: list[IdeaSnapshot],
    outcomes: list[OutcomeResult],
    horizon: str = "",
) -> GroupMetrics:
    """Compute overall summary metrics (no grouping)."""
    return compute_group_metrics(
        snapshots, outcomes,
        group_key="overall",
        group_value="all",
        horizon=horizon,
    )


# ─── Internal helpers ────────────────────────────────────────────────────────


def _group_and_compute(
    snapshots: list[IdeaSnapshot],
    outcomes: list[OutcomeResult],
    key_fn,
    group_key: str,
    horizon: str = "",
) -> list[GroupMetrics]:
    """Group snapshots/outcomes and compute metrics per group."""
    # Index outcomes by snapshot_id
    outcome_by_snap: dict[str, list[OutcomeResult]] = defaultdict(list)
    for o in outcomes:
        outcome_by_snap[o.snapshot_id].append(o)

    # Group snapshots
    groups: dict[str, list[IdeaSnapshot]] = defaultdict(list)
    for s in snapshots:
        groups[key_fn(s)].append(s)

    results: list[GroupMetrics] = []
    for group_value, group_snaps in sorted(groups.items()):
        group_outcomes = []
        for s in group_snaps:
            group_outcomes.extend(outcome_by_snap.get(s.snapshot_id, []))
        metrics = compute_group_metrics(
            group_snaps, group_outcomes, group_key, group_value, horizon,
        )
        results.append(metrics)

    return results


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return statistics.mean(values)


def _safe_median(values: list[float]) -> float:
    if not values:
        return 0.0
    return statistics.median(values)
