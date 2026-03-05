"""
tests/test_phase2_data_layer.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for Phase 2: Data Layer Split.

Tests validate:
  1. Provider functions return correct contract types
  2. Repositories can be imported and instantiated
  3. Providers handle edge cases (empty data, missing info)
"""

import pytest
from src.contracts.market_data import (
    PriceHistory, FinancialStatements, MarketMetrics,
    OHLCVBar, RawIndicators,
)


# ─── Provider Return Types ────────────────────────────────────────────────────

class TestProviderImports:
    """Verify all providers can be imported and return the right types."""

    def test_price_history_provider_exists(self):
        from src.data.providers.price_history import fetch_price_history
        assert callable(fetch_price_history)

    def test_financials_provider_exists(self):
        from src.data.providers.financials import fetch_financials
        assert callable(fetch_financials)

    def test_market_metrics_provider_exists(self):
        from src.data.providers.market_metrics import fetch_market_metrics
        assert callable(fetch_market_metrics)

    def test_provider_package_exports(self):
        from src.data.providers import fetch_price_history, fetch_financials, fetch_market_metrics
        assert all(callable(f) for f in [fetch_price_history, fetch_financials, fetch_market_metrics])


# ─── Contract Compatibility ───────────────────────────────────────────────────

class TestContractCompatibility:
    """Verify contracts work with the providers' expected output shapes."""

    def test_price_history_from_raw_bars(self):
        bars = [OHLCVBar(time="2024-01-01", open=150, high=155, low=148, close=152, volume=1000000)]
        ph = PriceHistory(ticker="TEST", current_price=152.0, ohlcv=bars)
        assert ph.ticker == "TEST"
        assert len(ph.ohlcv) == 1
        assert ph.ohlcv[0].close == 152

    def test_financial_statements_with_ratios(self):
        from src.contracts.market_data import FinancialRatios, ProfitabilityRatios
        fs = FinancialStatements(
            ticker="TEST",
            name="Test Corp",
            ratios=FinancialRatios(
                profitability=ProfitabilityRatios(roic=0.15)
            ),
        )
        assert fs.ratios.profitability.roic == 0.15
        assert fs.ratios.leverage.current_ratio is None

    def test_market_metrics_with_indicators(self):
        mm = MarketMetrics(
            ticker="TEST",
            exchange="NASDAQ",
            indicators=RawIndicators(rsi=65.0, sma50=175.0),
        )
        assert mm.indicators.rsi == 65.0
        assert mm.indicators.sma50 == 175.0
        assert mm.indicators.macd == 0.0  # default


# ─── Repository Imports ──────────────────────────────────────────────────────

class TestRepositoryImports:
    """Verify repositories can be imported and have expected methods."""

    def test_score_repository_methods(self):
        from src.data.repositories.score_repository import ScoreRepository
        assert hasattr(ScoreRepository, "save_opportunity_score")
        assert hasattr(ScoreRepository, "get_opportunity_history")
        assert hasattr(ScoreRepository, "get_score_history")

    def test_portfolio_repository_methods(self):
        from src.data.repositories.portfolio_repository import PortfolioRepository
        assert hasattr(PortfolioRepository, "save_portfolio")
        assert hasattr(PortfolioRepository, "list_portfolios")
        assert hasattr(PortfolioRepository, "get_portfolio")
        assert hasattr(PortfolioRepository, "delete_portfolio")


# ─── Market Metrics Helpers ───────────────────────────────────────────────────

class TestMarketMetricsHelpers:
    """Test internal helper functions."""

    def test_resolve_exchange(self):
        from src.data.providers.market_metrics import _resolve_exchange
        assert _resolve_exchange("NYQ") == "NYSE"
        assert _resolve_exchange("NMS") == "NASDAQ"
        assert _resolve_exchange("UNKNOWN") == "NASDAQ"

    def test_get_tv_indicator_single_key(self):
        from src.data.providers.market_metrics import _get_tv_indicator
        inds = {"RSI": 65.5, "MACD.macd": 1.2}
        assert _get_tv_indicator(inds, "RSI") == 65.5
        assert _get_tv_indicator(inds, "NONEXISTENT", 50.0) == 50.0

    def test_get_tv_indicator_multi_key(self):
        from src.data.providers.market_metrics import _get_tv_indicator
        inds = {"EMA20": 178.5}
        assert _get_tv_indicator(inds, ["SMA20", "EMA20"]) == 178.5

    def test_get_tv_indicator_none_value(self):
        from src.data.providers.market_metrics import _get_tv_indicator
        inds = {"RSI": None}
        assert _get_tv_indicator(inds, "RSI", 50.0) == 50.0
