"""
src/engines/allocation_learning/engine.py
──────────────────────────────────────────────────────────────────────────────
Allocation Learning Engine — orchestrator.

Pipeline:
  1. Receive allocation outcomes
  2. Compute risk-adjusted rewards
  3. Update UCB1 bandit
  4. Produce recommended sizing
"""

from __future__ import annotations

import logging

from src.engines.allocation_learning.bandit import UCB1Bandit
from src.engines.allocation_learning.models import (
    AllocationConfig,
    AllocationOutcome,
    AllocationReport,
)
from src.engines.allocation_learning.reward import RewardComputer

logger = logging.getLogger("365advisers.allocation_learning.engine")


class AllocationLearningEngine:
    """
    Learns optimal position sizing via multi-armed bandit.

    Usage::

        engine = AllocationLearningEngine()
        report = engine.process_outcomes(outcomes)
        # report.recommended_bucket, report.recommended_allocation
    """

    def __init__(self, config: AllocationConfig | None = None) -> None:
        self.config = config or AllocationConfig()
        self._bandit = UCB1Bandit(self.config)
        self._reward_computer = RewardComputer()

    def process_outcomes(
        self,
        outcomes: list[AllocationOutcome],
        config: AllocationConfig | None = None,
    ) -> AllocationReport:
        """
        Process allocation outcomes and update bandit.

        Parameters
        ----------
        outcomes : list[AllocationOutcome]
        config : AllocationConfig | None

        Returns
        -------
        AllocationReport
        """
        cfg = config or self.config

        for outcome in outcomes:
            reward = self._reward_computer.compute(outcome)
            self._bandit.update(
                outcome.bucket_id, reward, outcome.forward_return,
            )

        rec_bucket, rec_alloc = self._bandit.recommend()

        report = AllocationReport(
            config=cfg,
            bucket_states=self._bandit.get_states(),
            recommended_bucket=rec_bucket,
            recommended_allocation=rec_alloc,
            total_observations=sum(
                s.total_pulls for s in self._bandit.get_states()
            ),
        )

        logger.info(
            "ALLOC-LEARNING: %d outcomes → recommend '%s' (%.1f%%)",
            len(outcomes), rec_bucket, rec_alloc * 100,
        )
        return report

    def recommend(self) -> tuple[str, float]:
        """Get current sizing recommendation."""
        return self._bandit.recommend()

    def get_states(self):
        """Get current bucket states."""
        return self._bandit.get_states()

    def reset(self) -> None:
        """Reset all learning state."""
        self._bandit.reset()
