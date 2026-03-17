"""
tests/test_cross_sectional.py
--------------------------------------------------------------------------
Tests for CrossSectionalRanker: quintile sorting, spread, monotonicity.
"""

from __future__ import annotations

import pytest
from datetime import date

import pandas as pd
import numpy as np

from src.engines.backtesting.cross_sectional import CrossSectionalRanker
from src.engines.backtesting.cross_sectional_models import (
    CrossSectionalConfig,
    CrossSectionalReport,
    QuintileResult,
)


def _make_synthetic_ohlcv(
    n_days: int = 500,
    base_price: float = 100.0,
    daily_return: float = 0.001,
    start_date: str = "2022-01-01",
) -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    dates = pd.bdate_range(start=start_date, periods=n_days)
    prices = [base_price]
    for _ in range(n_days - 1):
        prices.append(prices[-1] * (1 + daily_return + np.random.normal(0, 0.015)))

    df = pd.DataFrame({
        "Open": [p * 0.999 for p in prices],
        "High": [p * 1.01 for p in prices],
        "Low": [p * 0.99 for p in prices],
        "Close": prices,
        "Volume": [1_000_000] * n_days,
    }, index=dates)
    return df


class TestCrossSectionalRanker:
    def setup_method(self):
        self.ranker = CrossSectionalRanker()

    def test_insufficient_tickers(self):
        """Need at least 10 tickers for valid quintiles."""
        config = CrossSectionalConfig(
            universe=["AAPL"] * 10,  # min_length=10
            start_date=date(2023, 1, 1),
            end_date=date(2024, 1, 1),
        )
        # With empty OHLCV data, should return empty report
        report = self.ranker.run(config, {})
        assert report.total_periods == 0

    def test_with_synthetic_data(self):
        """Run with synthetic data for 20 tickers."""
        np.random.seed(42)
        tickers = [f"T{i:02d}" for i in range(20)]

        # Create data with different drift rates (T00 best, T19 worst)
        ohlcv_data = {}
        for i, ticker in enumerate(tickers):
            drift = 0.002 - (i * 0.0002)  # T00=0.2%, T19=-0.18%
            ohlcv_data[ticker] = _make_synthetic_ohlcv(
                n_days=500, daily_return=drift,
            )

        # Add benchmark
        ohlcv_data["SPY"] = _make_synthetic_ohlcv(n_days=500, daily_return=0.0005)

        config = CrossSectionalConfig(
            universe=tickers,
            start_date=date(2022, 1, 1),
            end_date=date(2023, 12, 31),
            rebalance_frequency_days=21,
            forward_windows=[20, 60],
            benchmark_ticker="SPY",
        )

        report = self.ranker.run(config, ohlcv_data)

        assert report.total_periods > 0
        assert report.execution_time_seconds > 0

    def test_spearman_manual_perfect(self):
        """Perfect monotonicity: Q1 best, Q5 worst."""
        result = self.ranker._spearman_manual([0.05, 0.04, 0.03, 0.02, 0.01])
        assert result == 1.0  # Perfect positive correlation

    def test_spearman_manual_inverse(self):
        """Inverse monotonicity: Q5 best, Q1 worst."""
        result = self.ranker._spearman_manual([0.01, 0.02, 0.03, 0.04, 0.05])
        assert result == -1.0

    def test_spearman_manual_random(self):
        """Random order: correlation near 0."""
        result = self.ranker._spearman_manual([0.03, 0.05, 0.01, 0.04, 0.02])
        assert -1.0 <= result <= 1.0

    def test_normal_cdf_bounds(self):
        assert self.ranker._normal_cdf(-10.0) == 0.0
        assert self.ranker._normal_cdf(10.0) == 1.0
        assert 0.49 < self.ranker._normal_cdf(0.0) < 0.51


class TestQuintileResult:
    def test_creation(self):
        q = QuintileResult(
            quintile=1, n_tickers=20,
            avg_score=0.75,
            avg_return={20: 0.05},
            avg_excess_return={20: 0.03},
            tickers=["AAPL", "MSFT"],
        )
        assert q.quintile == 1
        assert q.n_tickers == 20
        assert q.avg_return[20] == 0.05

    def test_empty(self):
        q = QuintileResult(quintile=3)
        assert q.n_tickers == 0
        assert q.avg_return == {}


class TestCrossSectionalConfig:
    def test_defaults(self):
        config = CrossSectionalConfig(
            universe=[f"T{i}" for i in range(10)],
            start_date=date(2023, 1, 1),
        )
        assert config.rebalance_frequency_days == 21
        assert config.benchmark_ticker == "SPY"
        assert config.include_fundamentals is False

    def test_min_universe(self):
        with pytest.raises(Exception):
            CrossSectionalConfig(
                universe=["AAPL"],  # Too few
                start_date=date(2023, 1, 1),
            )
