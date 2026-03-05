"""
src/engines/backtesting/__init__.py
──────────────────────────────────────────────────────────────────────────────
Alpha Signal Backtesting Engine — empirical validation of signal performance.

Re-exports the public API.
"""

from src.engines.backtesting.engine import BacktestEngine

__all__ = ["BacktestEngine"]
