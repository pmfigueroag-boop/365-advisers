"""
src/data/external/contracts/enhanced_market.py
──────────────────────────────────────────────────────────────────────────────
Normalized contracts for enhanced market data (Polygon.io tier).

These extend the base MarketDataBundle with intraday, liquidity, and
trade-level detail — without modifying the existing contracts.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class IntradayBar(BaseModel):
    """Single intraday OHLCV bar (1m / 5m / 15m / 1h)."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float | None = None
    trade_count: int | None = None


class LiquiditySnapshot(BaseModel):
    """Point-in-time liquidity profile for a ticker."""
    ticker: str
    bid_ask_spread_bps: float | None = None
    avg_daily_volume_30d: float | None = None
    avg_dollar_volume_30d: float | None = None
    market_impact_estimate_bps: float | None = None
    turnover_ratio: float | None = None

    @classmethod
    def empty(cls, ticker: str = "") -> LiquiditySnapshot:
        return cls(ticker=ticker)


class EnhancedMarketData(BaseModel):
    """
    Enhanced market data from an institutional-grade provider.

    Supplements — does NOT replace — the existing MarketDataBundle.
    """
    ticker: str
    intraday_bars: list[IntradayBar] = Field(default_factory=list)
    liquidity: LiquiditySnapshot | None = None
    last_trade_price: float | None = None
    source: str = "unknown"
    sources_used: list[str] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @classmethod
    def empty(cls, ticker: str = "") -> EnhancedMarketData:
        return cls(ticker=ticker, source="null")
