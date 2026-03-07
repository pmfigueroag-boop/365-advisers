"""
src/engines/portfolio_lab/__init__.py
─────────────────────────────────────────────────────────────────────────────
Strategy Portfolio Lab — multi-portfolio simulation, comparison, and attribution.
"""

from .simulator import PortfolioSimulator
from .attribution import AttributionEngine
from .comparison import PortfolioComparison

__all__ = [
    "PortfolioSimulator",
    "AttributionEngine",
    "PortfolioComparison",
]
