"""
src/engines/validation_dashboard/__init__.py
──────────────────────────────────────────────────────────────────────────────
Validation Intelligence Dashboard — unified aggregation of all QVF modules.
"""

from src.engines.validation_dashboard.aggregator import DashboardAggregator
from src.engines.validation_dashboard.models import ValidationIntelligence

__all__ = ["DashboardAggregator", "ValidationIntelligence"]
