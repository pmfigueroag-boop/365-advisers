"""
src/engines/allocation_learning/__init__.py
──────────────────────────────────────────────────────────────────────────────
Reinforcement-Style Allocation Learning module.
"""

from src.engines.allocation_learning.bandit import UCB1Bandit
from src.engines.allocation_learning.engine import AllocationLearningEngine
from src.engines.allocation_learning.models import (
    AllocationConfig,
    AllocationOutcome,
    AllocationReport,
    BucketState,
)
from src.engines.allocation_learning.reward import RewardComputer

__all__ = [
    "AllocationConfig",
    "AllocationLearningEngine",
    "AllocationOutcome",
    "AllocationReport",
    "BucketState",
    "RewardComputer",
    "UCB1Bandit",
]
