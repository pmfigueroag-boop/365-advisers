"""
src/engines/shadow/
─────────────────────────────────────────────────────────────────────────────
Shadow Portfolio Framework — Persistent simulation portfolios for measuring
system decisions without real capital risk.
"""

from .manager import ShadowPortfolioManager
from .rebalancer import ShadowRebalancer
from .performance import ShadowPerformanceCalc

__all__ = [
    "ShadowPortfolioManager",
    "ShadowRebalancer",
    "ShadowPerformanceCalc",
]
