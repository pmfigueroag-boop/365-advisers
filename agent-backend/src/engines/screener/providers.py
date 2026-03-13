"""
src/engines/screener/providers.py
──────────────────────────────────────────────────────────────────────────────
Protocol-based filter providers for the composable Screener Engine.

Follows the same architecture pattern as universe_discovery.py.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from src.engines.screener.contracts import ScreenerFilter

logger = logging.getLogger("365advisers.screener.providers")


# ── Provider Protocol ────────────────────────────────────────────────────────

@runtime_checkable
class FilterProvider(Protocol):
    """Interface for pluggable filter data providers."""
    name: str
    description: str

    def supported_fields(self) -> list[dict]:
        """Return list of {'field': str, 'label': str, 'type': str, 'category': str}."""
        ...

    def extract(self, ticker_data: dict, field: str) -> float | str | None:
        """Extract a field value from ticker data dict."""
        ...


# ── Filter Registry ──────────────────────────────────────────────────────────

class FilterRegistry:
    """Central catalog of filter providers (composable)."""

    def __init__(self) -> None:
        self._providers: dict[str, FilterProvider] = {}
        self._field_to_provider: dict[str, str] = {}

    def register(self, provider: FilterProvider) -> None:
        if provider.name in self._providers:
            raise ValueError(f"Filter provider '{provider.name}' already registered")
        self._providers[provider.name] = provider
        for field_info in provider.supported_fields():
            self._field_to_provider[field_info["field"]] = provider.name
        logger.debug(f"filter_provider_registered: {provider.name}")

    def get_provider_for_field(self, field: str) -> FilterProvider | None:
        provider_name = self._field_to_provider.get(field)
        if provider_name:
            return self._providers.get(provider_name)
        return None

    def extract_field(self, ticker_data: dict, field: str) -> float | str | None:
        provider = self.get_provider_for_field(field)
        if provider is None:
            return None
        return provider.extract(ticker_data, field)

    def all_fields(self) -> list[dict]:
        fields = []
        for p in self._providers.values():
            fields.extend(p.supported_fields())
        return fields

    def list_providers(self) -> list[dict]:
        return [
            {"name": p.name, "description": p.description}
            for p in self._providers.values()
        ]

    def __len__(self) -> int:
        return len(self._providers)

    def __contains__(self, name: str) -> bool:
        return name in self._providers


# ── Fundamental Filter Provider ──────────────────────────────────────────────

class FundamentalFilterProvider:
    """Extracts fundamental metrics from ticker data for screening."""
    name = "fundamental"
    description = "Fundamental analysis metrics: valuation, quality, leverage, growth"

    _FIELDS = [
        {"field": "pe_ratio",           "label": "P/E Ratio",            "type": "number", "category": "valuation"},
        {"field": "pb_ratio",           "label": "P/B Ratio",            "type": "number", "category": "valuation"},
        {"field": "ev_ebitda",          "label": "EV/EBITDA",            "type": "number", "category": "valuation"},
        {"field": "fcf_yield",          "label": "FCF Yield %",          "type": "number", "category": "valuation"},
        {"field": "gross_margin",       "label": "Gross Margin %",       "type": "number", "category": "quality"},
        {"field": "ebit_margin",        "label": "EBIT Margin %",        "type": "number", "category": "quality"},
        {"field": "net_margin",         "label": "Net Margin %",         "type": "number", "category": "quality"},
        {"field": "roe",                "label": "ROE %",                "type": "number", "category": "quality"},
        {"field": "roic",              "label": "ROIC %",               "type": "number", "category": "quality"},
        {"field": "debt_to_equity",     "label": "Debt/Equity",          "type": "number", "category": "leverage"},
        {"field": "interest_coverage",  "label": "Interest Coverage",    "type": "number", "category": "leverage"},
        {"field": "current_ratio",      "label": "Current Ratio",        "type": "number", "category": "leverage"},
        {"field": "quick_ratio",        "label": "Quick Ratio",          "type": "number", "category": "leverage"},
        {"field": "revenue_growth",     "label": "Revenue Growth YoY %", "type": "number", "category": "growth"},
        {"field": "earnings_growth",    "label": "Earnings Growth YoY %","type": "number", "category": "growth"},
        {"field": "dividend_yield",     "label": "Dividend Yield %",     "type": "number", "category": "dividends"},
        {"field": "payout_ratio",       "label": "Payout Ratio %",       "type": "number", "category": "dividends"},
        {"field": "beta",               "label": "Beta",                 "type": "number", "category": "risk"},
    ]

    # Map field name → (ratios sub-dict key, ratio key)
    _EXTRACTION_MAP: dict[str, tuple[str, str]] = {
        "pe_ratio":          ("valuation",      "pe_ratio"),
        "pb_ratio":          ("valuation",      "pb_ratio"),
        "ev_ebitda":         ("valuation",      "ev_ebitda"),
        "fcf_yield":         ("valuation",      "fcf_yield"),
        "gross_margin":      ("profitability",  "gross_margin"),
        "ebit_margin":       ("profitability",  "ebit_margin"),
        "net_margin":        ("profitability",  "net_margin"),
        "roe":               ("profitability",  "roe"),
        "roic":              ("profitability",  "roic"),
        "debt_to_equity":    ("leverage",       "debt_to_equity"),
        "interest_coverage": ("leverage",       "interest_coverage"),
        "current_ratio":     ("leverage",       "current_ratio"),
        "quick_ratio":       ("leverage",       "quick_ratio"),
        "revenue_growth":    ("quality",        "revenue_growth_yoy"),
        "earnings_growth":   ("quality",        "earnings_growth_yoy"),
        "dividend_yield":    ("quality",        "dividend_yield"),
        "payout_ratio":      ("quality",        "payout_ratio"),
        "beta":              ("quality",        "beta"),
    }

    def supported_fields(self) -> list[dict]:
        return self._FIELDS.copy()

    def extract(self, ticker_data: dict, field: str) -> float | str | None:
        mapping = self._EXTRACTION_MAP.get(field)
        if mapping is None:
            return None
        category_key, ratio_key = mapping
        ratios = ticker_data.get("ratios", {})
        sub = ratios.get(category_key, {})
        val = sub.get(ratio_key)
        if val == "DATA_INCOMPLETE" or val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None


# ── Technical Filter Provider ────────────────────────────────────────────────

class TechnicalFilterProvider:
    """Extracts technical indicators from ticker data for screening."""
    name = "technical"
    description = "Technical analysis metrics: momentum, trend, volatility"

    _FIELDS = [
        {"field": "rsi",                "label": "RSI (14)",             "type": "number", "category": "momentum"},
        {"field": "macd_hist",          "label": "MACD Histogram",      "type": "number", "category": "momentum"},
        {"field": "stoch_k",            "label": "Stochastic %K",       "type": "number", "category": "momentum"},
        {"field": "atr_pct",            "label": "ATR %",               "type": "number", "category": "volatility"},
        {"field": "bb_width",           "label": "Bollinger Width",     "type": "number", "category": "volatility"},
        {"field": "sma50_distance",     "label": "Price vs SMA50 %",    "type": "number", "category": "trend"},
        {"field": "sma200_distance",    "label": "Price vs SMA200 %",   "type": "number", "category": "trend"},
        {"field": "obv_trend",          "label": "OBV Trend",           "type": "string", "category": "volume"},
        {"field": "tv_recommendation",  "label": "TradingView Rating",  "type": "string", "category": "consensus"},
    ]

    def supported_fields(self) -> list[dict]:
        return self._FIELDS.copy()

    def extract(self, ticker_data: dict, field: str) -> float | str | None:
        inds = ticker_data.get("indicators", {})
        info = ticker_data.get("info", {})

        if field == "rsi":
            return _safe(inds.get("rsi"))
        if field == "macd_hist":
            return _safe(inds.get("macd_hist"))
        if field == "stoch_k":
            return _safe(inds.get("stoch_k"))
        if field == "atr_pct":
            atr = _safe(inds.get("atr"), 0.0)
            close = _safe(inds.get("close"), 0.0)
            return (atr / close * 100) if close > 0 else None
        if field == "bb_width":
            upper = _safe(inds.get("bb_upper"), 0.0)
            lower = _safe(inds.get("bb_lower"), 0.0)
            basis = _safe(inds.get("bb_basis"), 0.0)
            return ((upper - lower) / basis * 100) if basis > 0 else None
        if field == "sma50_distance":
            close = _safe(inds.get("close"), 0.0)
            sma = _safe(inds.get("sma50"), 0.0)
            return ((close - sma) / sma * 100) if sma > 0 else None
        if field == "sma200_distance":
            close = _safe(inds.get("close"), 0.0)
            sma = _safe(inds.get("sma200"), 0.0)
            return ((close - sma) / sma * 100) if sma > 0 else None
        if field == "obv_trend":
            return inds.get("obv_trend")
        if field == "tv_recommendation":
            return inds.get("tv_recommendation") or ticker_data.get("tv_summary", {}).get("RECOMMENDATION")

        return None


# ── Metadata Filter Provider ─────────────────────────────────────────────────

class MetadataFilterProvider:
    """Extracts company metadata for screening."""
    name = "metadata"
    description = "Company metadata: sector, industry, market cap, exchange"

    _FIELDS = [
        {"field": "market_cap",   "label": "Market Cap ($)",  "type": "number", "category": "size"},
        {"field": "sector",       "label": "Sector",          "type": "string", "category": "classification"},
        {"field": "industry",     "label": "Industry",        "type": "string", "category": "classification"},
        {"field": "exchange",     "label": "Exchange",        "type": "string", "category": "listing"},
    ]

    def supported_fields(self) -> list[dict]:
        return self._FIELDS.copy()

    def extract(self, ticker_data: dict, field: str) -> float | str | None:
        info = ticker_data.get("info", {})
        ratios = ticker_data.get("ratios", {})

        if field == "market_cap":
            mc = info.get("marketCap") or ratios.get("valuation", {}).get("market_cap")
            return _safe(mc)
        if field == "sector":
            return ticker_data.get("sector") or info.get("sector")
        if field == "industry":
            return ticker_data.get("industry") or info.get("industry")
        if field == "exchange":
            return info.get("exchange") or ticker_data.get("exchange")

        return None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe(val, default=None) -> float | None:
    if val is None or val == "DATA_INCOMPLETE":
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ── Presets ──────────────────────────────────────────────────────────────────

SCREENER_PRESETS: dict[str, dict] = {
    "value": {
        "label": "Value Investing",
        "description": "Low valuation, strong balance sheet",
        "filters": [
            {"field": "pe_ratio",       "operator": "lte", "value": 20.0},
            {"field": "pb_ratio",       "operator": "lte", "value": 3.0},
            {"field": "debt_to_equity", "operator": "lte", "value": 1.0},
            {"field": "fcf_yield",      "operator": "gte", "value": 0.04},
        ],
    },
    "growth": {
        "label": "Growth",
        "description": "High revenue and earnings growth",
        "filters": [
            {"field": "revenue_growth",  "operator": "gte", "value": 0.15},
            {"field": "earnings_growth", "operator": "gte", "value": 0.15},
            {"field": "gross_margin",    "operator": "gte", "value": 0.40},
        ],
    },
    "momentum": {
        "label": "Technical Momentum",
        "description": "Positive momentum indicators",
        "filters": [
            {"field": "rsi",              "operator": "between", "value": 50.0, "value_max": 70.0},
            {"field": "sma50_distance",   "operator": "gte",     "value": 0.0},
            {"field": "sma200_distance",  "operator": "gte",     "value": 0.0},
            {"field": "macd_hist",        "operator": "gt",      "value": 0.0},
        ],
    },
    "quality": {
        "label": "Quality",
        "description": "High profitability and solid margins",
        "filters": [
            {"field": "roic",           "operator": "gte", "value": 0.15},
            {"field": "gross_margin",   "operator": "gte", "value": 0.50},
            {"field": "debt_to_equity", "operator": "lte", "value": 0.8},
            {"field": "current_ratio",  "operator": "gte", "value": 1.5},
        ],
    },
    "dividend": {
        "label": "Dividend Income",
        "description": "Sustainable high dividends",
        "filters": [
            {"field": "dividend_yield", "operator": "gte", "value": 0.025},
            {"field": "payout_ratio",   "operator": "lte", "value": 0.70},
            {"field": "debt_to_equity", "operator": "lte", "value": 1.5},
        ],
    },
}
