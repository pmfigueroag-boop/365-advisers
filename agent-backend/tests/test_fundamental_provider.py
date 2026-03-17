"""
tests/test_fundamental_provider.py
--------------------------------------------------------------------------
Tests for FundamentalProvider: field mapping, forward fill, edge cases.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from datetime import date

import pandas as pd
import numpy as np

from src.engines.backtesting.fundamental_provider import (
    FundamentalProvider,
    _safe_div,
    _get_field,
)


class TestSafeDiv:
    def test_normal(self):
        assert _safe_div(10.0, 2.0) == 5.0

    def test_zero_denominator(self):
        assert _safe_div(10.0, 0.0) is None

    def test_none_numerator(self):
        assert _safe_div(None, 5.0) is None

    def test_none_denominator(self):
        assert _safe_div(10.0, None) is None

    def test_nan(self):
        assert _safe_div(float("nan"), 5.0) is None
        assert _safe_div(5.0, float("nan")) is None


class TestGetField:
    def test_existing_field(self):
        df = pd.DataFrame(
            {"2024-Q1": [100.0, 50.0]},
            index=["Total Revenue", "Net Income"],
        )
        assert _get_field(df, "Total Revenue", "2024-Q1") == 100.0
        assert _get_field(df, "Net Income", "2024-Q1") == 50.0

    def test_missing_field(self):
        df = pd.DataFrame(
            {"2024-Q1": [100.0]},
            index=["Total Revenue"],
        )
        assert _get_field(df, "EBITDA", "2024-Q1") is None

    def test_nan_value(self):
        df = pd.DataFrame(
            {"2024-Q1": [float("nan")]},
            index=["Total Revenue"],
        )
        assert _get_field(df, "Total Revenue", "2024-Q1") is None


class TestFundamentalProvider:
    def test_empty_on_failure(self):
        provider = FundamentalProvider(cache_enabled=False)
        # With a nonsensical ticker, should return empty
        with patch("src.engines.backtesting.fundamental_provider.yf") as mock_yf:
            mock_ticker = MagicMock()
            mock_ticker.quarterly_financials = pd.DataFrame()
            mock_ticker.quarterly_balance_sheet = pd.DataFrame()
            mock_ticker.quarterly_cashflow = pd.DataFrame()
            mock_ticker.info = {}
            mock_yf.Ticker.return_value = mock_ticker

            result = provider.get_snapshots(
                "INVALID", date(2024, 1, 1), date(2024, 6, 1)
            )
            assert result == {}

    def test_cache_works(self):
        provider = FundamentalProvider(cache_enabled=True)
        # First call puts in cache
        provider._cache["AAPL"] = {"2024-01-15": {"pe_ratio": 25.0}}

        result = provider.get_snapshots(
            "AAPL", date(2024, 1, 1), date(2024, 6, 1)
        )
        assert result == {"2024-01-15": {"pe_ratio": 25.0}}

    def test_cache_clear(self):
        provider = FundamentalProvider(cache_enabled=True)
        provider._cache["AAPL"] = {"2024-01-15": {"pe_ratio": 25.0}}
        provider.clear_cache()
        assert len(provider._cache) == 0

    def test_extract_quarter_margins(self):
        """Test that margins are correctly computed from income statement."""
        provider = FundamentalProvider(cache_enabled=False)

        # Mock income statement
        q_date = pd.Timestamp("2024-03-31")
        income_stmt = pd.DataFrame(
            {q_date: [1000.0, 600.0, 200.0, 250.0, 300.0, 100.0]},
            index=[
                "Total Revenue", "Gross Profit", "Operating Income",
                "EBIT", "EBITDA", "Net Income",
            ],
        )

        snap = provider._extract_quarter(
            q_date, income_stmt,
            balance_sheet=None, cashflow=None,
            ohlcv=None, shares_outstanding=None, info={},
        )

        assert snap["gross_margin"] == 0.6  # 600/1000
        assert snap["ebit_margin"] == 0.2  # 200/1000
        assert snap["net_margin"] == 0.1  # 100/1000

    def test_forward_fill(self):
        """Test that quarterly snapshots are forward-filled to daily."""
        provider = FundamentalProvider(cache_enabled=False)

        # Mock yfinance
        with patch("src.engines.backtesting.fundamental_provider.yf") as mock_yf:
            q1_date = pd.Timestamp("2024-03-31")
            q2_date = pd.Timestamp("2024-06-30")

            income_stmt = pd.DataFrame(
                {q1_date: [1000.0, 100.0], q2_date: [1100.0, 120.0]},
                index=["Total Revenue", "Net Income"],
            )

            mock_ticker = MagicMock()
            mock_ticker.quarterly_financials = income_stmt
            mock_ticker.quarterly_balance_sheet = pd.DataFrame()
            mock_ticker.quarterly_cashflow = pd.DataFrame()
            mock_ticker.info = {}
            mock_yf.Ticker.return_value = mock_ticker

            result = provider.get_snapshots(
                "TEST", date(2024, 4, 1), date(2024, 8, 1)
            )

            # Should have daily entries forward-filled from quarterly
            assert len(result) > 0
            # All dates in April should use Q1 data (net_margin = 100/1000 = 0.1)
            april_dates = [d for d in result if d.startswith("2024-04")]
            if april_dates:
                assert result[april_dates[0]]["net_margin"] == pytest.approx(0.1, abs=0.01)

            # Dates after July should use Q2 data (net_margin = 120/1100)
            july_dates = [d for d in result if d.startswith("2024-07")]
            if july_dates:
                expected_nm = 120.0 / 1100.0
                assert result[july_dates[0]]["net_margin"] == pytest.approx(expected_nm, abs=0.01)
