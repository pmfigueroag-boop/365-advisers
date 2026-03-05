"""
src/data/providers/price_history.py
──────────────────────────────────────────────────────────────────────────────
Provider: OHLCV price history from yfinance.

Produces a PriceHistory contract with daily bars for the last year.
Includes timeout protection via threading.
"""

from __future__ import annotations

import logging
import threading
import pandas as pd
import yfinance as yf

from src.contracts.market_data import PriceHistory, OHLCVBar
from src.config import get_settings

logger = logging.getLogger("365advisers.providers.price_history")
_settings = get_settings()


def fetch_price_history(ticker: str) -> PriceHistory:
    """
    Fetch 1-year daily OHLCV data for a ticker.

    Returns a PriceHistory contract. On timeout or error, returns
    an empty PriceHistory with current_price = 0.0.
    """
    symbol = ticker.upper()
    logger.info(f"Fetching price history for {symbol}")

    result_container: dict = {}

    def _thread_target():
        try:
            stock = yf.Ticker(symbol)
            info = stock.info or {}
            history = stock.history(period="1y")
            result_container["info"] = info
            result_container["history"] = history
        except Exception as e:
            result_container["error"] = e

    t = threading.Thread(target=_thread_target, daemon=True)
    t.start()
    t.join(timeout=_settings.YFINANCE_TIMEOUT)

    if t.is_alive():
        logger.error(f"Price history for {symbol} timed out after {_settings.YFINANCE_TIMEOUT}s")
        return PriceHistory(ticker=symbol, current_price=0.0)

    if "error" in result_container:
        logger.warning(f"Price history error for {symbol}: {result_container['error']}")
        return PriceHistory(ticker=symbol, current_price=0.0)

    info = result_container.get("info", {})
    history: pd.DataFrame = result_container.get("history", pd.DataFrame())

    bars: list[OHLCVBar] = []
    if not history.empty:
        for idx, row in history.iterrows():
            bars.append(OHLCVBar(
                time=idx.strftime("%Y-%m-%d"),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
            ))

    current_price = float(history["Close"].iloc[-1]) if not history.empty else 0.0

    return PriceHistory(
        ticker=symbol,
        current_price=current_price,
        ohlcv=bars,
    )
