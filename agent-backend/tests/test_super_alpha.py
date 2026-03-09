"""
tests/test_super_alpha.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive tests for the Super Alpha Engine:
  - 4 Factor Engines (Value, Momentum, Quality, Size)
  - SuperAlphaEngine orchestrator
  - SuperAlphaAlertEngine
  - Edge cases
"""

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# 1. VALUE FACTOR
# ═══════════════════════════════════════════════════════════════════════════════

class TestValueFactor:
    def setup_method(self):
        from src.engines.super_alpha.factors.value import ValueFactor
        self.engine = ValueFactor()

    def test_cheap_stock_scores_high(self):
        result = self.engine.score({
            "pe_ratio": 8, "ev_to_ebitda": 6, "pb_ratio": 1.0, "fcf_yield": 0.10,
        })
        assert result.factor == "value"
        assert result.score > 65, f"Cheap stock should score high, got {result.score}"

    def test_expensive_stock_scores_low(self):
        result = self.engine.score({
            "pe_ratio": 60, "ev_to_ebitda": 30, "pb_ratio": 10, "fcf_yield": 0.005,
        })
        assert result.score < 40, f"Expensive stock should score low, got {result.score}"

    def test_empty_data_returns_50(self):
        result = self.engine.score({})
        assert result.score == 50.0
        assert result.data_quality == 0.0

    def test_partial_data(self):
        result = self.engine.score({"pe_ratio": 15})
        assert 0 <= result.score <= 100
        assert result.data_quality == 0.25

    def test_score_range(self):
        result = self.engine.score({
            "pe_ratio": 20, "ev_to_ebitda": 14, "pb_ratio": 3.5, "fcf_yield": 0.04,
        })
        assert 0 <= result.score <= 100

    def test_variables_present(self):
        result = self.engine.score({
            "pe_ratio": 15, "ev_to_ebitda": 10, "pb_ratio": 2.0, "fcf_yield": 0.06,
        })
        assert len(result.variables) == 4
        assert result.variables[0].name == "P/E Ratio"

    def test_signals_generated(self):
        result = self.engine.score({
            "pe_ratio": 8, "ev_to_ebitda": 6, "pb_ratio": 1.0, "fcf_yield": 0.10,
        })
        assert len(result.signals) > 0

    def test_negative_pe_ignored(self):
        result = self.engine.score({"pe_ratio": -5})
        # Negative P/E should not contribute
        assert result.variables[0].raw_value is None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. MOMENTUM FACTOR
# ═══════════════════════════════════════════════════════════════════════════════

class TestMomentumFactor:
    def setup_method(self):
        from src.engines.super_alpha.factors.momentum import MomentumFactor
        self.engine = MomentumFactor()

    def test_strong_momentum(self):
        result = self.engine.score({
            "return_3m": 0.20, "return_6m": 0.30, "return_12m": 0.50,
            "price_to_sma200": 1.20,
        })
        assert result.score > 70, f"Strong returns should score high, got {result.score}"

    def test_negative_momentum(self):
        result = self.engine.score({
            "return_3m": -0.15, "return_6m": -0.20, "return_12m": -0.30,
            "price_to_sma200": 0.80,
        })
        assert result.score < 30, f"Negative returns should score low, got {result.score}"

    def test_empty_data(self):
        result = self.engine.score({})
        assert result.score == 50.0

    def test_score_range(self):
        result = self.engine.score({
            "return_3m": 0.05, "return_6m": 0.08, "return_12m": 0.12,
        })
        assert 0 <= result.score <= 100

    def test_reversal_signal(self):
        result = self.engine.score({
            "return_3m": -0.12, "return_12m": 0.15,
        })
        assert any("reversal" in s.lower() for s in result.signals)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. QUALITY FACTOR
# ═══════════════════════════════════════════════════════════════════════════════

class TestQualityFactor:
    def setup_method(self):
        from src.engines.super_alpha.factors.quality import QualityFactor
        self.engine = QualityFactor()

    def test_high_quality(self):
        result = self.engine.score({
            "roic": 0.30, "operating_margin": 0.35,
            "earnings_stability": 0.95, "debt_to_equity": 0.3,
        })
        assert result.score > 70, f"High quality should score high, got {result.score}"

    def test_low_quality(self):
        result = self.engine.score({
            "roic": 0.02, "operating_margin": 0.03,
            "earnings_stability": 0.2, "debt_to_equity": 5.0,
        })
        assert result.score < 35, f"Low quality should score low, got {result.score}"

    def test_empty_data(self):
        result = self.engine.score({})
        assert result.score == 50.0

    def test_stability_clamped(self):
        result = self.engine.score({"earnings_stability": 1.5})
        # Should be clamped to 1.0
        assert 0 <= result.score <= 100

    def test_zero_debt(self):
        result = self.engine.score({"debt_to_equity": 0.0})
        assert 0 <= result.score <= 100

    def test_signals_for_elite_roic(self):
        result = self.engine.score({"roic": 0.30})
        assert any("ROIC" in s for s in result.signals)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SIZE FACTOR
# ═══════════════════════════════════════════════════════════════════════════════

class TestSizeFactor:
    def setup_method(self):
        from src.engines.super_alpha.factors.size import SizeFactor
        self.engine = SizeFactor()

    def test_small_cap(self):
        result = self.engine.score({
            "market_cap": 1e9, "avg_daily_volume_usd": 2e6,
        })
        assert result.score > 55, f"Small cap should have higher size score, got {result.score}"

    def test_mega_cap(self):
        result = self.engine.score({
            "market_cap": 2e12, "avg_daily_volume_usd": 100e6,
        })
        assert result.score < 50, f"Mega cap should have lower size score, got {result.score}"

    def test_empty_data(self):
        result = self.engine.score({})
        assert result.score == 50.0

    def test_classification_signal(self):
        result = self.engine.score({"market_cap": 500e6})
        assert any("Small Cap" in s for s in result.signals)

    def test_liquidity_signal(self):
        result = self.engine.score({"market_cap": 1e9, "avg_daily_volume_usd": 500_000})
        assert any("liquidity" in s.lower() for s in result.signals)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SUPER ALPHA ENGINE ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

class TestSuperAlphaEngine:
    def setup_method(self):
        from src.engines.super_alpha.engine import SuperAlphaEngine
        self.engine = SuperAlphaEngine()

    def _sample_data(self):
        return {
            "pe_ratio": 15, "ev_to_ebitda": 10, "pb_ratio": 2.0, "fcf_yield": 0.06,
            "return_3m": 0.10, "return_6m": 0.15, "return_12m": 0.25,
            "price_to_sma200": 1.10,
            "roic": 0.20, "operating_margin": 0.22,
            "earnings_stability": 0.85, "debt_to_equity": 0.8,
            "market_cap": 50e9, "avg_daily_volume_usd": 15e6,
            "vix_current": 18, "iv_rank": 45, "realized_vol": 15, "iv_current": 20,
            "vix_1yr_avg": 16.5, "vix_1yr_max": 35.0,
            "bullish_pct": 60, "bearish_pct": 25, "message_volume_24h": 500,
            "message_volume_7d": 3000, "news_count": 8,
            "gdp_growth": 2.5, "inflation": 3.2, "unemployment": 3.8,
            "yield_curve_spread": 0.3, "pmi": 52,
            "events": [],
        }

    def test_score_asset_returns_profile(self):
        profile = self.engine.score_asset("AAPL", self._sample_data())
        assert profile.ticker == "AAPL"
        assert 0 <= profile.composite_alpha_score <= 100
        assert profile.tier in ["Alpha Elite", "Strong Alpha", "Moderate Alpha",
                                "Neutral", "Weak", "Avoid"]

    def test_all_factors_scored(self):
        profile = self.engine.score_asset("AAPL", self._sample_data())
        for factor_name in ["value", "momentum", "quality", "size",
                           "volatility", "sentiment", "macro", "event"]:
            fs = getattr(profile, factor_name)
            assert 0 <= fs.score <= 100, f"{factor_name} score out of range"

    def test_rank_universe(self):
        assets = [
            ("AAPL", self._sample_data()),
            ("MSFT", {**self._sample_data(), "pe_ratio": 30, "return_3m": -0.05}),
        ]
        ranking = self.engine.rank_universe(assets)
        assert ranking.universe_size == 2
        assert ranking.rankings[0].rank == 1
        assert ranking.rankings[1].rank == 2

    def test_ranking_sorted_descending(self):
        assets = [("A", self._sample_data()), ("B", self._sample_data())]
        ranking = self.engine.rank_universe(assets)
        scores = [r.composite_alpha_score for r in ranking.rankings]
        assert scores == sorted(scores, reverse=True)

    def test_top_drivers_populated(self):
        profile = self.engine.score_asset("AAPL", self._sample_data())
        assert len(profile.top_drivers) > 0

    def test_empty_data(self):
        profile = self.engine.score_asset("EMPTY", {})
        assert 0 <= profile.composite_alpha_score <= 100

    def test_single_asset_universe(self):
        ranking = self.engine.rank_universe([("ONLY", self._sample_data())])
        assert ranking.universe_size == 1
        assert ranking.rankings[0].rank == 1

    def test_factor_exposures(self):
        profile = self.engine.score_asset("AAPL", self._sample_data())
        exposures = self.engine.get_factor_exposures([profile])
        assert len(exposures) == 1
        assert "Value" in exposures[0].exposures

    def test_convergence_bonus(self):
        """When most factors score high, convergence bonus should apply."""
        data = self._sample_data()
        data.update({
            "pe_ratio": 8, "ev_to_ebitda": 6, "pb_ratio": 1.0, "fcf_yield": 0.10,
            "return_3m": 0.20, "return_6m": 0.30, "return_12m": 0.50,
            "roic": 0.30, "operating_margin": 0.35, "earnings_stability": 0.95,
            "debt_to_equity": 0.3, "bullish_pct": 85, "bearish_pct": 10,
        })
        profile = self.engine.score_asset("BULL", data)
        # With most factors strong, should have some convergence
        assert profile.factor_agreement >= 4


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ALERT ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class TestSuperAlphaAlerts:
    def setup_method(self):
        from src.engines.super_alpha.engine import SuperAlphaEngine
        from src.engines.super_alpha.alerts import SuperAlphaAlertEngine
        self.engine = SuperAlphaEngine()
        self.alert_engine = SuperAlphaAlertEngine()

    def _sample_data(self):
        return {
            "pe_ratio": 15, "ev_to_ebitda": 10, "pb_ratio": 2.0, "fcf_yield": 0.06,
            "return_3m": 0.10, "return_6m": 0.15, "return_12m": 0.25,
            "price_to_sma200": 1.10,
            "roic": 0.20, "operating_margin": 0.22,
            "earnings_stability": 0.85, "debt_to_equity": 0.8,
            "market_cap": 50e9, "avg_daily_volume_usd": 15e6,
            "vix_current": 18, "iv_rank": 45, "realized_vol": 15, "iv_current": 20,
            "vix_1yr_avg": 16.5, "vix_1yr_max": 35.0,
            "bullish_pct": 60, "bearish_pct": 25, "message_volume_24h": 500,
            "message_volume_7d": 3000, "news_count": 8,
            "gdp_growth": 2.5, "inflation": 3.2, "unemployment": 3.8,
            "yield_curve_spread": 0.3, "pmi": 52,
            "events": [],
        }

    def test_evaluate_returns_list(self):
        assets = [("AAPL", self._sample_data()), ("MSFT", self._sample_data())]
        ranking = self.engine.rank_universe(assets)
        alerts = self.alert_engine.evaluate(ranking.rankings)
        assert isinstance(alerts, list)

    def test_alerts_sorted_by_severity(self):
        assets = [("A", self._sample_data()), ("B", self._sample_data())]
        ranking = self.engine.rank_universe(assets)
        alerts = self.alert_engine.evaluate(ranking.rankings)
        sev_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
        for i in range(len(alerts) - 1):
            assert sev_order.get(alerts[i].severity, 4) <= sev_order.get(alerts[i + 1].severity, 4)

    def test_sentiment_shift_alert(self):
        from src.engines.super_alpha.models import CompositeAlphaProfile, FactorScore, FactorName
        current = CompositeAlphaProfile(
            ticker="TEST", composite_alpha_score=60,
            sentiment=FactorScore(factor=FactorName.SENTIMENT, score=80),
        )
        previous = CompositeAlphaProfile(
            ticker="TEST", composite_alpha_score=50,
            sentiment=FactorScore(factor=FactorName.SENTIMENT, score=40),
        )
        current.percentile = 50.0
        alerts = self.alert_engine.evaluate([current], [previous])
        sentiment_alerts = [a for a in alerts if a.alert_type == "sentiment_shift"]
        assert len(sentiment_alerts) > 0

    def test_no_alerts_on_empty(self):
        alerts = self.alert_engine.evaluate([])
        assert len(alerts) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 7. MODEL CONTRACTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestModels:
    def test_factor_score_validation(self):
        from src.engines.super_alpha.models import FactorScore, FactorName
        fs = FactorScore(factor=FactorName.VALUE, score=75.0)
        assert fs.score == 75.0
        assert fs.data_quality == 1.0

    def test_composite_profile_defaults(self):
        from src.engines.super_alpha.models import CompositeAlphaProfile
        p = CompositeAlphaProfile(ticker="TEST")
        assert p.composite_alpha_score == 0.0
        assert p.tier == "Neutral"

    def test_tier_enum(self):
        from src.engines.super_alpha.models import AlphaTier
        assert AlphaTier.ALPHA_ELITE.value == "Alpha Elite"
        assert len(AlphaTier) == 6

    def test_alert_type_enum(self):
        from src.engines.super_alpha.models import AlertType
        assert len(AlertType) == 6
