"""
src/engines/online_learning/dampener.py
──────────────────────────────────────────────────────────────────────────────
Change Dampener — clamps weight deltas and enforces bounds.
"""

from __future__ import annotations

import logging

from src.engines.online_learning.models import OnlineLearningConfig

logger = logging.getLogger("365advisers.online_learning.dampener")


class ChangeDampener:
    """
    Clamps weight deltas to prevent abrupt changes and enforces
    min/max weight bounds.
    """

    def dampen(
        self,
        raw_delta: float,
        current_weight: float,
        config: OnlineLearningConfig,
    ) -> tuple[float, bool]:
        """
        Apply dampening to a raw delta.

        Parameters
        ----------
        raw_delta : float
        current_weight : float
        config : OnlineLearningConfig

        Returns
        -------
        tuple[float, bool]
            (dampened_delta, was_dampened)
        """
        dampened = False
        delta = raw_delta

        # Clamp magnitude
        if abs(delta) > config.max_change_per_step:
            sign = 1.0 if delta > 0 else -1.0
            delta = sign * config.max_change_per_step
            dampened = True

        # Enforce bounds
        new_weight = current_weight + delta
        if new_weight < config.min_weight:
            delta = config.min_weight - current_weight
            dampened = True
        elif new_weight > config.max_weight:
            delta = config.max_weight - current_weight
            dampened = True

        return delta, dampened

    @staticmethod
    def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
        """
        Normalize weights to sum to 1.0.

        Parameters
        ----------
        weights : dict[str, float]
            {signal_id: weight}

        Returns
        -------
        dict[str, float]
            Normalized weights.
        """
        total = sum(weights.values())
        if total <= 0:
            # Equal weights fallback
            n = len(weights)
            return {k: 1.0 / n for k in weights} if n > 0 else weights

        return {k: v / total for k, v in weights.items()}
