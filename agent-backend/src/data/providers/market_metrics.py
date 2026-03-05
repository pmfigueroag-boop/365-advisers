"""
src/data/providers/market_metrics.py
──────────────────────────────────────────────────────────────────────────────
Provider: TradingView indicators and market metrics.

Produces a MarketMetrics contract with raw indicator values, TV summary,
oscillators, and moving averages data.
"""

from __future__ import annotations

import logging
from tradingview_ta import TA_Handler, Interval

from src.contracts.market_data import MarketMetrics, RawIndicators
from src.config import get_settings

logger = logging.getLogger("365advisers.providers.market_metrics")
_settings = get_settings()


def _resolve_exchange(exchange_code: str) -> str:
    """Map yfinance exchange codes to TradingView exchange names."""
    return {
        "NYQ": "NYSE",
        "NMS": "NASDAQ",
        "NGM": "NASDAQ",
        "ASQ": "AMEX",
    }.get(exchange_code, "NASDAQ")


def _get_tv_indicator(inds: dict, keys: str | list, default: float = 0.0) -> float:
    """Extract a float indicator from a TradingView indicators dict."""
    if isinstance(keys, str):
        keys = [keys]
    for k in keys:
        if k in inds and inds[k] is not None:
            try:
                return float(inds[k])
            except (TypeError, ValueError):
                continue
    return default


def fetch_market_metrics(ticker: str, exchange: str = "NASDAQ") -> MarketMetrics:
    """
    Fetch TradingView indicators for a ticker.

    Args:
        ticker: Stock symbol (e.g. "AAPL")
        exchange: Exchange name for TradingView (e.g. "NASDAQ", "NYSE")

    Returns a MarketMetrics contract. On error, returns metrics with
    neutral fallback values.
    """
    symbol = ticker.upper()
    resolved_exchange = _resolve_exchange(exchange) if len(exchange) <= 3 else exchange
    logger.info(f"Fetching market metrics for {symbol} on {resolved_exchange}")

    try:
        handler = TA_Handler(
            symbol=symbol,
            screener="america",
            exchange=resolved_exchange,
            interval=Interval.INTERVAL_1_DAY,
        )
        analysis = handler.get_analysis()
        inds = analysis.indicators

        raw_indicators = RawIndicators(
            close=_get_tv_indicator(inds, ["close", "Close"], 0.0),
            sma20=_get_tv_indicator(inds, ["SMA20", "EMA20"]),
            sma50=_get_tv_indicator(inds, ["SMA50", "EMA50"]),
            sma200=_get_tv_indicator(inds, ["SMA200", "EMA200"]),
            ema20=_get_tv_indicator(inds, ["EMA20", "SMA20"]),
            rsi=_get_tv_indicator(inds, ["RSI", "RSI[1]"], 50.0),
            stoch_k=_get_tv_indicator(inds, ["Stoch.K", "Stoch.K[1]"], 50.0),
            stoch_d=_get_tv_indicator(inds, ["Stoch.D", "Stoch.D[1]"], 50.0),
            macd=_get_tv_indicator(inds, "MACD.macd"),
            macd_signal=_get_tv_indicator(inds, "MACD.signal"),
            macd_hist=_get_tv_indicator(inds, "MACD.hist"),
            bb_upper=_get_tv_indicator(inds, "BB.upper"),
            bb_lower=_get_tv_indicator(inds, "BB.lower"),
            bb_basis=_get_tv_indicator(inds, ["BB.basis", "SMA20"]),
            atr=_get_tv_indicator(inds, ["ATR", "Average True Range(14)"]),
            volume=_get_tv_indicator(inds, "volume"),
            obv=_get_tv_indicator(inds, "OBV"),
            tv_recommendation=analysis.summary.get("RECOMMENDATION", "UNKNOWN"),
        )

        return MarketMetrics(
            ticker=symbol,
            exchange=resolved_exchange,
            indicators=raw_indicators,
            tv_summary=analysis.summary,
            tv_oscillators=analysis.oscillators,
            tv_moving_averages=analysis.moving_averages,
        )

    except Exception as exc:
        logger.warning(f"TradingView fetch error for {symbol}: {exc}")
        return MarketMetrics(
            ticker=symbol,
            exchange=resolved_exchange,
            indicators=RawIndicators(
                tv_recommendation="UNKNOWN",
            ),
        )
