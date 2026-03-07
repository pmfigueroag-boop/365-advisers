"""
src/data/external/contracts/__init__.py
──────────────────────────────────────────────────────────────────────────────
Normalized data contracts for external provider outputs.

Each module defines Pydantic models that serve as the formal interface
between external data adapters and the internal Feature Layer / Engines.
"""

from src.data.external.contracts.enhanced_market import EnhancedMarketData
from src.data.external.contracts.etf_flows import ETFFlowData
from src.data.external.contracts.options import OptionsIntelligence
from src.data.external.contracts.institutional import InstitutionalFlowData
from src.data.external.contracts.sentiment import NewsSentimentData
from src.data.external.contracts.macro import MacroContext
from src.data.external.contracts.filing_event import FilingEventData
from src.data.external.contracts.geopolitical import GeopoliticalEventData

__all__ = [
    "EnhancedMarketData",
    "ETFFlowData",
    "OptionsIntelligence",
    "InstitutionalFlowData",
    "NewsSentimentData",
    "MacroContext",
    "FilingEventData",
    "GeopoliticalEventData",
]
