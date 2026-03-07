"""
src/engines/online_learning/updater.py
──────────────────────────────────────────────────────────────────────────────
EMA Weight Updater — computes raw weight deltas from new observations.
"""

from __future__ import annotations

import logging
import math

from src.engines.online_learning.models import (
    OnlineLearningConfig,
    SignalObservation,
)

logger = logging.getLogger("365advisers.online_learning.updater")


class EMAUpdater:
    """
    Exponential Moving Average weight updater.

    Given a new observation (signal return), computes the raw weight
    delta using EMA blending:

        observed_score = excess_return clamped to [-1, 1]
        raw_new_weight = α × observed_score + (1 − α) × current_weight
        raw_delta = raw_new_weight − current_weight
    """

    def compute_raw_delta(
        self,
        observation: SignalObservation,
        current_weight: float,
        learning_rate: float,
        config: OnlineLearningConfig,
    ) -> float:
        """
        Compute un-dampened weight delta from a single observation.

        Parameters
        ----------
        observation : SignalObservation
        current_weight : float
        learning_rate : float
            Current (possibly decayed) α.
        config : OnlineLearningConfig

        Returns
        -------
        float
            Raw delta (before dampening).
        """
        # Compute excess return over benchmark
        excess = observation.forward_return - observation.benchmark_return

        # Convert to a score in [-1, 1] via tanh-like scaling
        observed_score = self._score(excess)

        # EMA blend
        raw_new = learning_rate * observed_score + (1 - learning_rate) * current_weight
        raw_delta = raw_new - current_weight

        return raw_delta

    @staticmethod
    def _score(excess_return: float) -> float:
        """
        Map excess return to a score in [0, 1].

        Uses a sigmoid-like transform:
          - Large positive excess → close to 1
          - Zero excess → 0.5
          - Large negative excess → close to 0
        """
        # Scale: 10x amplification for typical return magnitudes
        x = excess_return * 10.0
        return 1.0 / (1.0 + math.exp(-x))

    @staticmethod
    def decay_lr(
        current_lr: float,
        decay_factor: float,
        min_lr: float = 0.001,
    ) -> float:
        """Apply one step of learning rate decay."""
        return max(min_lr, current_lr * decay_factor)
