"""
src/engines/validation/
──────────────────────────────────────────────────────────────────────────────
Alpha Validation System (AVS) — permanent infrastructure for validating
whether the Alpha Signal Engine generates real, robust alpha.

Modules:
  data_loader  — fetch + cache historical OHLCV + fundamentals
  metrics      — annualized performance metrics (Sharpe, Sortino, CAGR, etc.)
  ic_screen    — Phase 0: per-signal Information Coefficient computation
"""

from src.engines.validation.data_loader import ValidationDataLoader
from src.engines.validation.metrics import PerformanceMetrics
from src.engines.validation.ic_screen import ICScreen

__all__ = [
    "ValidationDataLoader",
    "PerformanceMetrics",
    "ICScreen",
]
