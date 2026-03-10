"""
src/engines/idea_generation/backtest/market_data_provider.py
──────────────────────────────────────────────────────────────────────────────
Abstract market data provider for outcome evaluation.

Provides a clean protocol for fetching historical prices, decoupled
from any concrete data source. Includes a FakeMarketDataProvider
for deterministic testing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Protocol

logger = logging.getLogger("365advisers.idea_generation.backtest.market_data")


class MarketDataProvider(Protocol):
    """Protocol for fetching historical price data."""

    def get_price(self, ticker: str, date: datetime) -> float | None:
        """Get closing price for a ticker on/near a specific date.

        Returns None if data is unavailable.
        """
        ...

    def get_price_series(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[tuple[datetime, float]]:
        """Get a series of (date, price) tuples for a date range.

        Returns empty list if data is unavailable.
        """
        ...


class FakeMarketDataProvider:
    """Deterministic market data provider for testing.

    Generates synthetic prices using a simple formula based on the
    ticker hash and day offset, producing repeatable results.

    Usage::

        provider = FakeMarketDataProvider(base_prices={"AAPL": 150.0})
        price = provider.get_price("AAPL", some_date)
    """

    def __init__(
        self,
        base_prices: dict[str, float] | None = None,
        daily_return: float = 0.001,
        missing_tickers: set[str] | None = None,
    ) -> None:
        self._base_prices = base_prices or {}
        self._daily_return = daily_return
        self._missing_tickers = missing_tickers or set()
        self._override_prices: dict[tuple[str, str], float] = {}

    def set_price(self, ticker: str, date: datetime, price: float) -> None:
        """Set a specific price for testing."""
        key = (ticker, date.strftime("%Y-%m-%d"))
        self._override_prices[key] = price

    def get_price(self, ticker: str, date: datetime) -> float | None:
        """Get synthetic price for a ticker on a date."""
        if ticker in self._missing_tickers:
            return None

        key = (ticker, date.strftime("%Y-%m-%d"))
        if key in self._override_prices:
            return self._override_prices[key]

        base = self._base_prices.get(ticker, 100.0)
        # Simple compound growth from epoch for determinism
        epoch = datetime(2020, 1, 1, tzinfo=date.tzinfo)
        if date.tzinfo is None:
            epoch = datetime(2020, 1, 1)
        days = (date - epoch).days
        return round(base * (1 + self._daily_return) ** days, 2)

    def get_price_series(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[tuple[datetime, float]]:
        """Generate a synthetic daily price series."""
        if ticker in self._missing_tickers:
            return []

        series: list[tuple[datetime, float]] = []
        current = start_date
        while current <= end_date:
            price = self.get_price(ticker, current)
            if price is not None:
                series.append((current, price))
            current += timedelta(days=1)
        return series
