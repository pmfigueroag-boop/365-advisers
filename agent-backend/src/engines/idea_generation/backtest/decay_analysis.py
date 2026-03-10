"""
src/engines/idea_generation/backtest/decay_analysis.py
──────────────────────────────────────────────────────────────────────────────
Alpha decay analysis across multiple evaluation horizons.

Measures how signal performance evolves over time:
  - Does alpha persist or dissipate?
  - What's the best holding horizon per detector?
  - Which detectors show rapid decay vs sustained alpha?

Reuses outcome data from the evaluator — no duplicate computation.
"""

from __future__ import annotations

from collections import defaultdict

from src.engines.idea_generation.backtest.models import (
    DecayPoint,
    DecayProfile,
    EvaluationHorizon,
    IdeaSnapshot,
    OutcomeResult,
)


# ─── Horizon ordering for analysis ──────────────────────────────────────────

HORIZON_ORDER = ["1D", "5D", "20D", "60D"]


def _horizon_sort_key(h: str) -> int:
    try:
        return HORIZON_ORDER.index(h)
    except ValueError:
        return 999


# ─── Decay Analysis ─────────────────────────────────────────────────────────


def compute_decay_profile(
    group_key: str,
    group_value: str,
    snapshots: list[IdeaSnapshot],
    outcomes: list[OutcomeResult],
) -> DecayProfile:
    """Compute alpha decay profile for a group of snapshots.

    Groups outcomes by horizon and computes hit_rate + avg_return
    at each point, then identifies best horizon and decay trend.
    """
    # Index outcomes by horizon
    by_horizon: dict[str, list[OutcomeResult]] = defaultdict(list)
    for o in outcomes:
        if o.data_available and o.raw_return is not None:
            by_horizon[o.horizon.value if isinstance(o.horizon, EvaluationHorizon) else o.horizon].append(o)

    points: list[DecayPoint] = []
    for h in HORIZON_ORDER:
        horizon_outcomes = by_horizon.get(h, [])
        if not horizon_outcomes:
            points.append(DecayPoint(horizon=h))
            continue

        returns = [o.raw_return for o in horizon_outcomes if o.raw_return is not None]
        hits = sum(1 for o in horizon_outcomes if o.is_hit)
        total = len(horizon_outcomes)

        avg_ret = sum(returns) / len(returns) if returns else 0.0
        hr = hits / total if total > 0 else 0.0

        points.append(DecayPoint(
            horizon=h,
            average_return=round(avg_ret, 6),
            hit_rate=round(hr, 4),
            sample_count=total,
        ))

    # Identify best horizon
    valid_points = [p for p in points if p.sample_count > 0]
    best_horizon = ""
    if valid_points:
        best = max(valid_points, key=lambda p: p.average_return)
        best_horizon = best.horizon

    # Detect decay: if performance consistently drops from best point onward
    decay_detected, decay_desc = _detect_decay(points)

    return DecayProfile(
        group_key=group_key,
        group_value=group_value,
        points=points,
        best_horizon=best_horizon,
        decay_detected=decay_detected,
        decay_description=decay_desc,
    )


def decay_by_detector(
    snapshots: list[IdeaSnapshot],
    outcomes: list[OutcomeResult],
) -> list[DecayProfile]:
    """Compute decay profiles grouped by detector."""
    return _group_and_decay(
        snapshots, outcomes,
        key_fn=lambda s: s.detector,
        group_key="detector",
    )


def decay_by_idea_type(
    snapshots: list[IdeaSnapshot],
    outcomes: list[OutcomeResult],
) -> list[DecayProfile]:
    """Compute decay profiles grouped by idea_type."""
    return _group_and_decay(
        snapshots, outcomes,
        key_fn=lambda s: s.idea_type,
        group_key="idea_type",
    )


def decay_summary(
    snapshots: list[IdeaSnapshot],
    outcomes: list[OutcomeResult],
) -> DecayProfile:
    """Compute overall decay profile (no grouping)."""
    return compute_decay_profile("overall", "all", snapshots, outcomes)


# ─── Internal ────────────────────────────────────────────────────────────────


def _group_and_decay(
    snapshots: list[IdeaSnapshot],
    outcomes: list[OutcomeResult],
    key_fn,
    group_key: str,
) -> list[DecayProfile]:
    """Group snapshots and compute decay per group."""
    outcome_by_snap: dict[str, list[OutcomeResult]] = defaultdict(list)
    for o in outcomes:
        outcome_by_snap[o.snapshot_id].append(o)

    groups: dict[str, list[IdeaSnapshot]] = defaultdict(list)
    for s in snapshots:
        groups[key_fn(s)].append(s)

    profiles: list[DecayProfile] = []
    for group_value, group_snaps in sorted(groups.items()):
        group_outcomes = []
        for s in group_snaps:
            group_outcomes.extend(outcome_by_snap.get(s.snapshot_id, []))
        profile = compute_decay_profile(group_key, group_value, group_snaps, group_outcomes)
        profiles.append(profile)

    return profiles


def _detect_decay(points: list[DecayPoint]) -> tuple[bool, str]:
    """Detect if alpha decays consistently after peak.

    Returns (decay_detected, description).
    """
    valid = [p for p in points if p.sample_count > 0]
    if len(valid) < 2:
        return False, "Insufficient data for decay detection"

    # Find peak return
    peak_idx = 0
    peak_return = valid[0].average_return
    for i, p in enumerate(valid):
        if p.average_return > peak_return:
            peak_return = p.average_return
            peak_idx = i

    # Check if returns decline after peak
    if peak_idx >= len(valid) - 1:
        return False, "Peak is at the longest horizon — no decay detected"

    post_peak = valid[peak_idx + 1:]
    declining = all(
        post_peak[i].average_return <= post_peak[i - 1].average_return
        if i > 0 else post_peak[i].average_return <= peak_return
        for i in range(len(post_peak))
    )

    if declining and len(post_peak) >= 1:
        last_return = post_peak[-1].average_return
        drop_pct = ((peak_return - last_return) / abs(peak_return) * 100) if peak_return != 0 else 0
        desc = (
            f"Alpha peaks at {valid[peak_idx].horizon} "
            f"({peak_return:.4f}) and declines {drop_pct:.0f}% "
            f"to {post_peak[-1].horizon} ({last_return:.4f})"
        )
        return True, desc

    return False, "No consistent decay pattern detected"
