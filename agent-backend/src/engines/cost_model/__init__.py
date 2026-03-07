"""
src/engines/cost_model/__init__.py
──────────────────────────────────────────────────────────────────────────────
Transaction Cost & Slippage Model — adjusts signal returns for real-world
market frictions (spread, market impact, slippage, commissions).
"""

from src.engines.cost_model.engine import CostModelEngine
from src.engines.cost_model.models import (
    CostModelConfig,
    CostModelReport,
    SignalCostProfile,
    TradeCostBreakdown,
)

__all__ = [
    "CostModelEngine",
    "CostModelConfig",
    "CostModelReport",
    "SignalCostProfile",
    "TradeCostBreakdown",
]
