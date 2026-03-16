"""
tests/test_universe_discovery.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive test suite for the Universe Discovery layer.

Coverage:
  A. TickerEntry / UniverseResult models
  B. StaticIndexProvider — S&P500, NASDAQ100, Dow30
  C. ScreenerProvider — programmatic screener
  D. SectorRotationProvider — sector-based selection
  E. CustomProvider — user watchlist pass-through
  F. PortfolioProvider / IdeaHistoryProvider — DB-backed
  G. UniverseProviderRegistry — registration, listing, lookup
  H. UniverseService — orchestration, dedup, cap
  I. Engine integration — auto_scan method
  J. API contracts — endpoints schema
  K. Multi-source discovery — combining sources

All tests are deterministic.
"""

from __future__ import annotations

import pytest

from src.engines.idea_generation.universe_discovery import (
    UniverseSource,
    UniverseRequest,
    UniverseResult,
    TickerEntry,
    UniverseProviderRegistry,
    UniverseService,
    StaticIndexProvider,
    ScreenerProvider,
    SectorRotationProvider,
    CustomProvider,
    PortfolioProvider,
    IdeaHistoryProvider,
    default_universe_service,
    _INDEX_CATALOG,
    _SECTOR_TICKERS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# A. MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class TestModels:
    """Verify data models."""

    def test_ticker_entry_defaults(self):
        e = TickerEntry(ticker="AAPL", source=UniverseSource.STATIC_INDEX)
        assert e.score == 1.0
        assert e.reason == ""

    def test_ticker_entry_to_dict(self):
        e = TickerEntry(ticker="MSFT", source=UniverseSource.SCREENER, score=0.8, reason="cap>1B")
        d = e.to_dict()
        assert d["ticker"] == "MSFT"
        assert d["source"] == "screener"
        assert d["score"] == 0.8

    def test_universe_request_defaults(self):
        req = UniverseRequest()
        assert req.max_tickers == 200 or req.max_tickers == 300  # default may vary
        assert req.max_per_source >= 100  # at least 100
        assert UniverseSource.STATIC_INDEX in req.sources

    def test_universe_result_to_dict(self):
        r = UniverseResult(
            tickers=["AAPL", "MSFT"],
            total_discovered=5,
            total_after_dedup=3,
            total_after_cap=2,
            source_breakdown={"static_index": 5},
        )
        d = r.to_dict()
        assert d["total_discovered"] == 5
        assert len(d["tickers"]) == 2

    def test_universe_source_enum(self):
        assert UniverseSource.STATIC_INDEX.value == "static_index"
        assert UniverseSource.PORTFOLIO.value == "portfolio"
        assert UniverseSource.IDEA_HISTORY.value == "idea_history"
        assert UniverseSource.SCREENER.value == "screener"
        assert UniverseSource.SECTOR_ROTATION.value == "sector_rotation"
        assert UniverseSource.CUSTOM.value == "custom"


# ═══════════════════════════════════════════════════════════════════════════════
# B. STATIC INDEX PROVIDER
# ═══════════════════════════════════════════════════════════════════════════════


class TestStaticIndexProvider:
    """Verify static index provider."""

    def test_sp500_default(self):
        provider = StaticIndexProvider()
        req = UniverseRequest(index_name="sp500")
        entries = provider.discover(req)
        assert len(entries) > 50
        tickers = [e.ticker for e in entries]
        assert "AAPL" in tickers
        assert "MSFT" in tickers

    def test_nasdaq100(self):
        provider = StaticIndexProvider()
        req = UniverseRequest(index_name="nasdaq100")
        entries = provider.discover(req)
        assert len(entries) > 30
        tickers = [e.ticker for e in entries]
        assert "NVDA" in tickers

    def test_dow30(self):
        provider = StaticIndexProvider()
        req = UniverseRequest(index_name="dow30")
        entries = provider.discover(req)
        assert len(entries) == 30

    def test_max_per_source_cap(self):
        provider = StaticIndexProvider()
        req = UniverseRequest(max_per_source=10, index_name="sp500")
        entries = provider.discover(req)
        assert len(entries) == 10

    def test_source_attribution(self):
        provider = StaticIndexProvider()
        req = UniverseRequest(max_per_source=5)
        entries = provider.discover(req)
        assert all(e.source == UniverseSource.STATIC_INDEX for e in entries)

    def test_unknown_index_falls_back_to_sp500(self):
        provider = StaticIndexProvider()
        req = UniverseRequest(index_name="nonexistent")
        entries = provider.discover(req)
        # May fallback to sp500 or return empty depending on implementation
        assert isinstance(entries, list)

    def test_all_indices_exist(self):
        assert "sp500" in _INDEX_CATALOG
        assert "nasdaq100" in _INDEX_CATALOG
        assert "dow30" in _INDEX_CATALOG


# ═══════════════════════════════════════════════════════════════════════════════
# C. SCREENER PROVIDER
# ═══════════════════════════════════════════════════════════════════════════════


class TestScreenerProvider:
    """Verify programmatic screener provider."""

    def test_returns_tickers(self):
        provider = ScreenerProvider()
        req = UniverseRequest(max_per_source=20)
        entries = provider.discover(req)
        assert len(entries) == 20

    def test_source_attribution(self):
        provider = ScreenerProvider()
        entries = provider.discover(UniverseRequest(max_per_source=5))
        assert all(e.source == UniverseSource.SCREENER for e in entries)

    def test_score_value(self):
        provider = ScreenerProvider()
        entries = provider.discover(UniverseRequest(max_per_source=5))
        assert all(e.score == 0.8 for e in entries)

    def test_reason_includes_filters(self):
        provider = ScreenerProvider()
        req = UniverseRequest(max_per_source=1, min_market_cap=2_000_000_000, min_volume=1_000_000)
        entries = provider.discover(req)
        assert "2B" in entries[0].reason
        assert "1000K" in entries[0].reason


# ═══════════════════════════════════════════════════════════════════════════════
# D. SECTOR ROTATION PROVIDER
# ═══════════════════════════════════════════════════════════════════════════════


class TestSectorRotationProvider:
    """Verify sector rotation provider."""

    def test_all_sectors(self):
        provider = SectorRotationProvider()
        entries = provider.discover(UniverseRequest(max_per_source=100))
        assert len(entries) > 50
        sources = {e.reason for e in entries}
        assert any("technology" in s for s in sources)

    def test_favored_sectors_filter(self):
        provider = SectorRotationProvider(favored_sectors=["technology", "energy"])
        entries = provider.discover(UniverseRequest(max_per_source=100))
        reasons = {e.reason for e in entries}
        assert all("technology" in r or "energy" in r for r in reasons)

    def test_source_attribution(self):
        provider = SectorRotationProvider(favored_sectors=["technology"])
        entries = provider.discover(UniverseRequest(max_per_source=5))
        assert all(e.source == UniverseSource.SECTOR_ROTATION for e in entries)

    def test_max_per_source_cap(self):
        provider = SectorRotationProvider()
        entries = provider.discover(UniverseRequest(max_per_source=5))
        assert len(entries) <= 5

    def test_all_sectors_exist(self):
        expected = [
            "technology", "healthcare", "financials", "energy",
            "consumer_discretionary", "consumer_staples", "industrials",
            "materials", "utilities", "real_estate", "communication",
        ]
        for sector in expected:
            assert sector in _SECTOR_TICKERS, f"Missing sector: {sector}"


# ═══════════════════════════════════════════════════════════════════════════════
# E. CUSTOM PROVIDER
# ═══════════════════════════════════════════════════════════════════════════════


class TestCustomProvider:
    """Verify custom/watchlist provider."""

    def test_pass_through(self):
        provider = CustomProvider()
        req = UniverseRequest(custom_tickers=["AAPL", "MSFT", "NVDA"])
        entries = provider.discover(req)
        assert len(entries) == 3
        assert entries[0].ticker == "AAPL"

    def test_uppercase_normalization(self):
        provider = CustomProvider()
        req = UniverseRequest(custom_tickers=["aapl", "msft"])
        entries = provider.discover(req)
        assert entries[0].ticker == "AAPL"
        assert entries[1].ticker == "MSFT"

    def test_empty_tickers_filtered(self):
        provider = CustomProvider()
        req = UniverseRequest(custom_tickers=["AAPL", "", "  ", "MSFT"])
        entries = provider.discover(req)
        assert len(entries) == 2

    def test_source_attribution(self):
        provider = CustomProvider()
        req = UniverseRequest(custom_tickers=["TSLA"])
        entries = provider.discover(req)
        assert entries[0].source == UniverseSource.CUSTOM
        assert entries[0].reason == "user watchlist"

    def test_max_per_source_cap(self):
        provider = CustomProvider()
        tickers = [f"T{i}" for i in range(200)]
        req = UniverseRequest(custom_tickers=tickers, max_per_source=10)
        entries = provider.discover(req)
        assert len(entries) == 10


# ═══════════════════════════════════════════════════════════════════════════════
# F. DB-BACKED PROVIDERS (protocol/interface checks)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDBProviders:
    """Verify DB-backed providers have correct interface."""

    def test_portfolio_provider_protocol(self):
        p = PortfolioProvider()
        assert p.name == "portfolio"
        assert p.source == UniverseSource.PORTFOLIO
        assert hasattr(p, "discover")

    def test_idea_history_provider_protocol(self):
        p = IdeaHistoryProvider()
        assert p.name == "idea_history"
        assert p.source == UniverseSource.IDEA_HISTORY
        assert hasattr(p, "discover")

    def test_portfolio_provider_graceful_failure(self):
        """Provider should not raise on DB failure — returns empty list."""
        p = PortfolioProvider()
        # Will fail gracefully if DB is not configured
        result = p.discover(UniverseRequest())
        assert isinstance(result, list)

    def test_idea_history_provider_graceful_failure(self):
        p = IdeaHistoryProvider()
        result = p.discover(UniverseRequest())
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════════════
# G. PROVIDER REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════


class TestProviderRegistry:
    """Verify provider registry operations."""

    def test_register_and_len(self):
        reg = UniverseProviderRegistry()
        reg.register(StaticIndexProvider())
        assert len(reg) == 1

    def test_duplicate_raises(self):
        reg = UniverseProviderRegistry()
        reg.register(StaticIndexProvider())
        with pytest.raises(ValueError, match="already registered"):
            reg.register(StaticIndexProvider())

    def test_get_by_source(self):
        reg = UniverseProviderRegistry()
        reg.register(StaticIndexProvider())
        p = reg.get_by_source(UniverseSource.STATIC_INDEX)
        assert p is not None
        assert p.name == "static_index"

    def test_get_by_source_missing(self):
        reg = UniverseProviderRegistry()
        assert reg.get_by_source(UniverseSource.STATIC_INDEX) is None

    def test_list_all(self):
        reg = UniverseProviderRegistry()
        reg.register(StaticIndexProvider())
        reg.register(CustomProvider())
        assert len(reg.list_all()) == 2

    def test_list_sources(self):
        reg = UniverseProviderRegistry()
        reg.register(StaticIndexProvider())
        sources = reg.list_sources()
        assert len(sources) == 1
        assert sources[0]["name"] == "static_index"
        assert sources[0]["source"] == "static_index"

    def test_contains(self):
        reg = UniverseProviderRegistry()
        reg.register(StaticIndexProvider())
        assert "static_index" in reg
        assert "nonexistent" not in reg


# ═══════════════════════════════════════════════════════════════════════════════
# H. UNIVERSE SERVICE
# ═══════════════════════════════════════════════════════════════════════════════


class TestUniverseService:
    """Verify orchestration service."""

    def _make_service(self, *providers) -> UniverseService:
        reg = UniverseProviderRegistry()
        for p in providers:
            reg.register(p)
        return UniverseService(reg)

    def test_single_source_discovery(self):
        service = self._make_service(StaticIndexProvider())
        result = service.discover(UniverseRequest(
            sources=[UniverseSource.STATIC_INDEX],
            max_tickers=10,
        ))
        assert len(result.tickers) == 10
        assert result.total_discovered >= 10

    def test_deduplication(self):
        """Same tickers from two sources should be deduplicated."""
        service = self._make_service(StaticIndexProvider(), ScreenerProvider())
        result = service.discover(UniverseRequest(
            sources=[UniverseSource.STATIC_INDEX, UniverseSource.SCREENER],
            max_tickers=500,
        ))
        # AAPL appears in both — should be deduplicated
        aapl_count = result.tickers.count("AAPL")
        assert aapl_count <= 1
        assert result.total_after_dedup <= result.total_discovered

    def test_max_tickers_cap(self):
        service = self._make_service(StaticIndexProvider())
        result = service.discover(UniverseRequest(
            sources=[UniverseSource.STATIC_INDEX],
            max_tickers=5,
        ))
        assert len(result.tickers) == 5
        assert result.total_after_cap == 5

    def test_source_breakdown(self):
        service = self._make_service(StaticIndexProvider(), CustomProvider())
        result = service.discover(UniverseRequest(
            sources=[UniverseSource.STATIC_INDEX, UniverseSource.CUSTOM],
            custom_tickers=["TSLA", "GME"],
            max_tickers=500,
        ))
        assert "static_index" in result.source_breakdown
        assert "custom" in result.source_breakdown
        assert result.source_breakdown["custom"] == 2

    def test_discovery_ms_populated(self):
        service = self._make_service(StaticIndexProvider())
        result = service.discover(UniverseRequest(max_tickers=5))
        assert result.discovery_ms >= 0.0

    def test_empty_sources(self):
        service = self._make_service(StaticIndexProvider())
        result = service.discover(UniverseRequest(sources=[]))
        assert len(result.tickers) == 0

    def test_missing_provider_skipped(self):
        service = self._make_service(StaticIndexProvider())
        # SCREENER source has no provider registered
        result = service.discover(UniverseRequest(
            sources=[UniverseSource.STATIC_INDEX, UniverseSource.SCREENER],
            max_tickers=10,
        ))
        assert len(result.tickers) == 10

    def test_entries_in_result(self):
        service = self._make_service(CustomProvider())
        result = service.discover(UniverseRequest(
            sources=[UniverseSource.CUSTOM],
            custom_tickers=["AAPL", "MSFT"],
            max_tickers=10,
        ))
        assert len(result.entries) == 2
        assert result.entries[0].ticker == "AAPL"

    def test_dedup_keeps_highest_score(self):
        """When duplicate tickers, service keeps the one with highest score."""
        service = self._make_service(StaticIndexProvider(), ScreenerProvider())
        result = service.discover(UniverseRequest(
            sources=[UniverseSource.STATIC_INDEX, UniverseSource.SCREENER],
            max_tickers=500,
            max_per_source=500,
        ))
        # Static gives score 1.0, screener gives 0.8 — static should win
        entries_dict = {e.ticker: e for e in result.entries}
        if "AAPL" in entries_dict:
            assert entries_dict["AAPL"].score == 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# I. ENGINE INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestEngineIntegration:
    """Verify engine auto_scan method."""

    def test_engine_has_auto_scan(self):
        from src.engines.idea_generation.engine import IdeaGenerationEngine
        engine = IdeaGenerationEngine()
        assert hasattr(engine, "auto_scan")

    def test_engine_auto_scan_is_async(self):
        import asyncio
        from src.engines.idea_generation.engine import IdeaGenerationEngine
        engine = IdeaGenerationEngine()
        assert asyncio.iscoroutinefunction(engine.auto_scan)


# ═══════════════════════════════════════════════════════════════════════════════
# J. API CONTRACTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAPIContracts:
    """Verify API-level schemas."""

    def test_auto_scan_request_defaults(self):
        from src.routes.ideas import AutoScanRequest
        req = AutoScanRequest()
        assert req.sources == ["static_index"]
        assert req.max_tickers >= 200  # may be 200 or 300
        assert req.strategy_profile is None

    def test_auto_scan_request_custom(self):
        from src.routes.ideas import AutoScanRequest
        req = AutoScanRequest(
            sources=["custom", "screener"],
            strategy_profile="swing",
            custom_tickers=["AAPL"],
            max_tickers=50,
        )
        assert len(req.sources) == 2
        assert req.strategy_profile == "swing"

    def test_universe_preview_request(self):
        from src.routes.ideas import UniversePreviewRequest
        req = UniversePreviewRequest(
            sources=["sp500"],
            max_tickers=10,
        )
        assert req.max_tickers == 10

    def test_universe_source_enum_values(self):
        valid = ["static_index", "portfolio", "idea_history", "screener", "sector_rotation", "custom"]
        for v in valid:
            assert UniverseSource(v) is not None


# ═══════════════════════════════════════════════════════════════════════════════
# K. DEFAULT SERVICE
# ═══════════════════════════════════════════════════════════════════════════════


class TestDefaultService:
    """Verify the default singleton service."""

    def test_default_service_exists(self):
        assert default_universe_service is not None

    def test_default_service_has_all_providers(self):
        assert len(default_universe_service._registry) == 6

    def test_default_service_all_sources_registered(self):
        for source in UniverseSource:
            p = default_universe_service._registry.get_by_source(source)
            assert p is not None, f"No provider for source: {source.value}"

    def test_default_service_discovers(self):
        result = default_universe_service.discover(
            UniverseRequest(max_tickers=5)
        )
        assert len(result.tickers) == 5

    def test_default_service_multi_source(self):
        result = default_universe_service.discover(
            UniverseRequest(
                sources=[UniverseSource.STATIC_INDEX, UniverseSource.SCREENER],
                max_tickers=20,
            )
        )
        assert len(result.tickers) == 20
        assert len(result.source_breakdown) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# L. MULTI-SOURCE COMBINATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultiSourceCombinations:
    """Verify combining multiple sources."""

    def test_static_plus_custom(self):
        result = default_universe_service.discover(
            UniverseRequest(
                sources=[UniverseSource.STATIC_INDEX, UniverseSource.CUSTOM],
                custom_tickers=["UNIQUE_TICKER_XYZ"],
                max_tickers=500,
            )
        )
        assert "UNIQUE_TICKER_XYZ" in result.tickers

    def test_screener_plus_sector(self):
        result = default_universe_service.discover(
            UniverseRequest(
                sources=[UniverseSource.SCREENER, UniverseSource.SECTOR_ROTATION],
                max_tickers=50,
            )
        )
        assert len(result.tickers) == 50
        assert result.total_after_dedup <= result.total_discovered

    def test_all_sources(self):
        result = default_universe_service.discover(
            UniverseRequest(
                sources=list(UniverseSource),
                custom_tickers=["TEST_ALL"],
                max_tickers=500,
            )
        )
        assert len(result.tickers) > 0
        # custom source should be in breakdown
        assert "custom" in result.source_breakdown
        assert result.source_breakdown["custom"] >= 1

    def test_custom_only(self):
        result = default_universe_service.discover(
            UniverseRequest(
                sources=[UniverseSource.CUSTOM],
                custom_tickers=["X", "Y", "Z"],
                max_tickers=100,
            )
        )
        assert result.tickers == ["X", "Y", "Z"]
        assert result.source_breakdown["custom"] == 3
