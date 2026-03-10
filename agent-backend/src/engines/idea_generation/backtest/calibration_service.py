"""
src/engines/idea_generation/backtest/calibration_service.py
──────────────────────────────────────────────────────────────────────────────
Calibration analysis for confidence_score vs realized outcomes.

Compares predicted confidence with actual hit_rate per bucket,
producing:
  - calibration_gap per bucket
  - overall calibration error (weighted mean absolute error)
  - monotonicity check (higher confidence → higher hit_rate?)
  - reliability summary

Design: descriptive statistics only — no ML.
Leaves foundation for future isotonic regression / Platt scaling.
"""

from __future__ import annotations

from collections import defaultdict

from src.engines.idea_generation.backtest.models import (
    CalibrationBucket,
    CalibrationReport,
    IdeaSnapshot,
    OutcomeResult,
)
from src.engines.idea_generation.metrics import get_collector


# ─── Bucket definitions ─────────────────────────────────────────────────────

DEFAULT_BUCKETS = [
    (0.0, 0.2, "0.0–0.2"),
    (0.2, 0.4, "0.2–0.4"),
    (0.4, 0.6, "0.4–0.6"),
    (0.6, 0.8, "0.6–0.8"),
    (0.8, 1.0, "0.8–1.0"),
]


def _assign_bucket(value: float) -> str:
    """Assign a value to its confidence bucket."""
    for low, high, label in DEFAULT_BUCKETS:
        if low <= value < high or (value == high and high == 1.0):
            return label
    return "unknown"


# ─── Calibration ─────────────────────────────────────────────────────────────


def compute_calibration(
    snapshots: list[IdeaSnapshot],
    outcomes: list[OutcomeResult],
    horizon: str = "",
) -> CalibrationReport:
    """Compute calibration report comparing confidence vs realized hit rate.

    Pure function — no side effects.
    """
    get_collector().increment("calibration_runs_total")

    # Index outcomes by snapshot_id
    outcome_map: dict[str, list[OutcomeResult]] = defaultdict(list)
    for o in outcomes:
        outcome_map[o.snapshot_id].append(o)

    # Populate buckets
    bucket_data: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    total_evaluated = 0

    for snap in snapshots:
        snap_outcomes = outcome_map.get(snap.snapshot_id, [])
        valid_outcomes = [
            o for o in snap_outcomes
            if o.data_available and o.raw_return is not None
        ]
        if not valid_outcomes:
            continue

        bucket = _assign_bucket(snap.confidence_score)
        for o in valid_outcomes:
            bucket_data[bucket].append((snap.confidence_score, o.is_hit))
            total_evaluated += 1

    # Build CalibrationBucket list
    buckets_result: list[CalibrationBucket] = []
    for low, high, label in DEFAULT_BUCKETS:
        entries = bucket_data.get(label, [])
        if not entries:
            buckets_result.append(CalibrationBucket(
                bucket_label=label,
                bucket_min=low,
                bucket_max=high,
            ))
            continue

        confidences = [c for c, _ in entries]
        hits = sum(1 for _, h in entries if h)
        total = len(entries)
        avg_conf = sum(confidences) / total
        observed_hr = hits / total

        # Calibration gap: difference between average confidence and hit_rate
        gap = avg_conf - observed_hr

        buckets_result.append(CalibrationBucket(
            bucket_label=label,
            bucket_min=low,
            bucket_max=high,
            total_count=total,
            hit_count=hits,
            observed_hit_rate=round(observed_hr, 4),
            average_confidence=round(avg_conf, 4),
            calibration_gap=round(gap, 4),
        ))

    # ── Compute average returns per bucket ──
    _add_avg_returns_to_buckets(buckets_result, snapshots, outcomes)

    # ── Overall calibration error (weighted MAE) ──
    total_weight = sum(b.total_count for b in buckets_result)
    if total_weight > 0:
        overall_error = sum(
            abs(b.calibration_gap) * b.total_count for b in buckets_result
        ) / total_weight
    else:
        overall_error = 0.0

    # ── Monotonicity check ──
    is_mono, violations = _check_monotonicity(buckets_result)

    return CalibrationReport(
        buckets=buckets_result,
        overall_calibration_error=round(overall_error, 4),
        is_monotonic=is_mono,
        monotonicity_violations=violations,
        total_evaluated=total_evaluated,
        horizon=horizon,
    )


def _add_avg_returns_to_buckets(
    buckets: list[CalibrationBucket],
    snapshots: list[IdeaSnapshot],
    outcomes: list[OutcomeResult],
) -> None:
    """Enrich buckets with average return data."""
    outcome_map: dict[str, list[OutcomeResult]] = defaultdict(list)
    for o in outcomes:
        outcome_map[o.snapshot_id].append(o)

    bucket_returns: dict[str, list[float]] = defaultdict(list)
    for snap in snapshots:
        bucket = _assign_bucket(snap.confidence_score)
        for o in outcome_map.get(snap.snapshot_id, []):
            if o.data_available and o.raw_return is not None:
                bucket_returns[bucket].append(o.raw_return)

    for b in buckets:
        returns = bucket_returns.get(b.bucket_label, [])
        if returns:
            b.average_return = round(sum(returns) / len(returns), 6)


def _check_monotonicity(
    buckets: list[CalibrationBucket],
) -> tuple[bool, list[str]]:
    """Check if higher confidence buckets have higher hit rates.

    Returns (is_monotonic, list of violations).
    """
    violations: list[str] = []
    non_empty = [b for b in buckets if b.total_count > 0]

    if len(non_empty) < 2:
        return True, []

    for i in range(len(non_empty) - 1):
        curr = non_empty[i]
        next_b = non_empty[i + 1]
        if next_b.observed_hit_rate < curr.observed_hit_rate:
            violations.append(
                f"{next_b.bucket_label} (hit_rate={next_b.observed_hit_rate:.2%}) < "
                f"{curr.bucket_label} (hit_rate={curr.observed_hit_rate:.2%})"
            )

    return len(violations) == 0, violations
