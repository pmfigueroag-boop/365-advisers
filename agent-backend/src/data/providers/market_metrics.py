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
from src.utils.exchange_resolver import resolve_exchange, resolve_screener
from src.config import get_settings

logger = logging.getLogger("365advisers.providers.market_metrics")
_settings = get_settings()


def _resolve_exchange(exchange_code: str) -> str:
    """Legacy shim — delegates to centralized resolver."""
    return resolve_exchange(exchange_code)


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
            screener=resolve_screener(resolved_exchange),
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
            adx=_get_tv_indicator(inds, ["ADX", "ADX+DI[14]"], 20.0),
            plus_di=_get_tv_indicator(inds, ["ADX+DI", "DI.plus"], 20.0),
            minus_di=_get_tv_indicator(inds, ["ADX-DI", "DI.minus"], 20.0),
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


# ─── Multi-Timeframe Fetch ───────────────────────────────────────────────────

def fetch_multi_timeframe(
    ticker: str,
    exchange: str = "NASDAQ",
) -> dict[str, dict]:
    """
    Fetch TradingView indicators for 4 timeframes: 1H, 4H, 1D, 1W.

    Returns a dict keyed by timeframe label ("1h", "4h", "1d", "1w"),
    each containing a tech_data dict compatible with IndicatorEngine.
    """
    symbol = ticker.upper()
    resolved_exchange = _resolve_exchange(exchange) if len(exchange) <= 3 else exchange

    intervals = {
        "1h":  Interval.INTERVAL_1_HOUR,
        "4h":  Interval.INTERVAL_4_HOURS,
        "1d":  Interval.INTERVAL_1_DAY,
        "1w":  Interval.INTERVAL_1_WEEK,
    }

    result: dict[str, dict] = {}

    for tf_key, tf_interval in intervals.items():
        try:
            handler = TA_Handler(
                symbol=symbol,
                screener=resolve_screener(resolved_exchange),
                exchange=resolved_exchange,
                interval=tf_interval,
            )
            analysis = handler.get_analysis()
            inds = analysis.indicators

            result[tf_key] = {
                "current_price": _get_tv_indicator(inds, ["close", "Close"], 0.0),
                "indicators": {
                    "sma50":      _get_tv_indicator(inds, ["SMA50", "EMA50"]),
                    "sma200":     _get_tv_indicator(inds, ["SMA200", "EMA200"]),
                    "ema20":      _get_tv_indicator(inds, ["EMA20", "SMA20"]),
                    "rsi":        _get_tv_indicator(inds, ["RSI", "RSI[1]"], 50.0),
                    "stoch_k":    _get_tv_indicator(inds, ["Stoch.K", "Stoch.K[1]"], 50.0),
                    "stoch_d":    _get_tv_indicator(inds, ["Stoch.D", "Stoch.D[1]"], 50.0),
                    "macd":       _get_tv_indicator(inds, "MACD.macd"),
                    "macd_signal":_get_tv_indicator(inds, "MACD.signal"),
                    "macd_hist":  _get_tv_indicator(inds, "MACD.hist"),
                    "bb_upper":   _get_tv_indicator(inds, "BB.upper"),
                    "bb_lower":   _get_tv_indicator(inds, "BB.lower"),
                    "bb_basis":   _get_tv_indicator(inds, ["BB.basis", "SMA20"]),
                    "atr":        _get_tv_indicator(inds, ["ATR", "Average True Range(14)"]),
                    "volume":     _get_tv_indicator(inds, "volume"),
                    "obv":        _get_tv_indicator(inds, "OBV"),
                },
                "ohlcv": [],  # OHLCV not available from TV per-timeframe
            }
            logger.info(f"MTF: Fetched {tf_key} for {symbol}")

        except Exception as exc:
            logger.warning(f"MTF: Error fetching {tf_key} for {symbol}: {exc}")
            # Skip this timeframe, scorer handles missing TFs gracefully

    return result
