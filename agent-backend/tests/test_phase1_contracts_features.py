"""
tests/test_phase1_contracts_features.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for Phase 1: Contracts and Feature Layer.

Tests validate:
  1. All contracts instantiate correctly with defaults
  2. Fundamental feature extraction normalises DATA_INCOMPLETE → None
  3. Technical feature extraction computes derived values
  4. Feature extractors produce valid typed outputs
"""

import pytest

# ─── Contract Instantiation ──────────────────────────────────────────────────

class TestContractInstantiation:
    """Verify all contracts can be constructed with defaults."""

    def test_market_data_bundle(self):
        from src.contracts.market_data import MarketDataBundle
        b = MarketDataBundle(ticker="TEST")
        assert b.ticker == "TEST"
        assert b.price_history.ohlcv == []

    def test_fundamental_feature_set(self):
        from src.contracts.features import FundamentalFeatureSet
        f = FundamentalFeatureSet(ticker="AAPL")
        assert f.ticker == "AAPL"
        assert f.roic is None
        assert f.dividend_yield == 0.0

    def test_technical_feature_set(self):
        from src.contracts.features import TechnicalFeatureSet
        t = TechnicalFeatureSet(ticker="MSFT")
        assert t.ticker == "MSFT"
        assert t.rsi == 50.0
        assert t.ohlcv == []

    def test_fundamental_result(self):
        from src.contracts.analysis import FundamentalResult
        r = FundamentalResult(ticker="GOOG")
        assert r.agent_memos == []
        assert r.committee_verdict.score == 5.0

    def test_technical_result(self):
        from src.contracts.analysis import TechnicalResult
        r = TechnicalResult(ticker="NVDA")
        assert r.technical_score == 5.0
        assert r.volatility_condition == "NORMAL"

    def test_opportunity_score_result(self):
        from src.contracts.scoring import OpportunityScoreResult
        o = OpportunityScoreResult()
        assert o.opportunity_score == 5.0
        assert o.dimensions.business_quality == 5.0
        assert o.factors.competitive_moat == 5.0

    def test_position_allocation(self):
        from src.contracts.sizing import PositionAllocation
        p = PositionAllocation()
        assert p.conviction_level == "Avoid"
        assert p.suggested_allocation == 0.0

    def test_investment_decision(self):
        from src.contracts.decision import InvestmentDecision
        d = InvestmentDecision(ticker="AMZN")
        assert d.investment_position == "Neutral"
        assert d.cio_memo.thesis_summary == ""
        assert d.opportunity.dimensions.valuation == 5.0


# ─── Fundamental Feature Extraction ──────────────────────────────────────────

class TestFundamentalFeatures:
    """Validate fundamental feature extraction logic."""

    def _make_financials(self, **overrides):
        from src.contracts.market_data import (
            FinancialStatements, FinancialRatios,
            ProfitabilityRatios, ValuationRatios,
            LeverageRatios, QualityRatios, CashFlowEntry,
        )
        defaults = {
            "ticker": "TEST",
            "name": "Test Corp",
            "sector": "Technology",
            "industry": "Software",
            "ratios": FinancialRatios(
                profitability=ProfitabilityRatios(
                    roic=0.15, roe=0.20,
                    gross_margin=0.60, ebit_margin=0.25, net_margin=0.18,
                ),
                valuation=ValuationRatios(
                    pe_ratio=25.0, pb_ratio=5.0, ev_ebitda=18.0,
                    fcf_yield=0.04, market_cap=500e9,
                ),
                leverage=LeverageRatios(
                    debt_to_equity=0.5, current_ratio=2.0, quick_ratio=1.8,
                ),
                quality=QualityRatios(
                    revenue_growth_yoy=0.12, earnings_growth_yoy=0.15,
                    dividend_yield=0.01, beta=1.1,
                ),
            ),
            "cashflow_series": [
                CashFlowEntry(year="2023", fcf=10e9, revenue=100e9),
                CashFlowEntry(year="2024", fcf=15e9, revenue=112e9),
            ],
        }
        defaults.update(overrides)
        return FinancialStatements(**defaults)

    def test_basic_extraction(self):
        from src.features.fundamental_features import extract_fundamental_features
        fs = self._make_financials()
        result = extract_fundamental_features(fs)

        assert result.ticker == "TEST"
        assert result.roic == 0.15
        assert result.pe_ratio == 25.0
        assert result.sector == "Technology"
        assert result.market_cap == 500e9

    def test_data_incomplete_becomes_none(self):
        from src.contracts.market_data import (
            FinancialStatements, FinancialRatios,
            ProfitabilityRatios, ValuationRatios,
            LeverageRatios, QualityRatios,
        )
        from src.features.fundamental_features import extract_fundamental_features

        fs = FinancialStatements(
            ticker="BAD",
            ratios=FinancialRatios(
                profitability=ProfitabilityRatios(roic="DATA_INCOMPLETE"),
                valuation=ValuationRatios(pe_ratio="DATA_INCOMPLETE"),
            ),
        )
        result = extract_fundamental_features(fs)
        assert result.roic is None  # was "DATA_INCOMPLETE"
        assert result.pe_ratio is None

    def test_margin_trend_computed(self):
        from src.features.fundamental_features import extract_fundamental_features
        fs = self._make_financials()
        result = extract_fundamental_features(fs)
        # margin_trend = (15/112 - 10/100) ≈ 0.0339 - 0.10 ... let's verify it's a float
        assert result.margin_trend is not None
        assert isinstance(result.margin_trend, float)

    def test_earnings_stability_computed(self):
        from src.features.fundamental_features import extract_fundamental_features
        fs = self._make_financials()
        result = extract_fundamental_features(fs)
        assert result.earnings_stability is not None
        assert 0.0 <= result.earnings_stability <= 10.0


# ─── Technical Feature Extraction ─────────────────────────────────────────────

class TestTechnicalFeatures:
    """Validate technical feature extraction logic."""

    def _make_inputs(self):
        from src.contracts.market_data import (
            PriceHistory, MarketMetrics, RawIndicators, OHLCVBar,
        )
        bars = [
            OHLCVBar(time=f"2024-01-{i+1:02d}", open=150+i, high=152+i,
                     low=149+i, close=151+i, volume=1000000+i*10000)
            for i in range(30)
        ]
        ph = PriceHistory(ticker="AAPL", current_price=180.0, ohlcv=bars)
        mm = MarketMetrics(
            ticker="AAPL",
            exchange="NASDAQ",
            indicators=RawIndicators(
                close=180.0, sma50=175.0, sma200=170.0, ema20=178.0,
                rsi=62.5, stoch_k=72.0, stoch_d=68.0,
                macd=1.5, macd_signal=1.2, macd_hist=0.3,
                bb_upper=185.0, bb_lower=172.0, bb_basis=178.5,
                atr=3.2, volume=1500000, obv=25000000,
            ),
        )
        return ph, mm

    def test_basic_extraction(self):
        from src.features.technical_features import extract_technical_features
        ph, mm = self._make_inputs()
        result = extract_technical_features(ph, mm)

        assert result.ticker == "AAPL"
        assert result.current_price == 180.0
        assert result.sma_50 == 175.0
        assert result.rsi == 62.5
        assert result.atr == 3.2

    def test_volume_avg_computed(self):
        from src.features.technical_features import extract_technical_features
        ph, mm = self._make_inputs()
        result = extract_technical_features(ph, mm)

        assert result.volume_avg_20 > 0
        # Should be average of the last 20 bars' volume
        expected_avg = sum(1000000 + i * 10000 for i in range(10, 30)) / 20
        assert abs(result.volume_avg_20 - expected_avg) < 1.0

    def test_ohlcv_forwarded(self):
        from src.features.technical_features import extract_technical_features
        ph, mm = self._make_inputs()
        result = extract_technical_features(ph, mm)

        assert len(result.ohlcv) == 30
        assert result.ohlcv[0]["time"] == "2024-01-01"

    def test_empty_history(self):
        from src.contracts.market_data import PriceHistory, MarketMetrics
        from src.features.technical_features import extract_technical_features

        ph = PriceHistory(ticker="EMPTY", current_price=0.0)
        mm = MarketMetrics(ticker="EMPTY")
        result = extract_technical_features(ph, mm)

        assert result.volume_avg_20 == 0.0
        assert result.ohlcv == []
        assert result.rsi == 50.0  # default
