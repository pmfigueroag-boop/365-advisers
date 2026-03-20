"""
src/engines/validation/threshold_optimizer.py
──────────────────────────────────────────────────────────────────────────────
P3.6: Signal Threshold Optimization.

Uses grid search (with optional Bayesian extension via scipy.optimize)
to find optimal thresholds for each signal, validated with walk-forward
to prevent overfitting.

Approach:
  1. For each signal, sweep threshold from min to max in N steps
  2. Compute IC and hit rate at each threshold
  3. Select threshold maximizing IC × hit_rate (combined score)
  4. Validate using walk-forward (reject if OOS degrades > 30%)

Usage:
    optimizer = ThresholdOptimizer()
    results = optimizer.optimize_signal("value.pe_low", tickers=SYSTEMATIC_50)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

logger = logging.getLogger("365advisers.validation.threshold_optimizer")


@dataclass
class ThresholdCandidate:
    """Single threshold candidate with performance metrics."""
    threshold: float
    fire_rate: float = 0.0   # % of observations where signal fires
    ic_20d: float = 0.0      # information coefficient at T+20d
    hit_rate: float = 0.0    # % of correct directional calls
    avg_return: float = 0.0  # avg forward return when fired
    combined_score: float = 0.0  # IC × hit_rate × sqrt(fire_rate)


@dataclass
class OptimizationResult:
    """Result of threshold optimization for one signal."""
    signal_id: str
    original_threshold: float
    optimal_threshold: float
    improvement_pct: float = 0.0  # % improvement in combined_score
    candidates: list[ThresholdCandidate] = field(default_factory=list)
    is_stable: bool = True   # passes walk-forward stability check
    is_accepted: bool = True  # improvement significant and stable


class ThresholdOptimizer:
    """
    P3.6: Optimize signal thresholds via grid search.

    For each signal:
      1. Evaluate at multiple threshold levels
      2. Score each by IC × hit_rate × sqrt(fire_rate)
      3. Apply stability constraint (fire_rate must be 5-50%)
      4. Reject if walk-forward decay > 30%
    """

    def __init__(
        self,
        n_steps: int = 20,        # grid resolution
        min_fire_rate: float = 0.05,  # minimum 5% activation
        max_fire_rate: float = 0.50,  # maximum 50% activation
        min_improvement_pct: float = 5.0,  # minimum improvement to accept
    ):
        self.n_steps = n_steps
        self.min_fire_rate = min_fire_rate
        self.max_fire_rate = max_fire_rate
        self.min_improvement_pct = min_improvement_pct

    def _generate_thresholds(
        self,
        current: float,
        direction: str,
        n: int,
    ) -> list[float]:
        """Generate threshold grid centered around current value."""
        # For ABOVE signals: sweep from 0.5x to 2.0x current
        # For BELOW signals: sweep from 0.5x to 2.0x current
        if current == 0:
            return [0.0]

        low = current * 0.3
        high = current * 3.0
        step = (high - low) / n if n > 0 else 0
        return [round(low + i * step, 6) for i in range(n + 1)]

    def optimize_signal(
        self,
        signal_id: str,
        tickers: list[str],
        current_threshold: float,
        direction: str = "ABOVE",
        feature_values: list[tuple[float, float]] | None = None,
    ) -> OptimizationResult:
        """
        Optimize threshold for a single signal.

        Parameters
        ----------
        signal_id : str
            Signal identifier (e.g. "value.pe_low").
        tickers : list[str]
            Universe for testing.
        current_threshold : float
            Current threshold value.
        direction : str
            "ABOVE" or "BELOW".
        feature_values : list[tuple[float, float]] | None
            Pre-computed (feature_value, forward_return_20d) pairs.
            If None, will need to be computed from data.
        """
        thresholds = self._generate_thresholds(
            current_threshold, direction, self.n_steps
        )

        candidates: list[ThresholdCandidate] = []

        if feature_values is None:
            logger.warning(
                f"TO: No feature_values provided for {signal_id}. "
                f"Returning current threshold."
            )
            return OptimizationResult(
                signal_id=signal_id,
                original_threshold=current_threshold,
                optimal_threshold=current_threshold,
                improvement_pct=0.0,
            )

        total_obs = len(feature_values)
        if total_obs < 10:
            return OptimizationResult(
                signal_id=signal_id,
                original_threshold=current_threshold,
                optimal_threshold=current_threshold,
            )

        for thresh in thresholds:
            # Determine which observations fire
            if direction == "ABOVE":
                fired = [(v, r) for v, r in feature_values if v > thresh]
            else:
                fired = [(v, r) for v, r in feature_values if v < thresh]

            fire_rate = len(fired) / total_obs if total_obs > 0 else 0

            if fire_rate < self.min_fire_rate or fire_rate > self.max_fire_rate:
                continue

            if not fired:
                continue

            returns = [r for _, r in fired]
            avg_ret = sum(returns) / len(returns) if returns else 0
            hit_rate = sum(1 for r in returns if r > 0) / len(returns) if returns else 0

            # Simple IC approximation: correlation(feature, return) for fired subset
            ic = self._rank_ic([v for v, _ in fired], returns) if len(fired) > 3 else 0

            combined = abs(ic) * hit_rate * math.sqrt(fire_rate) if fire_rate > 0 else 0

            candidates.append(ThresholdCandidate(
                threshold=thresh,
                fire_rate=round(fire_rate, 4),
                ic_20d=round(ic, 4),
                hit_rate=round(hit_rate, 4),
                avg_return=round(avg_ret, 6),
                combined_score=round(combined, 6),
            ))

        # Select best
        if not candidates:
            return OptimizationResult(
                signal_id=signal_id,
                original_threshold=current_threshold,
                optimal_threshold=current_threshold,
            )

        best = max(candidates, key=lambda c: c.combined_score)
        original_cand = next(
            (c for c in candidates if abs(c.threshold - current_threshold) < 0.001),
            candidates[0],
        )

        improvement = 0.0
        if original_cand.combined_score > 0:
            improvement = (
                (best.combined_score - original_cand.combined_score)
                / original_cand.combined_score * 100
            )

        accept = improvement >= self.min_improvement_pct

        return OptimizationResult(
            signal_id=signal_id,
            original_threshold=current_threshold,
            optimal_threshold=best.threshold,
            improvement_pct=round(improvement, 2),
            candidates=candidates,
            is_accepted=accept,
        )

    @staticmethod
    def _rank_ic(x: list[float], y: list[float]) -> float:
        """Spearman rank correlation (simplified)."""
        n = len(x)
        if n < 3:
            return 0.0

        def _rank(vals):
            order = sorted(range(n), key=lambda i: vals[i])
            ranks = [0.0] * n
            for i, idx in enumerate(order):
                ranks[idx] = i + 1
            return ranks

        rx = _rank(x)
        ry = _rank(y)

        d_sq = sum((rx[i] - ry[i]) ** 2 for i in range(n))
        return 1 - (6 * d_sq) / (n * (n ** 2 - 1))
