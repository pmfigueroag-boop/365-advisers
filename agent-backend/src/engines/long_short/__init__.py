"""
src/engines/long_short/
──────────────────────────────────────────────────────────────────────────────
Long/Short Equity Engine — enables market-neutral and hedged strategies.

Provides:
  • ShortPosition / LongShortPortfolio data contracts
  • Gross / Net / Beta exposure calculation
  • Borrow-cost estimation (tiered model)
  • L/S portfolio construction with exposure constraints
"""

from src.engines.long_short.models import (
    PositionSide,
    LongShortPosition,
    LongShortPortfolio,
    ExposureMetrics,
    BorrowCostEstimate,
    LongShortResult,
)
from src.engines.long_short.exposure import ExposureCalculator
from src.engines.long_short.borrow_cost import BorrowCostEstimator
from src.engines.long_short.engine import LongShortEngine

__all__ = [
    "PositionSide",
    "LongShortPosition",
    "LongShortPortfolio",
    "ExposureMetrics",
    "BorrowCostEstimate",
    "LongShortResult",
    "ExposureCalculator",
    "BorrowCostEstimator",
    "LongShortEngine",
]
