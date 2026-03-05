"""
src/contracts/market_data.py
──────────────────────────────────────────────────────────────────────────────
Layer 1 output contracts — shapes produced by MarketDataLayer providers.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


# ─── OHLCV / Price History ────────────────────────────────────────────────────

class OHLCVBar(BaseModel):
    """Single daily OHLCV bar."""
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class PriceHistory(BaseModel):
    """Complete price history for a ticker."""
    ticker: str
    current_price: float = 0.0
    ohlcv: list[OHLCVBar] = Field(default_factory=list)


# ─── Financial Statements ────────────────────────────────────────────────────

class ProfitabilityRatios(BaseModel):
    gross_margin: float | str | None = None
    ebit_margin: float | str | None = None
    net_margin: float | str | None = None
    roe: float | str | None = None
    roic: float | str | None = None


class ValuationRatios(BaseModel):
    pe_ratio: float | str | None = None
    pb_ratio: float | str | None = None
    ev_ebitda: float | str | None = None
    fcf_yield: float | str | None = None
    market_cap: float | None = None


class LeverageRatios(BaseModel):
    debt_to_equity: float | str | None = None
    interest_coverage: float | str | None = None
    current_ratio: float | str | None = None
    quick_ratio: float | str | None = None


class QualityRatios(BaseModel):
    revenue_growth_yoy: float | str | None = None
    earnings_growth_yoy: float | str | None = None
    dividend_yield: float = 0.0
    payout_ratio: float = 0.0
    beta: float | str | None = None


class FinancialRatios(BaseModel):
    """Computed financial ratios bucket."""
    profitability: ProfitabilityRatios = Field(default_factory=ProfitabilityRatios)
    valuation: ValuationRatios = Field(default_factory=ValuationRatios)
    leverage: LeverageRatios = Field(default_factory=LeverageRatios)
    quality: QualityRatios = Field(default_factory=QualityRatios)


class CashFlowEntry(BaseModel):
    year: str
    fcf: float = 0.0
    revenue: float = 0.0


class FinancialStatements(BaseModel):
    """Fundamental financial data for a ticker."""
    ticker: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    description: str = ""
    ratios: FinancialRatios = Field(default_factory=FinancialRatios)
    cashflow_series: list[CashFlowEntry] = Field(default_factory=list)
    info: dict = Field(default_factory=dict)  # raw yfinance info for backward compat


# ─── Market Metrics (TradingView + derived) ───────────────────────────────────

class RawIndicators(BaseModel):
    """Raw indicator values from TradingView and yfinance."""
    close: float = 0.0
    sma20: float = 0.0
    sma50: float = 0.0
    sma200: float = 0.0
    ema20: float = 0.0
    rsi: float = 50.0
    stoch_k: float = 50.0
    stoch_d: float = 50.0
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_hist: float = 0.0
    bb_upper: float = 0.0
    bb_lower: float = 0.0
    bb_basis: float = 0.0
    atr: float = 0.0
    volume: float = 0.0
    obv: float = 0.0
    tv_recommendation: str = "UNKNOWN"


class TVSummary(BaseModel):
    """TradingView summary snapshot."""
    RECOMMENDATION: str = "UNKNOWN"
    BUY: int = 0
    SELL: int = 0
    NEUTRAL: int = 0


class MarketMetrics(BaseModel):
    """TradingView-sourced market metrics."""
    ticker: str
    exchange: str = ""
    indicators: RawIndicators = Field(default_factory=RawIndicators)
    tv_summary: dict = Field(default_factory=dict)
    tv_oscillators: dict = Field(default_factory=dict)
    tv_moving_averages: dict = Field(default_factory=dict)


# ─── Unified Market Data Bundle ───────────────────────────────────────────────

class MarketDataBundle(BaseModel):
    """
    Complete market data output from Layer 1.
    Contains everything needed by the Feature Layer.
    """
    ticker: str
    price_history: PriceHistory = Field(default_factory=lambda: PriceHistory(ticker=""))
    financials: FinancialStatements = Field(default_factory=lambda: FinancialStatements(ticker=""))
    market_metrics: MarketMetrics = Field(default_factory=lambda: MarketMetrics(ticker=""))
