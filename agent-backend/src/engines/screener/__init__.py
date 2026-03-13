"""
src/engines/screener/
──────────────────────────────────────────────────────────────────────────────
Composable multi-criteria Screener Engine.

Follows the Protocol + Registry pattern from universe_discovery.py.
"""

from src.engines.screener.contracts import (
    ScreenerFilter,
    ScreenerRequest,
    ScreenerMatch,
    ScreenerResult,
    FilterOperator,
)
from src.engines.screener.providers import (
    FilterProvider,
    FilterRegistry,
    FundamentalFilterProvider,
    TechnicalFilterProvider,
    MetadataFilterProvider,
)
from src.engines.screener.engine import ScreenerEngine

__all__ = [
    "ScreenerFilter",
    "ScreenerRequest",
    "ScreenerMatch",
    "ScreenerResult",
    "FilterOperator",
    "FilterProvider",
    "FilterRegistry",
    "FundamentalFilterProvider",
    "TechnicalFilterProvider",
    "MetadataFilterProvider",
    "ScreenerEngine",
]
