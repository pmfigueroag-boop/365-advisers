"""
src/data/external/adapters/__init__.py
──────────────────────────────────────────────────────────────────────────────
Concrete provider adapters — one module per external data source.
"""

# ── Existing adapters ─────────────────────────────────────────────────────────
from src.data.external.adapters.polygon import PolygonAdapter
from src.data.external.adapters.etf_flows import ETFFlowAdapter
from src.data.external.adapters.options import OptionsAdapter
from src.data.external.adapters.institutional import InstitutionalAdapter
from src.data.external.adapters.news_sentiment import NewsSentimentAdapter
from src.data.external.adapters.macro import MacroAdapter
from src.data.external.adapters.finnhub import FinnhubAdapter
from src.data.external.adapters.fred import FREDAdapter
from src.data.external.adapters.sec_edgar import SECEdgarAdapter
from src.data.external.adapters.gdelt import GDELTAdapter
from src.data.external.adapters.quiver import QuiverAdapter

# ── New adapters (multi-source integration layer) ─────────────────────────────
from src.data.external.adapters.alpha_vantage import AlphaVantageAdapter
from src.data.external.adapters.twelve_data import TwelveDataAdapter
from src.data.external.adapters.fmp import FMPAdapter
from src.data.external.adapters.world_bank import WorldBankAdapter
from src.data.external.adapters.stocktwits import StocktwitsAdapter
from src.data.external.adapters.cboe import CboeAdapter
from src.data.external.adapters.santiment import SantimentAdapter
from src.data.external.adapters.imf import IMFAdapter
from src.data.external.adapters.stubs import (
    MorningstarAdapter,
    SimilarwebAdapter,
    ThinknumAdapter,
    OptionMetricsAdapter,
)

__all__ = [
    # Existing
    "PolygonAdapter", "ETFFlowAdapter", "OptionsAdapter",
    "InstitutionalAdapter", "NewsSentimentAdapter", "MacroAdapter",
    "FinnhubAdapter", "FREDAdapter", "SECEdgarAdapter",
    "GDELTAdapter", "QuiverAdapter",
    # New
    "AlphaVantageAdapter", "TwelveDataAdapter", "FMPAdapter",
    "WorldBankAdapter", "StocktwitsAdapter", "CboeAdapter",
    "SantimentAdapter", "IMFAdapter",
    "MorningstarAdapter", "SimilarwebAdapter",
    "ThinknumAdapter", "OptionMetricsAdapter",
]

