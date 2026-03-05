"""
src/data/providers/__init__.py
──────────────────────────────────────────────────────────────────────────────
Data providers — each module encapsulates a single external data concern.
"""

from src.data.providers.price_history import fetch_price_history
from src.data.providers.financials import fetch_financials
from src.data.providers.market_metrics import fetch_market_metrics

__all__ = ["fetch_price_history", "fetch_financials", "fetch_market_metrics"]
