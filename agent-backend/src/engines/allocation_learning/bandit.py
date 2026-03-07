"""
src/engines/allocation_learning/bandit.py
──────────────────────────────────────────────────────────────────────────────
UCB1 Multi-Armed Bandit for position sizing.
"""

from __future__ import annotations

import logging
import math

from src.engines.allocation_learning.models import AllocationConfig, BucketState

logger = logging.getLogger("365advisers.allocation_learning.bandit")


class UCB1Bandit:
    """
    Upper Confidence Bound (UCB1) multi-armed bandit.

    Each arm is a position sizing bucket.
    UCB1(arm) = avg_reward + c × √(ln(N) / n_arm)
    """

    def __init__(self, config: AllocationConfig | None = None) -> None:
        self.config = config or AllocationConfig()
        self._states: dict[str, BucketState] = {}
        self._total_pulls: int = 0

        # Initialise arms
        for name, pct in zip(self.config.bucket_names, self.config.buckets):
            self._states[name] = BucketState(
                bucket_id=name,
                allocation_pct=pct,
            )

    # ── Core API ──────────────────────────────────────────────────────────

    def update(self, bucket_id: str, reward: float, forward_return: float = 0.0) -> None:
        """
        Record a reward for a bucket arm.

        Parameters
        ----------
        bucket_id : str
        reward : float
        forward_return : float
        """
        if bucket_id not in self._states:
            logger.warning("BANDIT: Unknown bucket %s", bucket_id)
            return

        state = self._states[bucket_id]
        self._total_pulls += 1
        state.total_pulls += 1

        # Incremental mean update with decay
        decay = self.config.reward_decay
        if state.total_pulls == 1:
            state.avg_reward = reward
        else:
            state.avg_reward = decay * state.avg_reward + (1 - decay) * reward

        # Track returns
        state.total_return += forward_return
        state.best_return = max(state.best_return, forward_return)
        state.worst_return = min(state.worst_return, forward_return)

        # Recompute UCB scores for all arms
        self._recompute_ucb()

    def recommend(self) -> tuple[str, float]:
        """
        Select the best arm using UCB1.

        Returns
        -------
        tuple[str, float]
            (bucket_id, allocation_pct) of the recommended arm.
        """
        # Prioritise unexplored arms
        for name, state in self._states.items():
            if state.total_pulls < self.config.min_observations:
                return name, state.allocation_pct

        # Select by highest UCB score
        best = max(self._states.values(), key=lambda s: s.ucb_score)
        return best.bucket_id, best.allocation_pct

    def get_states(self) -> list[BucketState]:
        """Return current state of all arms."""
        return list(self._states.values())

    def reset(self) -> None:
        """Reset all arm statistics."""
        self._total_pulls = 0
        for state in self._states.values():
            state.total_pulls = 0
            state.avg_reward = 0.0
            state.ucb_score = float("inf")
            state.total_return = 0.0
            state.best_return = 0.0
            state.worst_return = 0.0

    # ── Internal ──────────────────────────────────────────────────────────

    def _recompute_ucb(self) -> None:
        """Recompute UCB1 scores for all arms."""
        N = self._total_pulls
        c = self.config.ucb_c

        for state in self._states.values():
            if state.total_pulls == 0:
                state.ucb_score = float("inf")
            else:
                exploration = c * math.sqrt(math.log(N) / state.total_pulls)
                state.ucb_score = round(state.avg_reward + exploration, 6)
