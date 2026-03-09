"""
src/data/external/contracts/__init__.py
──────────────────────────────────────────────────────────────────────────────
Normalized data contracts for external provider outputs.

Each module defines Pydantic models that serve as the formal interface
between external data adapters and the internal Feature Layer / Engines.
"""

# ── Existing contracts ────────────────────────────────────────────────────────
from src.data.external.contracts.enhanced_market import EnhancedMarketData
from src.data.external.contracts.etf_flows import ETFFlowData
from src.data.external.contracts.options import OptionsIntelligence
from src.data.external.contracts.institutional import InstitutionalFlowData
from src.data.external.contracts.sentiment import NewsSentimentData
from src.data.external.contracts.macro import MacroContext
from src.data.external.contracts.filing_event import FilingEventData
from src.data.external.contracts.geopolitical import GeopoliticalEventData

# ── New contracts (multi-source integration layer) ────────────────────────────
from src.data.external.contracts.asset_profile import AssetProfile
from src.data.external.contracts.financial_statement import FinancialStatementData
from src.data.external.contracts.financial_ratios import FinancialRatios
from src.data.external.contracts.analyst_estimate import AnalystEstimateData
from src.data.external.contracts.economic_indicator import EconomicIndicatorData
from src.data.external.contracts.sentiment_signal import SentimentSignal
from src.data.external.contracts.alternative_signal import AlternativeSignal
from src.data.external.contracts.options_chain import OptionsChainData
from src.data.external.contracts.volatility_snapshot import VolatilitySnapshot

__all__ = [
    # Existing
    "EnhancedMarketData",
    "ETFFlowData",
    "OptionsIntelligence",
    "InstitutionalFlowData",
    "NewsSentimentData",
    "MacroContext",
    "FilingEventData",
    "GeopoliticalEventData",
    # New
    "AssetProfile",
    "FinancialStatementData",
    "FinancialRatios",
    "AnalystEstimateData",
    "EconomicIndicatorData",
    "SentimentSignal",
    "AlternativeSignal",
    "OptionsChainData",
    "VolatilitySnapshot",
]
