"""
src/engines/execution/
─────────────────────────────────────────────────────────────────────────────
Execution Simulation — Realistic execution modeling with slippage,
volume participation, spread, and latency for more accurate backtests.
"""

from .simulator import ExecutionSimulator
from .fill_model import FillModel

__all__ = ["ExecutionSimulator", "FillModel"]
