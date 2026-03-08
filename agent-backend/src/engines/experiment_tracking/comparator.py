"""
src/engines/experiment_tracking/comparator.py
─────────────────────────────────────────────────────────────────────────────
ExperimentComparator — side-by-side comparison of research experiments.

Compares metrics, configs, and regime behavior across experiments.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger("365advisers.experiment_tracking.comparator")


class ExperimentComparator:
    """Compare multiple research experiments."""

    @staticmethod
    def compare(experiments: list[dict]) -> dict:
        """Compare experiments side-by-side.

        Args:
            experiments: List of experiment summary dicts with metrics.

        Returns:
            Comparison with metric table, rankings, config diff, and verdict.
        """
        if len(experiments) < 2:
            return {"error": "Need at least 2 experiments to compare"}

        exp_ids = [e.get("experiment_id", f"exp_{i}") for i, e in enumerate(experiments)]
        exp_names = [e.get("name", f"Experiment {i}") for i, e in enumerate(experiments)]

        # ── Metric comparison ──
        metric_keys = set()
        for e in experiments:
            metric_keys.update(e.get("metrics", {}).keys())

        metrics_table: dict[str, list] = {}
        for key in sorted(metric_keys):
            metrics_table[key] = [
                e.get("metrics", {}).get(key) for e in experiments
            ]

        # ── Rankings ──
        rankings = {}
        rank_metrics = {
            "best_sharpe": ("sharpe_ratio", True),
            "best_cagr": ("cagr", True),
            "lowest_drawdown": ("max_drawdown", False),
            "best_sortino": ("sortino_ratio", True),
            "best_alpha": ("alpha", True),
            "lowest_cost": ("cost_drag_bps", False),
        }

        for rank_name, (metric_key, higher_better) in rank_metrics.items():
            values = [
                (exp_ids[i], e.get("metrics", {}).get(metric_key))
                for i, e in enumerate(experiments)
            ]
            valid = [(eid, v) for eid, v in values if v is not None]
            if valid:
                sorted_vals = sorted(valid, key=lambda x: x[1], reverse=higher_better)
                rankings[rank_name] = sorted_vals[0][0]

        # ── Config diff ──
        config_diffs = []
        if len(experiments) >= 2:
            config_diffs = _diff_configs(
                [e.get("config_snapshot", {}) for e in experiments],
                exp_ids,
            )

        # ── Regime comparison ──
        regime_comparison = _compare_regimes(experiments, exp_ids)

        # ── Verdict ──
        verdict = _generate_verdict(experiments, exp_ids, rankings)

        return {
            "experiment_count": len(experiments),
            "experiments": [
                {"experiment_id": exp_ids[i], "name": exp_names[i],
                 "type": e.get("experiment_type", "unknown"),
                 "status": e.get("status", "unknown")}
                for i, e in enumerate(experiments)
            ],
            "metrics_comparison": metrics_table,
            "rankings": rankings,
            "config_diff": config_diffs,
            "regime_comparison": regime_comparison,
            "verdict": verdict,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


def _diff_configs(configs: list[dict], exp_ids: list[str]) -> list[dict]:
    """Find parameter differences across experiment configs."""
    diffs = []

    all_keys = set()
    for cfg in configs:
        all_keys.update(_flatten_dict(cfg).keys())

    for key in sorted(all_keys):
        values = [_flatten_dict(cfg).get(key) for cfg in configs]
        unique = set(str(v) for v in values)
        if len(unique) > 1:
            diffs.append({
                "parameter": key,
                "values": {exp_ids[i]: values[i] for i in range(len(values))},
            })

    return diffs


def _flatten_dict(d: dict, prefix: str = "") -> dict:
    """Flatten nested dict with dot notation keys."""
    flat = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            flat.update(_flatten_dict(v, key))
        else:
            flat[key] = v
    return flat


def _compare_regimes(experiments: list[dict], exp_ids: list[str]) -> dict:
    """Compare experiment performance across regimes."""
    regime_data = {}
    for i, e in enumerate(experiments):
        ra = e.get("regime_analysis", {}).get("regimes", {})
        for regime, stats in ra.items():
            regime_data.setdefault(regime, {})[exp_ids[i]] = stats

    comparison = {}
    for regime, strategies in regime_data.items():
        sharpes = {eid: s.get("sharpe_ratio", 0) for eid, s in strategies.items()}
        if sharpes:
            best = max(sharpes, key=sharpes.get)
            worst = min(sharpes, key=sharpes.get)
            comparison[regime] = {"best": best, "worst": worst, "sharpes": sharpes}

    return comparison


def _generate_verdict(experiments: list[dict], exp_ids: list[str], rankings: dict) -> str:
    """Generate a human-readable verdict."""
    if not rankings:
        return "Insufficient metrics for comparison"

    # Count how many times each experiment "wins"
    wins = {}
    for rank_name, winner in rankings.items():
        wins[winner] = wins.get(winner, 0) + 1

    if wins:
        dominant = max(wins, key=wins.get)
        dominant_name = None
        for e in experiments:
            if e.get("experiment_id") == dominant:
                dominant_name = e.get("name", dominant)
                break

        win_count = wins[dominant]
        total = len(rankings)
        if win_count == total:
            return f"{dominant_name or dominant} dominates across all {total} metrics"
        elif win_count > total / 2:
            return f"{dominant_name or dominant} leads in {win_count}/{total} metrics"
        else:
            return "No clear winner — trade-offs across metrics"

    return "Unable to determine verdict"
