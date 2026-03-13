"""
tests/test_screener.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive tests for the composable Screener Engine.

Coverage:
  1. ScreenerFilter — operator evaluation, edge cases
  2. FilterProviders — field extraction for fundamental, technical, metadata
  3. FilterRegistry — registration, lookup, field listing
  4. ScreenerEngine — integration with mock data
  5. Presets — availability and structure
"""

import pytest

from src.engines.screener.contracts import (
    ScreenerFilter,
    ScreenerRequest,
    ScreenerMatch,
    ScreenerResult,
    FilterOperator,
)
from src.engines.screener.providers import (
    FilterRegistry,
    FundamentalFilterProvider,
    TechnicalFilterProvider,
    MetadataFilterProvider,
    SCREENER_PRESETS,
)
from src.engines.screener.engine import ScreenerEngine


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _mock_ticker_data(ticker: str = "AAPL", **overrides) -> dict:
    """Build realistic ticker data for testing."""
    base = {
        "ticker": ticker,
        "name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "info": {
            "marketCap": 3_000_000_000_000,
            "currentPrice": 185.0,
            "exchange": "NMS",
            "sector": "Technology",
            "industry": "Consumer Electronics",
        },
        "ratios": {
            "profitability": {
                "gross_margin": 0.45,
                "ebit_margin": 0.30,
                "net_margin": 0.25,
                "roe": 0.35,
                "roic": 0.28,
            },
            "valuation": {
                "pe_ratio": 30.0,
                "pb_ratio": 45.0,
                "ev_ebitda": 25.0,
                "fcf_yield": 0.035,
                "market_cap": 3_000_000_000_000,
            },
            "leverage": {
                "debt_to_equity": 1.5,
                "interest_coverage": 30.0,
                "current_ratio": 1.0,
                "quick_ratio": 0.8,
            },
            "quality": {
                "revenue_growth_yoy": 0.08,
                "earnings_growth_yoy": 0.10,
                "dividend_yield": 0.005,
                "payout_ratio": 0.15,
                "beta": 1.2,
            },
        },
        "indicators": {
            "rsi": 55.0,
            "macd_hist": 1.5,
            "stoch_k": 60.0,
            "atr": 3.5,
            "close": 185.0,
            "sma50": 180.0,
            "sma200": 170.0,
            "bb_upper": 195.0,
            "bb_lower": 175.0,
            "bb_basis": 185.0,
            "obv_trend": "RISING",
            "tv_recommendation": "BUY",
        },
        "exchange": "NASDAQ",
        "tv_summary": {"RECOMMENDATION": "BUY"},
    }
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════════════════════
# Section 1: ScreenerFilter evaluation
# ═══════════════════════════════════════════════════════════════════════════════

class TestScreenerFilter:
    """Test ScreenerFilter.evaluate() for all operators."""

    def test_gt(self):
        f = ScreenerFilter(field="pe_ratio", operator=FilterOperator.GT, value=20.0)
        assert f.evaluate(25.0) is True
        assert f.evaluate(20.0) is False
        assert f.evaluate(15.0) is False

    def test_gte(self):
        f = ScreenerFilter(field="pe_ratio", operator=FilterOperator.GTE, value=20.0)
        assert f.evaluate(25.0) is True
        assert f.evaluate(20.0) is True
        assert f.evaluate(15.0) is False

    def test_lt(self):
        f = ScreenerFilter(field="pe_ratio", operator=FilterOperator.LT, value=20.0)
        assert f.evaluate(15.0) is True
        assert f.evaluate(20.0) is False

    def test_lte(self):
        f = ScreenerFilter(field="pe_ratio", operator=FilterOperator.LTE, value=20.0)
        assert f.evaluate(15.0) is True
        assert f.evaluate(20.0) is True
        assert f.evaluate(25.0) is False

    def test_eq_numeric(self):
        f = ScreenerFilter(field="score", operator=FilterOperator.EQ, value=5.0)
        assert f.evaluate(5.0) is True
        assert f.evaluate(5.0000000001) is True  # within 1e-9 epsilon
        assert f.evaluate(6.0) is False

    def test_eq_string(self):
        f = ScreenerFilter(field="sector", operator=FilterOperator.EQ, value="Technology")
        assert f.evaluate("Technology") is True
        assert f.evaluate("technology") is True  # case insensitive
        assert f.evaluate("Healthcare") is False

    def test_neq(self):
        f = ScreenerFilter(field="sector", operator=FilterOperator.NEQ, value="Technology")
        assert f.evaluate("Healthcare") is True
        assert f.evaluate("Technology") is False

    def test_between(self):
        f = ScreenerFilter(field="rsi", operator=FilterOperator.BETWEEN, value=30.0, value_max=70.0)
        assert f.evaluate(50.0) is True
        assert f.evaluate(30.0) is True
        assert f.evaluate(70.0) is True
        assert f.evaluate(25.0) is False
        assert f.evaluate(75.0) is False

    def test_in_operator(self):
        f = ScreenerFilter(field="sector", operator=FilterOperator.IN, value=["Technology", "Healthcare"])
        assert f.evaluate("Technology") is True
        assert f.evaluate("Healthcare") is True
        assert f.evaluate("Energy") is False

    def test_none_always_fails(self):
        f = ScreenerFilter(field="pe_ratio", operator=FilterOperator.GT, value=20.0)
        assert f.evaluate(None) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Section 2: Filter Providers — field extraction
# ═══════════════════════════════════════════════════════════════════════════════

class TestFundamentalFilterProvider:
    """Test fundamental metric extraction."""

    def setup_method(self):
        self.provider = FundamentalFilterProvider()
        self.data = _mock_ticker_data()

    def test_supported_fields_non_empty(self):
        fields = self.provider.supported_fields()
        assert len(fields) >= 15

    def test_extract_pe_ratio(self):
        assert self.provider.extract(self.data, "pe_ratio") == 30.0

    def test_extract_roic(self):
        assert self.provider.extract(self.data, "roic") == 0.28

    def test_extract_debt_to_equity(self):
        assert self.provider.extract(self.data, "debt_to_equity") == 1.5

    def test_extract_beta(self):
        assert self.provider.extract(self.data, "beta") == 1.2

    def test_extract_revenue_growth(self):
        assert self.provider.extract(self.data, "revenue_growth") == 0.08

    def test_extract_missing_returns_none(self):
        assert self.provider.extract({}, "pe_ratio") is None

    def test_data_incomplete_returns_none(self):
        data = _mock_ticker_data()
        data["ratios"]["valuation"]["pe_ratio"] = "DATA_INCOMPLETE"
        assert self.provider.extract(data, "pe_ratio") is None

    def test_unknown_field_returns_none(self):
        assert self.provider.extract(self.data, "nonexistent_field") is None


class TestTechnicalFilterProvider:
    """Test technical indicator extraction."""

    def setup_method(self):
        self.provider = TechnicalFilterProvider()
        self.data = _mock_ticker_data()

    def test_extract_rsi(self):
        assert self.provider.extract(self.data, "rsi") == 55.0

    def test_extract_macd_hist(self):
        assert self.provider.extract(self.data, "macd_hist") == 1.5

    def test_extract_atr_pct(self):
        val = self.provider.extract(self.data, "atr_pct")
        assert val is not None
        assert abs(val - (3.5 / 185.0 * 100)) < 0.01

    def test_extract_sma50_distance(self):
        val = self.provider.extract(self.data, "sma50_distance")
        assert val is not None
        assert abs(val - ((185 - 180) / 180 * 100)) < 0.01

    def test_extract_tv_recommendation(self):
        assert self.provider.extract(self.data, "tv_recommendation") == "BUY"


class TestMetadataFilterProvider:
    """Test metadata extraction."""

    def setup_method(self):
        self.provider = MetadataFilterProvider()
        self.data = _mock_ticker_data()

    def test_extract_market_cap(self):
        assert self.provider.extract(self.data, "market_cap") == 3_000_000_000_000

    def test_extract_sector(self):
        assert self.provider.extract(self.data, "sector") == "Technology"

    def test_extract_industry(self):
        assert self.provider.extract(self.data, "industry") == "Consumer Electronics"


# ═══════════════════════════════════════════════════════════════════════════════
# Section 3: Filter Registry
# ═══════════════════════════════════════════════════════════════════════════════

class TestFilterRegistry:
    """Test FilterRegistry CRUD operations."""

    def test_register_provider(self):
        reg = FilterRegistry()
        reg.register(FundamentalFilterProvider())
        assert "fundamental" in reg

    def test_duplicate_registration_raises(self):
        reg = FilterRegistry()
        reg.register(FundamentalFilterProvider())
        with pytest.raises(ValueError, match="already registered"):
            reg.register(FundamentalFilterProvider())

    def test_all_fields_aggregates(self):
        reg = FilterRegistry()
        reg.register(FundamentalFilterProvider())
        reg.register(TechnicalFilterProvider())
        reg.register(MetadataFilterProvider())
        fields = reg.all_fields()
        assert len(fields) >= 25

    def test_extract_field_dispatches(self):
        reg = FilterRegistry()
        reg.register(FundamentalFilterProvider())
        data = _mock_ticker_data()
        assert reg.extract_field(data, "pe_ratio") == 30.0

    def test_extract_unknown_field_returns_none(self):
        reg = FilterRegistry()
        assert reg.extract_field({}, "nonexistent") is None


# ═══════════════════════════════════════════════════════════════════════════════
# Section 4: ScreenerEngine (unit tests with mock data)
# ═══════════════════════════════════════════════════════════════════════════════

class TestScreenerEngine:
    """Test ScreenerEngine internal logic."""

    def test_default_creates_engine(self):
        engine = ScreenerEngine.default()
        assert len(engine.registry) == 3

    def test_available_fields(self):
        engine = ScreenerEngine.default()
        fields = engine.available_fields()
        assert len(fields) >= 25
        field_names = {f["field"] for f in fields}
        assert "pe_ratio" in field_names
        assert "rsi" in field_names
        assert "market_cap" in field_names

    def test_presets_available(self):
        engine = ScreenerEngine.default()
        presets = engine.get_presets()
        assert "value" in presets
        assert "growth" in presets
        assert "momentum" in presets
        assert "quality" in presets
        assert "dividend" in presets

    def test_preset_has_filters(self):
        engine = ScreenerEngine.default()
        for name, cfg in engine.get_presets().items():
            assert "label" in cfg
            assert "description" in cfg
            assert "filters" in cfg
            assert len(cfg["filters"]) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# Section 5: Contracts validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestContracts:
    """Test Pydantic model validation."""

    def test_screener_request_defaults(self):
        req = ScreenerRequest()
        assert req.universe == "sp500"
        assert req.limit == 50
        assert req.sort_desc is True
        assert req.filters == []

    def test_screener_request_with_preset(self):
        req = ScreenerRequest(preset="value")
        assert req.preset == "value"

    def test_screener_match_serialization(self):
        match = ScreenerMatch(
            ticker="AAPL",
            name="Apple",
            field_values={"pe_ratio": 30.0},
            filters_passed=2,
            filters_total=2,
        )
        d = match.model_dump()
        assert d["ticker"] == "AAPL"
        assert d["field_values"]["pe_ratio"] == 30.0

    def test_screener_result_model(self):
        result = ScreenerResult(
            matches=[],
            total_scanned=100,
            total_passed=5,
            filters_applied=3,
            universe="sp500",
        )
        d = result.model_dump()
        assert d["total_scanned"] == 100
        assert d["filters_applied"] == 3

    def test_filter_operator_enum(self):
        assert FilterOperator.GT.value == "gt"
        assert FilterOperator.BETWEEN.value == "between"
        assert FilterOperator.IN.value == "in"
