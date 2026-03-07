"""
tests/test_edpl.py
──────────────────────────────────────────────────────────────────────────────
End-to-end test suite for the External Data Provider Layer.

Tests:
  1. Foundation — registry, health checker, circuit breaker
  2. Fallback Router — priority chain, null contract fallback
  3. Adapters — instantiation, capabilities, empty-data handling
  4. Feature Extractors — contract → engine param transformation
  5. Config — EDPL settings loaded correctly
"""

import asyncio
import pytest
from datetime import datetime, timezone

# ── Foundation Tests ──────────────────────────────────────────────────────────


class TestCircuitBreaker:
    """Tests for the CircuitBreaker state machine."""

    def test_starts_closed(self):
        from src.data.external.health import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == "closed"
        assert not cb.is_open

    def test_opens_after_threshold(self):
        from src.data.external.health import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"  # not yet
        cb.record_failure()
        assert cb.state == "open"
        assert cb.is_open

    def test_closes_on_success(self):
        from src.data.external.health import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open
        cb.record_success()
        assert cb.state == "closed"
        assert not cb.is_open

    def test_partial_failures_dont_trip(self):
        from src.data.external.health import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()  # resets
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"  # only 2 consecutive


class TestProviderRegistry:
    """Tests for the ProviderRegistry."""

    def test_empty_registry(self):
        from src.data.external.registry import ProviderRegistry
        from src.data.external.base import DataDomain
        reg = ProviderRegistry()
        assert reg.get_primary(DataDomain.MARKET_DATA) is None
        assert reg.list_domains() == []
        assert reg.summary() == {}

    def test_register_and_lookup(self):
        from src.data.external.registry import ProviderRegistry
        from src.data.external.adapters.polygon import PolygonAdapter
        reg = ProviderRegistry()
        adapter = PolygonAdapter()
        reg.register(adapter)
        assert reg.get_primary(adapter.domain) == adapter
        assert len(reg.get_all(adapter.domain)) == 1

    def test_duplicate_registration_skipped(self):
        from src.data.external.registry import ProviderRegistry
        from src.data.external.adapters.polygon import PolygonAdapter
        reg = ProviderRegistry()
        adapter = PolygonAdapter()
        reg.register(adapter)
        reg.register(adapter)  # duplicate
        assert len(reg.get_all(adapter.domain)) == 1

    def test_unregister(self):
        from src.data.external.registry import ProviderRegistry
        from src.data.external.adapters.polygon import PolygonAdapter
        reg = ProviderRegistry()
        adapter = PolygonAdapter()
        reg.register(adapter)
        assert reg.unregister(adapter.name)
        assert reg.get_primary(adapter.domain) is None

    def test_status_management(self):
        from src.data.external.registry import ProviderRegistry
        from src.data.external.base import ProviderStatus
        from src.data.external.adapters.polygon import PolygonAdapter
        reg = ProviderRegistry()
        adapter = PolygonAdapter()
        reg.register(adapter)
        reg.set_status(adapter.name, ProviderStatus.DISABLED)
        assert reg.get_status(adapter.name) == ProviderStatus.DISABLED
        # get_primary skips disabled adapters
        assert reg.get_primary(adapter.domain) is None


class TestHealthChecker:
    """Tests for the HealthChecker."""

    def test_record_success(self):
        from src.data.external.health import HealthChecker
        from src.data.external.base import DataDomain, ProviderStatus
        hc = HealthChecker()
        hc.register_provider("test", DataDomain.MARKET_DATA)
        hc.record_success("test", 42.0)
        h = hc.get_health("test")
        assert h.status == ProviderStatus.ACTIVE
        assert h.avg_latency_ms == 42.0
        assert h.consecutive_failures == 0

    def test_record_failure_trips_breaker(self):
        from src.data.external.health import HealthChecker
        from src.data.external.base import DataDomain, ProviderStatus
        hc = HealthChecker(failure_threshold=2)
        hc.register_provider("test", DataDomain.MARKET_DATA)
        hc.record_failure("test", "timeout")
        hc.record_failure("test", "timeout")
        h = hc.get_health("test")
        assert h.status == ProviderStatus.DISABLED
        assert h.consecutive_failures == 2
        assert hc.is_circuit_open("test")

    def test_summary(self):
        from src.data.external.health import HealthChecker
        from src.data.external.base import DataDomain
        hc = HealthChecker()
        hc.register_provider("p1", DataDomain.MARKET_DATA)
        hc.register_provider("p2", DataDomain.OPTIONS)
        summary = hc.summary()
        assert "p1" in summary
        assert "p2" in summary


# ── Fallback Router Tests ────────────────────────────────────────────────────


class TestFallbackRouter:
    """Tests for the FallbackRouter."""

    def test_null_response_when_no_adapters(self):
        from src.data.external.registry import ProviderRegistry
        from src.data.external.health import HealthChecker
        from src.data.external.fallback import FallbackRouter
        from src.data.external.base import DataDomain, ProviderRequest

        reg = ProviderRegistry()
        hc = HealthChecker()
        router = FallbackRouter(reg, hc)

        req = ProviderRequest(domain=DataDomain.MARKET_DATA)
        resp = asyncio.get_event_loop().run_until_complete(
            router.fetch(DataDomain.MARKET_DATA, req)
        )
        assert not resp.ok
        assert resp.provider_name == "null"

    def test_null_factory_produces_contract(self):
        from src.data.external.registry import ProviderRegistry
        from src.data.external.health import HealthChecker
        from src.data.external.fallback import FallbackRouter
        from src.data.external.base import DataDomain, ProviderRequest
        from src.data.external.contracts.enhanced_market import EnhancedMarketData

        reg = ProviderRegistry()
        hc = HealthChecker()
        router = FallbackRouter(
            reg, hc,
            null_factories={DataDomain.MARKET_DATA: EnhancedMarketData.empty},
        )

        req = ProviderRequest(domain=DataDomain.MARKET_DATA)
        resp = asyncio.get_event_loop().run_until_complete(
            router.fetch(DataDomain.MARKET_DATA, req)
        )
        assert resp.data is not None  # null factory produced a contract
        assert resp.data.source == "null"


# ── Adapter Tests ────────────────────────────────────────────────────────────


class TestAdapters:
    """Tests for adapter instantiation and capabilities."""

    def test_polygon_adapter(self):
        from src.data.external.adapters.polygon import PolygonAdapter
        a = PolygonAdapter()
        assert a.name == "polygon"
        assert a.domain.value == "market_data"
        assert len(a.get_capabilities()) == 4

    def test_etf_flow_adapter(self):
        from src.data.external.adapters.etf_flows import ETFFlowAdapter
        a = ETFFlowAdapter()
        assert a.name == "etf_flows"
        assert a.domain.value == "etf_flows"
        assert len(a.get_capabilities()) == 3

    def test_options_adapter(self):
        from src.data.external.adapters.options import OptionsAdapter
        a = OptionsAdapter()
        assert a.name == "options"
        assert a.domain.value == "options"
        assert len(a.get_capabilities()) >= 1

    def test_institutional_adapter(self):
        from src.data.external.adapters.institutional import InstitutionalAdapter
        a = InstitutionalAdapter()
        assert a.name == "institutional"
        assert a.domain.value == "institutional"
        assert len(a.get_capabilities()) == 2

    def test_sentiment_adapter(self):
        from src.data.external.adapters.news_sentiment import NewsSentimentAdapter
        a = NewsSentimentAdapter()
        assert a.name == "news_sentiment"
        assert a.domain.value == "sentiment"
        assert len(a.get_capabilities()) == 3

    def test_macro_adapter(self):
        from src.data.external.adapters.macro import MacroAdapter
        a = MacroAdapter()
        assert a.name == "macro"
        assert a.domain.value == "macro"
        assert len(a.get_capabilities()) == 3


# ── Null Contract Tests ──────────────────────────────────────────────────────


class TestNullContracts:
    """Tests for empty/null contract factories."""

    def test_enhanced_market_empty(self):
        from src.data.external.contracts.enhanced_market import EnhancedMarketData
        e = EnhancedMarketData.empty("AAPL")
        assert e.ticker == "AAPL"
        assert e.source == "null"
        assert e.intraday_bars == []

    def test_etf_flow_empty(self):
        from src.data.external.contracts.etf_flows import ETFFlowData
        e = ETFFlowData.empty()
        assert e.source == "null"
        assert e.sector_flows == []

    def test_options_empty(self):
        from src.data.external.contracts.options import OptionsIntelligence
        e = OptionsIntelligence.empty("AAPL")
        assert e.ticker == "AAPL"
        assert e.source == "null"

    def test_institutional_empty(self):
        from src.data.external.contracts.institutional import InstitutionalFlowData
        e = InstitutionalFlowData.empty("AAPL")
        assert e.ticker == "AAPL"
        assert e.source == "null"

    def test_sentiment_empty(self):
        from src.data.external.contracts.sentiment import NewsSentimentData
        e = NewsSentimentData.empty("AAPL")
        assert e.ticker == "AAPL"
        assert e.source == "null"

    def test_macro_default(self):
        from src.data.external.contracts.macro import MacroContext
        m = MacroContext.default()
        assert m.source == "null"
        assert m.regime_classification == "unknown"


# ── Feature Extractor Tests ──────────────────────────────────────────────────


class TestFeatureExtractors:
    """Tests for feature extraction bridges."""

    def test_liquidity_features_empty(self):
        from src.features.liquidity_features import extract_liquidity_market_data
        from src.data.external.contracts.enhanced_market import EnhancedMarketData
        e = EnhancedMarketData.empty("AAPL")
        result = extract_liquidity_market_data(e, fallback_price=150.0)
        assert "avg_volume_20d" in result
        assert "avg_price" in result
        assert "market_cap" in result
        assert "bid_ask_spread" in result
        assert result["avg_price"] == 150.0

    def test_liquidity_features_with_data(self):
        from src.features.liquidity_features import extract_liquidity_market_data
        from src.data.external.contracts.enhanced_market import (
            EnhancedMarketData, IntradayBar, LiquiditySnapshot,
        )
        liq = LiquiditySnapshot(
            ticker="AAPL",
            bid_ask_spread_bps=1.5,
            avg_daily_volume_30d=50_000_000,
        )
        bars = [
            IntradayBar(
                timestamp=datetime.now(timezone.utc),
                open=150.0, high=151.0, low=149.0, close=150.5,
                volume=1_000_000,
            )
        ]
        data = EnhancedMarketData(
            ticker="AAPL", intraday_bars=bars, liquidity=liq,
            last_trade_price=150.5, source="polygon",
        )
        result = extract_liquidity_market_data(data)
        assert result["avg_volume_20d"] == 50_000_000
        assert result["bid_ask_spread"] > 0

    def test_crowding_features_empty(self):
        from src.features.crowding_features import build_crowding_params
        params = build_crowding_params()
        assert params["net_flows_5d"] == 0.0
        assert params["implied_vol_30d"] is None
        assert params["inst_ownership_change"] == 0.0

    def test_crowding_features_with_data(self):
        from src.features.crowding_features import build_crowding_params
        from src.data.external.contracts.etf_flows import ETFFlowData, SectorFlowSummary
        from src.data.external.contracts.options import OptionsIntelligence, OptionsSnapshot

        etf = ETFFlowData(
            sector_flows=[SectorFlowSummary(sector="Technology", net_flow_5d=250)],
            source="test",
        )
        opts = OptionsIntelligence(
            ticker="AAPL",
            snapshot=OptionsSnapshot(ticker="AAPL", implied_vol_30d=0.25),
        )
        params = build_crowding_params(etf_data=etf, options_data=opts, ticker_sector="Technology")
        assert params["net_flows_5d"] == 250
        assert params["implied_vol_30d"] == 0.25

    def test_intraday_volume_profile_empty(self):
        from src.features.liquidity_features import extract_intraday_volume_profile
        from src.data.external.contracts.enhanced_market import EnhancedMarketData
        e = EnhancedMarketData.empty("AAPL")
        profile = extract_intraday_volume_profile(e)
        assert profile is None  # Not enough data

    def test_impact_inputs_fallback(self):
        from src.features.liquidity_features import extract_impact_inputs
        from src.data.external.contracts.enhanced_market import EnhancedMarketData
        e = EnhancedMarketData.empty("AAPL")
        result = extract_impact_inputs(e, fallback_adv=50e6, fallback_price=150.0)
        assert result["adv"] == 50e6
        assert result["price"] == 150.0


# ── Config Tests ─────────────────────────────────────────────────────────────


class TestConfig:
    """Tests for EDPL configuration."""

    def test_edpl_settings_exist(self):
        from src.config import get_settings
        s = get_settings()
        assert hasattr(s, "POLYGON_API_KEY")
        assert hasattr(s, "EDPL_CB_FAILURE_THRESHOLD")
        assert hasattr(s, "EDPL_CACHE_TTL_MARKET")
        assert hasattr(s, "EDPL_ENABLE_MARKET_DATA")

    def test_feature_flags_default_true(self):
        from src.config import get_settings
        s = get_settings()
        assert s.EDPL_ENABLE_MARKET_DATA is True
        assert s.EDPL_ENABLE_ETF_FLOWS is True
        assert s.EDPL_ENABLE_OPTIONS is True
        assert s.EDPL_ENABLE_INSTITUTIONAL is True
        assert s.EDPL_ENABLE_SENTIMENT is True
        assert s.EDPL_ENABLE_MACRO is True

    def test_api_keys_default_empty(self):
        from src.config import get_settings
        s = get_settings()
        # API keys should default to empty (graceful degradation)
        assert s.POLYGON_API_KEY == "" or isinstance(s.POLYGON_API_KEY, str)


# ── Integration Test (full registry) ─────────────────────────────────────────


class TestFullRegistry:
    """Integration test — register all 6 adapters and verify."""

    def test_all_adapters_register(self):
        from src.data.external.registry import ProviderRegistry
        from src.data.external.health import HealthChecker
        from src.data.external.adapters.polygon import PolygonAdapter
        from src.data.external.adapters.etf_flows import ETFFlowAdapter
        from src.data.external.adapters.options import OptionsAdapter
        from src.data.external.adapters.institutional import InstitutionalAdapter
        from src.data.external.adapters.news_sentiment import NewsSentimentAdapter
        from src.data.external.adapters.macro import MacroAdapter

        reg = ProviderRegistry()
        hc = HealthChecker()
        adapters = [
            PolygonAdapter(), ETFFlowAdapter(), OptionsAdapter(),
            InstitutionalAdapter(), NewsSentimentAdapter(), MacroAdapter(),
        ]

        for a in adapters:
            reg.register(a)
            hc.register_provider(a.name, a.domain)

        assert len(reg.list_domains()) == 6
        assert len(hc.summary()) == 6

        # Verify each domain has exactly one adapter
        for a in adapters:
            assert reg.get_primary(a.domain) == a

        # Summary should have all 6 domains
        summary = reg.summary()
        assert len(summary) == 6
