"""
tests/test_integration_layer.py
──────────────────────────────────────────────────────────────────────────────
Test suite for the multi-source API integration layer.

Tests:
  1. New canonical contracts — empty factories, field presence
  2. New adapters — instantiation, name, domain, capabilities
  3. Stub adapters — error responses, documentation
  4. Extended registry — all adapters register, domain counts
  5. Config — new API key fields, timeouts, feature flags
  6. Scheduler — schedule definitions, manager operations
  7. Data domains — new enums exist
"""

import pytest


# ── 1. Canonical Contract Tests ──────────────────────────────────────────────


class TestNewContracts:
    """Tests for the 9 new canonical contracts."""

    def test_asset_profile_empty(self):
        from src.data.external.contracts.asset_profile import AssetProfile
        p = AssetProfile.empty("AAPL")
        assert p.ticker == "AAPL"
        assert p.source == "null"
        assert p.market_cap is None
        assert p.sector == ""

    def test_financial_statement_empty(self):
        from src.data.external.contracts.financial_statement import FinancialStatementData
        s = FinancialStatementData.empty("AAPL")
        assert s.ticker == "AAPL"
        assert s.source == "null"
        assert s.income_statements == []
        assert s.balance_sheets == []
        assert s.cash_flows == []

    def test_financial_ratios_empty(self):
        from src.data.external.contracts.financial_ratios import FinancialRatios
        r = FinancialRatios.empty("AAPL")
        assert r.ticker == "AAPL"
        assert r.source == "null"
        assert r.pe_ratio is None
        assert r.roe is None

    def test_analyst_estimate_empty(self):
        from src.data.external.contracts.analyst_estimate import AnalystEstimateData
        e = AnalystEstimateData.empty("AAPL")
        assert e.ticker == "AAPL"
        assert e.source == "null"
        assert e.earnings_estimates == []

    def test_economic_indicator_empty(self):
        from src.data.external.contracts.economic_indicator import EconomicIndicatorData
        i = EconomicIndicatorData.empty("GDP")
        assert i.series.series_id == "GDP"
        assert i.source == "null"
        assert i.observations == []

    def test_sentiment_signal_empty(self):
        from src.data.external.contracts.sentiment_signal import SentimentSignal
        s = SentimentSignal.empty("AAPL")
        assert s.ticker == "AAPL"
        assert s.source == "null"
        assert s.bullish_pct is None

    def test_alternative_signal_empty(self):
        from src.data.external.contracts.alternative_signal import AlternativeSignal
        a = AlternativeSignal.empty("AAPL")
        assert a.ticker == "AAPL"
        assert a.source == "null"
        assert a.web_traffic is None

    def test_options_chain_empty(self):
        from src.data.external.contracts.options_chain import OptionsChainData
        o = OptionsChainData.empty("AAPL")
        assert o.ticker == "AAPL"
        assert o.source == "null"
        assert o.expirations == []

    def test_volatility_snapshot_empty(self):
        from src.data.external.contracts.volatility_snapshot import VolatilitySnapshot
        v = VolatilitySnapshot.empty()
        assert v.ticker == "^VIX"
        assert v.source == "null"
        assert v.vix is None

    def test_contracts_init_exports_all(self):
        from src.data.external.contracts import (
            AssetProfile, FinancialStatementData, FinancialRatios,
            AnalystEstimateData, EconomicIndicatorData, SentimentSignal,
            AlternativeSignal, OptionsChainData, VolatilitySnapshot,
        )
        # Just verify they're importable
        assert AssetProfile is not None
        assert VolatilitySnapshot is not None


# ── 2. New Adapter Tests ─────────────────────────────────────────────────────


class TestNewAdapters:
    """Tests for the 6 Priority 1 + 2 Priority 2 adapters."""

    def test_alpha_vantage(self):
        from src.data.external.adapters.alpha_vantage import AlphaVantageAdapter
        a = AlphaVantageAdapter()
        assert a.name == "alpha_vantage"
        assert a.domain.value == "market_data"
        assert len(a.get_capabilities()) >= 2

    def test_twelve_data(self):
        from src.data.external.adapters.twelve_data import TwelveDataAdapter
        a = TwelveDataAdapter()
        assert a.name == "twelve_data"
        assert a.domain.value == "market_data"
        assert len(a.get_capabilities()) == 2

    def test_fmp(self):
        from src.data.external.adapters.fmp import FMPAdapter
        a = FMPAdapter()
        assert a.name == "fmp"
        assert a.domain.value == "fundamental"
        assert len(a.get_capabilities()) == 4

    def test_world_bank(self):
        from src.data.external.adapters.world_bank import WorldBankAdapter
        a = WorldBankAdapter()
        assert a.name == "world_bank"
        assert a.domain.value == "macro"
        assert len(a.get_capabilities()) >= 3

    def test_stocktwits(self):
        from src.data.external.adapters.stocktwits import StocktwitsAdapter
        a = StocktwitsAdapter()
        assert a.name == "stocktwits"
        assert a.domain.value == "sentiment"
        assert len(a.get_capabilities()) == 2

    def test_cboe(self):
        from src.data.external.adapters.cboe import CboeAdapter
        a = CboeAdapter()
        assert a.name == "cboe"
        assert a.domain.value == "volatility"
        assert len(a.get_capabilities()) >= 2

    def test_santiment(self):
        from src.data.external.adapters.santiment import SantimentAdapter
        a = SantimentAdapter()
        assert a.name == "santiment"
        assert a.domain.value == "sentiment"

    def test_imf(self):
        from src.data.external.adapters.imf import IMFAdapter
        a = IMFAdapter()
        assert a.name == "imf"
        assert a.domain.value == "macro"


# ── 3. Stub Adapter Tests ───────────────────────────────────────────────────


class TestStubAdapters:
    """Tests for the 4 commercial API stubs."""

    def test_morningstar(self):
        from src.data.external.adapters.stubs import MorningstarAdapter
        a = MorningstarAdapter()
        assert a.name == "morningstar"
        assert a.domain.value == "fundamental"
        assert len(a.get_capabilities()) >= 3

    def test_similarweb(self):
        from src.data.external.adapters.stubs import SimilarwebAdapter
        a = SimilarwebAdapter()
        assert a.name == "similarweb"
        assert a.domain.value == "alternative"

    def test_thinknum(self):
        from src.data.external.adapters.stubs import ThinknumAdapter
        a = ThinknumAdapter()
        assert a.name == "thinknum"
        assert a.domain.value == "alternative"

    def test_optionmetrics(self):
        from src.data.external.adapters.stubs import OptionMetricsAdapter
        a = OptionMetricsAdapter()
        assert a.name == "optionmetrics"
        assert a.domain.value == "volatility"

    def test_stubs_return_error(self):
        import asyncio
        from src.data.external.adapters.stubs import MorningstarAdapter
        from src.data.external.base import ProviderRequest, DataDomain
        a = MorningstarAdapter()
        req = ProviderRequest(domain=DataDomain.FUNDAMENTAL, ticker="AAPL")
        resp = asyncio.get_event_loop().run_until_complete(a.fetch(req))
        assert not resp.ok
        assert "stub" in resp.error.lower() or "commercial" in resp.error.lower()

    def test_stubs_health_disabled(self):
        import asyncio
        from src.data.external.adapters.stubs import SimilarwebAdapter
        a = SimilarwebAdapter()
        h = asyncio.get_event_loop().run_until_complete(a.health_check())
        assert h.status.value == "disabled"


# ── 4. Extended Registry Tests ───────────────────────────────────────────────


class TestExtendedRegistry:
    """Tests for registering all adapters (existing + new)."""

    def test_all_new_adapters_register(self):
        from src.data.external.registry import ProviderRegistry
        from src.data.external.adapters.alpha_vantage import AlphaVantageAdapter
        from src.data.external.adapters.twelve_data import TwelveDataAdapter
        from src.data.external.adapters.fmp import FMPAdapter
        from src.data.external.adapters.world_bank import WorldBankAdapter
        from src.data.external.adapters.stocktwits import StocktwitsAdapter
        from src.data.external.adapters.cboe import CboeAdapter
        from src.data.external.adapters.santiment import SantimentAdapter
        from src.data.external.adapters.imf import IMFAdapter
        from src.data.external.adapters.stubs import (
            MorningstarAdapter, SimilarwebAdapter, ThinknumAdapter, OptionMetricsAdapter,
        )

        reg = ProviderRegistry()
        adapters = [
            AlphaVantageAdapter(), TwelveDataAdapter(), FMPAdapter(),
            WorldBankAdapter(), StocktwitsAdapter(), CboeAdapter(),
            SantimentAdapter(), IMFAdapter(),
            MorningstarAdapter(), SimilarwebAdapter(),
            ThinknumAdapter(), OptionMetricsAdapter(),
        ]
        for a in adapters:
            reg.register(a)

        # Should have adapters across multiple domains
        assert len(reg.list_domains()) >= 5
        summary = reg.summary()
        assert len(summary) >= 5

    def test_new_domains_exist(self):
        from src.data.external.base import DataDomain
        assert DataDomain.FUNDAMENTAL.value == "fundamental"
        assert DataDomain.ALTERNATIVE.value == "alternative"
        assert DataDomain.VOLATILITY.value == "volatility"


# ── 5. Config Tests ──────────────────────────────────────────────────────────


class TestNewConfig:
    """Tests for new EDPL configuration settings."""

    def test_new_api_keys_exist(self):
        from src.config import get_settings
        s = get_settings()
        assert hasattr(s, "ALPHA_VANTAGE_API_KEY")
        assert hasattr(s, "TWELVE_DATA_API_KEY")
        assert hasattr(s, "FMP_API_KEY")
        assert hasattr(s, "STOCKTWITS_API_KEY")
        assert hasattr(s, "SANTIMENT_API_KEY")
        assert hasattr(s, "CBOE_API_KEY")

    def test_new_timeouts_exist(self):
        from src.config import get_settings
        s = get_settings()
        assert hasattr(s, "EDPL_AV_TIMEOUT")
        assert hasattr(s, "EDPL_TD_TIMEOUT")
        assert hasattr(s, "EDPL_FMP_TIMEOUT")
        assert hasattr(s, "EDPL_WB_TIMEOUT")

    def test_new_feature_flags_default_true(self):
        from src.config import get_settings
        s = get_settings()
        assert s.EDPL_ENABLE_FUNDAMENTAL is True
        assert s.EDPL_ENABLE_ALTERNATIVE is True
        assert s.EDPL_ENABLE_VOLATILITY is True

    def test_new_cache_ttls(self):
        from src.config import get_settings
        s = get_settings()
        assert s.EDPL_CACHE_TTL_FUNDAMENTAL == 86400
        assert s.EDPL_CACHE_TTL_VOLATILITY == 900


# ── 6. Scheduler Tests ──────────────────────────────────────────────────────


class TestScheduler:
    """Tests for the sync scheduler."""

    def test_default_schedules_exist(self):
        from src.data.external.scheduler import SyncManager
        mgr = SyncManager()
        schedules = mgr.get_schedules()
        assert len(schedules) >= 8

    def test_get_schedule_by_domain(self):
        from src.data.external.scheduler import SyncManager
        mgr = SyncManager()
        s = mgr.get_schedule("market_data")
        assert s is not None
        assert s.market_hours_only is True

    def test_update_frequency(self):
        from src.data.external.scheduler import SyncManager, SyncFrequency
        mgr = SyncManager()
        ok = mgr.update_frequency("macro", SyncFrequency.DAILY, "0 9 * * 1-5")
        assert ok
        s = mgr.get_schedule("macro")
        assert s.frequency == SyncFrequency.DAILY

    def test_summary_serializable(self):
        from src.data.external.scheduler import SyncManager
        mgr = SyncManager()
        summary = mgr.summary()
        assert isinstance(summary, list)
        assert all("domain" in s and "frequency" in s for s in summary)


# ── 7. New Capability Enum Tests ─────────────────────────────────────────────


class TestNewCapabilities:
    """Tests for new ProviderCapability enum values."""

    def test_fundamental_capabilities(self):
        from src.data.external.base import ProviderCapability
        assert ProviderCapability.FINANCIAL_STATEMENTS.value == "financial_statements"
        assert ProviderCapability.FINANCIAL_RATIOS.value == "financial_ratios"
        assert ProviderCapability.ANALYST_ESTIMATES.value == "analyst_estimates"
        assert ProviderCapability.COMPANY_PROFILE.value == "company_profile"

    def test_macro_capabilities(self):
        from src.data.external.base import ProviderCapability
        assert ProviderCapability.GDP_DATA.value == "gdp_data"
        assert ProviderCapability.INFLATION_DATA.value == "inflation_data"

    def test_volatility_capabilities(self):
        from src.data.external.base import ProviderCapability
        assert ProviderCapability.VIX_DATA.value == "vix_data"
        assert ProviderCapability.VOLATILITY_SURFACE.value == "volatility_surface"
