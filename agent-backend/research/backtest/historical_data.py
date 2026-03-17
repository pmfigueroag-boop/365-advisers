"""
historical_data.py
--------------------------------------------------------------------------------
Provides point-in-time historical data slices for quantitative backtesting.
Downloads bulk history once and slices it cleanly.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Any

import yfinance as yf
import pandas as pd
import numpy as np

logger = logging.getLogger("365advisers.backtest.historical")

class TimeMachine:
    """Historical data provider that prevents look-ahead bias."""

    def __init__(self, tickers: list[str], start_date: str, end_date: str):
        self.tickers = tickers
        self.start_date = start_date
        self.end_date = end_date
        self._data: Dict[str, pd.DataFrame] = {}
        
    def download_bulk(self):
        """Downloads all history at initialization to be fast later."""
        logger.info(f"Downloading historical data from {self.start_date} to {self.end_date} for {len(self.tickers)} tickers...")
        # yf.download can be finicky with multi-index, we'll download one by one for safety or use group_by
        data = yf.download(
            " ".join(self.tickers), 
            start=self.start_date, 
            end=self.end_date, 
            group_by='ticker',
            progress=False
        )
        
        if len(self.tickers) == 1:
            # yfinance doesn't use MultiIndex for a single ticker
            self._data[self.tickers[0]] = data.dropna()
        else:
            for ticker in self.tickers:
                if ticker in data:
                    self._data[ticker] = data[ticker].dropna()
                    
        logger.info(f"Bulk download complete. Loaded {len(self._data)} tickers.")

    def get_slice(self, ticker: str, current_date: datetime, lookback_days: int) -> pd.DataFrame:
        """Returns the dataframe exactly UP TO current_date strictly."""
        if ticker not in self._data:
            return pd.DataFrame()
            
        df = self._data[ticker]
        # Filter all rows strictly before or equal to current_date
        # Ensure timezone-naive comparison
        mask = df.index.tz_localize(None) <= current_date
        past_df = df[mask]
        
        if len(past_df) == 0:
            return pd.DataFrame()
            
        # Get the lookback period
        # We assume 1 trading day ~ 1 row, so 252 rows ~ 1 year.
        # But we'll just slice the last N calendar days or rows
        # Easiest is to slice rows:
        return past_df.tail(lookback_days)

    def get_latest_price(self, ticker: str, current_date: datetime) -> float | None:
        """Get the last available closing price on or before current_date."""
        df = self.get_slice(ticker, current_date, lookback_days=1)
        if df.empty:
            return None
        return float(df['Close'].iloc[-1])

    def get_trading_dates(self) -> list[datetime]:
        """Returns all unique trading dates across all loaded symbols."""
        all_dates = pd.DatetimeIndex([])
        for df in self._data.values():
            all_dates = all_dates.union(df.index)
        return sorted([d.to_pydatetime() for d in set(all_dates.tz_localize(None))])
