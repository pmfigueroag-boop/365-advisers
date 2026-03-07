"""
src/engines/signal_lab/stability.py
─────────────────────────────────────────────────────────────────────────────
StabilityAnalyzer — bootstrap and temporal stability analysis for signals.

Measures whether a signal's performance is robust across:
  - Random subsamples (bootstrap)
  - Time periods (temporal windows)
  - Market regimes
"""

from __future__ import annotations

import logging
import random
import math
from collections import defaultdict

logger = logging.getLogger(__name__)


class StabilityAnalyzer:
    """Analyze signal stability through resampling and temporal analysis."""

    @staticmethod
    def bootstrap_stability(
        fires: list[dict],
        n_samples: int = 100,
        sample_fraction: float = 0.8,
        seed: int | None = 42,
    ) -> dict:
        """Bootstrap resampling to test confidence stability.

        Draws n_samples random subsets and measures variance in key metrics.

        Returns:
            {
                "confidence_mean": float,
                "confidence_std": float,
                "confidence_ci_95": [lo, hi],
                "stability_score": float,   # 0–1, higher = more stable
                "n_samples": int,
                "sample_size": int,
            }
        """
        if len(fires) < 5:
            return {
                "confidence_mean": 0.0, "confidence_std": 0.0,
                "confidence_ci_95": [0.0, 0.0], "stability_score": 0.0,
                "n_samples": 0, "sample_size": 0,
            }

        rng = random.Random(seed)
        sample_size = max(3, int(len(fires) * sample_fraction))
        boot_means = []

        for _ in range(n_samples):
            sample = rng.sample(fires, sample_size)
            confidences = [f.get("confidence", 0.0) for f in sample]
            boot_means.append(sum(confidences) / len(confidences))

        boot_means.sort()
        mean = sum(boot_means) / len(boot_means)
        variance = sum((x - mean) ** 2 for x in boot_means) / len(boot_means)
        std = math.sqrt(variance)

        ci_lo = boot_means[int(0.025 * len(boot_means))]
        ci_hi = boot_means[int(0.975 * len(boot_means))]

        # Stability score: low std relative to mean = high stability
        cv = std / mean if mean > 0 else float("inf")
        stability = max(0.0, min(1.0, 1.0 - cv))

        return {
            "confidence_mean": round(mean, 4),
            "confidence_std": round(std, 4),
            "confidence_ci_95": [round(ci_lo, 4), round(ci_hi, 4)],
            "stability_score": round(stability, 4),
            "n_samples": n_samples,
            "sample_size": sample_size,
        }

    @staticmethod
    def temporal_stability(
        fires: list[dict],
        window_months: int = 3,
    ) -> dict:
        """Analyze signal performance across temporal windows.

        Splits fires by time windows and measures consistency.

        Returns:
            {
                "windows": [{period, fires, avg_confidence, strength_pct}],
                "temporal_consistency": float,   # 0–1
                "trend": str,                    # "improving" | "stable" | "degrading"
            }
        """
        if not fires:
            return {"windows": [], "temporal_consistency": 0.0, "trend": "unknown"}

        # Sort by date
        sorted_fires = sorted(fires, key=lambda f: f.get("fire_date", ""))

        # Group into windows
        windows: list[list[dict]] = []
        current_window: list[dict] = []
        window_start = None

        for fire in sorted_fires:
            fire_date = fire.get("fire_date", "")
            if not fire_date:
                continue

            fire_month = fire_date[:7]  # YYYY-MM

            if window_start is None:
                window_start = fire_month
                current_window = [fire]
            elif _months_diff(window_start, fire_month) < window_months:
                current_window.append(fire)
            else:
                windows.append(current_window)
                window_start = fire_month
                current_window = [fire]

        if current_window:
            windows.append(current_window)

        # Analyze each window
        window_results = []
        window_confidences = []

        for w in windows:
            confs = [f.get("confidence", 0.0) for f in w]
            avg_conf = sum(confs) / len(confs) if confs else 0.0
            strong_pct = sum(1 for f in w if f.get("strength") == "strong") / len(w) if w else 0.0

            dates = sorted(f.get("fire_date", "") for f in w)
            period = f"{dates[0]} → {dates[-1]}" if dates else "unknown"

            window_results.append({
                "period": period,
                "fires": len(w),
                "avg_confidence": round(avg_conf, 4),
                "strong_pct": round(strong_pct, 4),
            })
            window_confidences.append(avg_conf)

        # Consistency: low variance across windows = high consistency
        if len(window_confidences) >= 2:
            mean_c = sum(window_confidences) / len(window_confidences)
            var_c = sum((c - mean_c) ** 2 for c in window_confidences) / len(window_confidences)
            cv = math.sqrt(var_c) / mean_c if mean_c > 0 else float("inf")
            consistency = max(0.0, min(1.0, 1.0 - cv))
        else:
            consistency = 1.0  # Can't measure with single window

        # Trend detection
        trend = "stable"
        if len(window_confidences) >= 3:
            first_half = window_confidences[:len(window_confidences) // 2]
            second_half = window_confidences[len(window_confidences) // 2:]
            first_avg = sum(first_half) / len(first_half)
            second_avg = sum(second_half) / len(second_half)

            delta = (second_avg - first_avg) / first_avg if first_avg > 0 else 0
            if delta > 0.1:
                trend = "improving"
            elif delta < -0.1:
                trend = "degrading"

        return {
            "windows": window_results,
            "temporal_consistency": round(consistency, 4),
            "trend": trend,
        }

    @staticmethod
    def regime_stability(
        fires: list[dict],
        regime_field: str = "metadata",
        regime_key: str = "regime",
    ) -> dict:
        """Analyze signal performance across market regimes.

        Expects regime info in fire metadata or as separate field.
        """
        regime_fires: dict[str, list] = defaultdict(list)

        for fire in fires:
            meta = fire.get(regime_field, {})
            if isinstance(meta, dict):
                regime = meta.get(regime_key, "unknown")
            else:
                regime = "unknown"
            regime_fires[regime].append(fire)

        regime_stats = {}
        for regime, rfires in regime_fires.items():
            confs = [f.get("confidence", 0.0) for f in rfires]
            regime_stats[regime] = {
                "fires": len(rfires),
                "avg_confidence": round(sum(confs) / len(confs), 4) if confs else 0.0,
                "strong_pct": round(
                    sum(1 for f in rfires if f.get("strength") == "strong") / len(rfires), 4
                ) if rfires else 0.0,
            }

        # Best and worst regimes
        sorted_regimes = sorted(regime_stats.items(), key=lambda x: x[1]["avg_confidence"], reverse=True)
        best = sorted_regimes[0][0] if sorted_regimes else "unknown"
        worst = sorted_regimes[-1][0] if sorted_regimes else "unknown"

        return {
            "regimes": regime_stats,
            "best_regime": best,
            "worst_regime": worst,
            "regime_count": len(regime_stats),
        }


def _months_diff(ym1: str, ym2: str) -> int:
    """Calculate month difference between YYYY-MM strings."""
    try:
        y1, m1 = int(ym1[:4]), int(ym1[5:7])
        y2, m2 = int(ym2[:4]), int(ym2[5:7])
        return abs((y2 - y1) * 12 + (m2 - m1))
    except (ValueError, IndexError):
        return 0
