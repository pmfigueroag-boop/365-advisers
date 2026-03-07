"""
src/engines/allocation_learning/reward.py
──────────────────────────────────────────────────────────────────────────────
Reward computer for allocation outcomes.

Reward = sharpe_contribution × allocation_efficiency
"""

from __future__ import annotations

import logging
import math

from src.engines.allocation_learning.models import AllocationOutcome

logger = logging.getLogger("365advisers.allocation_learning.reward")


class RewardComputer:
    """
    Computes risk-adjusted reward from an allocation outcome.

    reward = sharpe_contribution × allocation_efficiency

    sharpe_contribution = return / max(vol, epsilon)
    allocation_efficiency = |return| / max(max_drawdown, epsilon)
    """

    def __init__(self, epsilon: float = 0.001) -> None:
        self.epsilon = epsilon

    def compute(self, outcome: AllocationOutcome) -> float:
        """
        Compute reward for a single allocation outcome.

        Parameters
        ----------
        outcome : AllocationOutcome

        Returns
        -------
        float
            Risk-adjusted reward, unbounded.
        """
        vol = max(abs(outcome.volatility), self.epsilon)
        mdd = max(abs(outcome.max_drawdown), self.epsilon)

        sharpe_contribution = outcome.forward_return / vol

        # Annualize
        if outcome.holding_period_days > 0:
            annualisation = math.sqrt(252 / outcome.holding_period_days)
        else:
            annualisation = 1.0

        sharpe_contribution *= annualisation

        allocation_efficiency = abs(outcome.forward_return) / mdd

        # Combined reward — sign from return direction
        sign = 1.0 if outcome.forward_return >= 0 else -1.0
        reward = sign * abs(sharpe_contribution) * min(allocation_efficiency, 5.0)

        return round(reward, 6)
