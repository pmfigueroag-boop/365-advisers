"""
tests/test_investment_brain.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive test suite for the Investment Brain module.

Covers: Models, Regime Detector, Opportunity Detector, Portfolio Advisor,
        Risk Detector, Insights Engine, InvestmentBrain facade, Alert gen.
"""

from __future__ import annotations

import pytest

# ── Models ───────────────────────────────────────────────────────────────────

from src.engines.investment_brain.models import (
    BrainAlert,
    BrainAlertType,
    DetectedOpportunity,
    InsightCategory,
    InvestmentBrainDashboard,
    InvestmentInsight,
    MarketRegime,
    OpportunityType,
    PortfolioStyle,
    PortfolioSuggestion,
    RegimeClassification,
    RegimeFactor,
    RiskAlert,
    RiskAlertSeverity,
    RiskAlertType,
    SuggestedPosition,
)


class TestModels:
    """Validate Pydantic model instantiation and defaults."""

    def test_market_regime_enum_values(self):
        assert MarketRegime.EXPANSION.value == "expansion"
        assert MarketRegime.HIGH_VOLATILITY.value == "high_volatility"
        assert len(MarketRegime) == 6

    def test_regime_classification_defaults(self):
        rc = RegimeClassification()
        assert rc.regime == MarketRegime.EXPANSION
        assert rc.confidence == 0.5
        assert rc.regime_changed is False
        assert rc.probabilities == {}

    def test_detected_opportunity_creation(self):
        opp = DetectedOpportunity(
            ticker="AAPL",
            opportunity_type=OpportunityType.UNDERVALUED,
            alpha_score=75.5,
            confidence=0.8,
            signals=["Value factor: 80"],
            justification="Deep value play.",
        )
        assert opp.ticker == "AAPL"
        assert opp.alpha_score == 75.5

    def test_portfolio_suggestion_creation(self):
        ps = PortfolioSuggestion(
            style=PortfolioStyle.GROWTH,
            positions=[SuggestedPosition(ticker="NVDA", weight=0.25)],
            rationale="Growth-oriented.",
        )
        assert ps.style == PortfolioStyle.GROWTH
        assert len(ps.positions) == 1
        assert ps.positions[0].weight == 0.25

    def test_risk_alert_creation(self):
        ra = RiskAlert(
            alert_type=RiskAlertType.SYSTEMIC_RISK,
            severity=RiskAlertSeverity.CRITICAL,
            title="VIX Spike",
            description="VIX above 40.",
        )
        assert ra.severity == RiskAlertSeverity.CRITICAL

    def test_investment_insight_creation(self):
        ins = InvestmentInsight(
            what_happened="GDP increased.",
            why_it_happened="Strong consumer spending.",
            what_it_means="Bullish for equities.",
        )
        assert ins.category == InsightCategory.REGIME  # default

    def test_brain_dashboard_creation(self):
        dashboard = InvestmentBrainDashboard(
            regime=RegimeClassification(),
            opportunities=[],
            portfolios=[],
            risk_alerts=[],
            insights=[],
        )
        assert dashboard.version == "1.0.0"
        assert dashboard.asset_count == 0


# ── Regime Detector ──────────────────────────────────────────────────────────

from src.engines.investment_brain.regime_detector import RegimeDetector


class TestRegimeDetector:
    def setup_method(self):
        self.detector = RegimeDetector()

    def test_expansion_regime(self):
        result = self.detector.detect(
            macro_data={"gdp_growth": 3.5, "inflation": 2.0, "unemployment": 3.5, "pmi": 58},
            vol_data={"vix_current": 14},
        )
        assert result.regime == MarketRegime.EXPANSION
        assert result.confidence > 0.3
        assert len(result.contributing_factors) > 0

    def test_recession_regime(self):
        result = self.detector.detect(
            macro_data={"gdp_growth": -1.0, "unemployment": 8.0, "pmi": 42, "yield_curve_spread": -1.0},
            vol_data={"vix_current": 35},
        )
        assert result.regime == MarketRegime.RECESSION
        assert result.confidence > 0.2

    def test_high_volatility_regime(self):
        result = self.detector.detect(
            macro_data={},
            vol_data={"vix_current": 45, "iv_rank": 90},
        )
        assert result.regime == MarketRegime.HIGH_VOLATILITY

    def test_liquidity_expansion_regime(self):
        result = self.detector.detect(
            macro_data={"interest_rate": 1.0, "inflation": 1.5, "m2_growth": 12.0},
        )
        assert result.regime == MarketRegime.LIQUIDITY_EXPANSION

    def test_empty_data_returns_default(self):
        result = self.detector.detect()
        assert isinstance(result, RegimeClassification)

    def test_probabilities_sum_to_one(self):
        result = self.detector.detect(
            macro_data={"gdp_growth": 2.0, "inflation": 3.0},
        )
        total = sum(result.probabilities.values())
        assert abs(total - 1.0) < 0.01


# ── Opportunity Detector ─────────────────────────────────────────────────────

from src.engines.investment_brain.opportunity_detector import OpportunityDetector


class TestOpportunityDetector:
    def setup_method(self):
        self.detector = OpportunityDetector()

    def test_detects_undervalued(self):
        profiles = [{"ticker": "JPM", "composite_alpha_score": 70, "sector": "Financials", "factor_scores": {"value": 75, "momentum": 30}, "tier": "alpha"}]
        result = self.detector.detect(alpha_profiles=profiles)
        types = [o.opportunity_type for o in result]
        assert OpportunityType.UNDERVALUED in types

    def test_detects_momentum_breakout(self):
        profiles = [{"ticker": "NVDA", "composite_alpha_score": 80, "sector": "Technology", "factor_scores": {"momentum": 85, "value": 40}, "tier": "strong_alpha"}]
        result = self.detector.detect(alpha_profiles=profiles)
        types = [o.opportunity_type for o in result]
        assert OpportunityType.MOMENTUM_BREAKOUT in types

    def test_detects_sentiment_driven(self):
        profiles = [{"ticker": "TSLA", "composite_alpha_score": 60, "sector": "Auto", "factor_scores": {}, "tier": "alpha"}]
        sentiments = [{"ticker": "TSLA", "composite_score": 65, "polarity": 0.6, "momentum_of_attention": 1.5}]
        result = self.detector.detect(alpha_profiles=profiles, sentiment_scores=sentiments)
        types = [o.opportunity_type for o in result]
        assert OpportunityType.SENTIMENT_DRIVEN in types

    def test_detects_event_catalyst(self):
        profiles = [{"ticker": "META", "composite_alpha_score": 55, "sector": "Technology", "factor_scores": {}, "tier": "alpha"}]
        events = [{"ticker": "META", "composite_score": 50, "bullish_events": 3}]
        result = self.detector.detect(alpha_profiles=profiles, event_scores=events)
        types = [o.opportunity_type for o in result]
        assert OpportunityType.EVENT_CATALYST in types

    def test_empty_input_returns_empty(self):
        result = self.detector.detect()
        assert result == []

    def test_max_20_opportunities(self):
        profiles = [
            {"ticker": f"T{i}", "composite_alpha_score": 80, "sector": "Technology", "factor_scores": {"value": 80, "momentum": 80}, "tier": "alpha"}
            for i in range(30)
        ]
        result = self.detector.detect(alpha_profiles=profiles)
        assert len(result) <= 20


# ── Portfolio Advisor ────────────────────────────────────────────────────────

from src.engines.investment_brain.portfolio_advisor import PortfolioAdvisor


class TestPortfolioAdvisor:
    def setup_method(self):
        self.advisor = PortfolioAdvisor()

    def test_generates_five_portfolios(self):
        opportunities = [
            DetectedOpportunity(ticker="AAPL", opportunity_type=OpportunityType.MOMENTUM_BREAKOUT, alpha_score=80, confidence=0.8),
            DetectedOpportunity(ticker="JPM", opportunity_type=OpportunityType.UNDERVALUED, alpha_score=70, confidence=0.7),
            DetectedOpportunity(ticker="TSLA", opportunity_type=OpportunityType.SENTIMENT_DRIVEN, alpha_score=65, confidence=0.6),
        ]
        result = self.advisor.advise(opportunities=opportunities)
        assert len(result) == 5
        styles = {p.style for p in result}
        assert styles == {PortfolioStyle.GROWTH, PortfolioStyle.VALUE, PortfolioStyle.INCOME, PortfolioStyle.DEFENSIVE, PortfolioStyle.OPPORTUNISTIC}

    def test_weights_sum_to_one(self):
        opportunities = [
            DetectedOpportunity(ticker=f"T{i}", opportunity_type=OpportunityType.MACRO_ALIGNED, alpha_score=70, confidence=0.7)
            for i in range(5)
        ]
        result = self.advisor.advise(opportunities=opportunities)
        for portfolio in result:
            if portfolio.positions:
                total = sum(p.weight for p in portfolio.positions)
                assert abs(total - 1.0) < 0.02, f"{portfolio.style}: weights sum to {total}"

    def test_empty_opportunities_returns_empty_positions(self):
        result = self.advisor.advise(opportunities=[])
        assert all(len(p.positions) == 0 for p in result)

    def test_regime_suitability_populated(self):
        result = self.advisor.advise(
            regime=RegimeClassification(regime=MarketRegime.RECESSION),
        )
        for portfolio in result:
            assert portfolio.regime_suitability != ""


# ── Risk Detector ────────────────────────────────────────────────────────────

from src.engines.investment_brain.risk_detector import RiskDetector


class TestRiskDetector:
    def setup_method(self):
        self.detector = RiskDetector()

    def test_extreme_vix_triggers_systemic(self):
        result = self.detector.detect(vol_data={"vix_current": 40})
        types = [a.alert_type for a in result]
        assert RiskAlertType.SYSTEMIC_RISK in types
        assert any(a.severity == RiskAlertSeverity.CRITICAL for a in result)

    def test_stagflation_detected(self):
        result = self.detector.detect(macro_data={"gdp_growth": 0.5, "inflation": 6.0})
        titles = [a.title for a in result]
        assert any("Stagflation" in t for t in titles)

    def test_yield_curve_inversion(self):
        result = self.detector.detect(macro_data={"yield_curve_spread": -1.0})
        types = [a.alert_type for a in result]
        assert RiskAlertType.SYSTEMIC_RISK in types

    def test_sector_overheating(self):
        profiles = [
            {"ticker": f"T{i}", "composite_alpha_score": 80, "sector": "Technology"}
            for i in range(5)
        ]
        result = self.detector.detect(alpha_profiles=profiles)
        types = [a.alert_type for a in result]
        assert RiskAlertType.SECTOR_OVERHEATING in types

    def test_no_data_returns_empty(self):
        result = self.detector.detect()
        assert result == []

    def test_alerts_sorted_by_severity(self):
        result = self.detector.detect(
            vol_data={"vix_current": 40},
            macro_data={"gdp_growth": 0.3, "inflation": 7.0},
        )
        if len(result) >= 2:
            severity_order = {"critical": 0, "high": 1, "moderate": 2, "low": 3}
            for i in range(len(result) - 1):
                assert severity_order.get(result[i].severity.value, 9) <= severity_order.get(result[i + 1].severity.value, 9)


# ── Insights Engine ──────────────────────────────────────────────────────────

from src.engines.investment_brain.insights_engine import InsightsEngine


class TestInsightsEngine:
    def setup_method(self):
        self.engine = InsightsEngine()

    def test_regime_insight_generated(self):
        regime = RegimeClassification(regime=MarketRegime.EXPANSION, confidence=0.8)
        result = self.engine.generate(regime=regime)
        assert len(result) > 0
        assert result[0].category == InsightCategory.REGIME
        assert "expansion" in result[0].what_happened.lower()

    def test_all_three_fields_populated(self):
        regime = RegimeClassification()
        result = self.engine.generate(regime=regime)
        for insight in result:
            assert insight.what_happened
            assert insight.why_it_happened
            assert insight.what_it_means

    def test_macro_goldilocks_insight(self):
        result = self.engine.generate(macro_data={"gdp_growth": 3.0, "inflation": 2.0, "interest_rate": 3.5})
        categories = [i.category for i in result]
        assert InsightCategory.MACRO in categories

    def test_sentiment_insight(self):
        sentiments = [
            {"ticker": "AAPL", "composite_score": 55},
            {"ticker": "MSFT", "composite_score": 60},
        ]
        result = self.engine.generate(sentiment_scores=sentiments)
        categories = [i.category for i in result]
        assert InsightCategory.SENTIMENT in categories

    def test_empty_input_returns_empty(self):
        result = self.engine.generate()
        assert result == []


# ── InvestmentBrain Facade ───────────────────────────────────────────────────

from src.engines.investment_brain.engine import InvestmentBrain


class TestInvestmentBrain:
    def test_full_pipeline_produces_dashboard(self):
        brain = InvestmentBrain()
        dashboard = brain.analyze(
            macro_data={"gdp_growth": 2.5, "inflation": 2.8, "unemployment": 4.0, "pmi": 55},
            vol_data={"vix_current": 18},
        )
        assert isinstance(dashboard, InvestmentBrainDashboard)
        assert dashboard.regime.regime in list(MarketRegime)
        assert isinstance(dashboard.portfolios, list)
        assert isinstance(dashboard.insights, list)

    def test_pipeline_with_universe(self):
        brain = InvestmentBrain()
        universe = [
            ("AAPL", {"price": 180, "volume": 80e6, "pe_ratio": 28, "roe": 0.35, "revenue_growth": 0.08}),
            ("MSFT", {"price": 380, "volume": 25e6, "pe_ratio": 32, "roe": 0.40, "revenue_growth": 0.12}),
        ]
        dashboard = brain.analyze(
            macro_data={"gdp_growth": 2.0},
            universe_data=universe,
        )
        assert isinstance(dashboard, InvestmentBrainDashboard)
        assert dashboard.asset_count == 2

    def test_empty_data_does_not_crash(self):
        brain = InvestmentBrain()
        dashboard = brain.analyze()
        assert isinstance(dashboard, InvestmentBrainDashboard)


# ── Alert Generation ─────────────────────────────────────────────────────────

class TestAlertGeneration:
    def test_regime_change_alert(self):
        prev = InvestmentBrainDashboard(
            regime=RegimeClassification(regime=MarketRegime.EXPANSION),
        )
        current = InvestmentBrainDashboard(
            regime=RegimeClassification(regime=MarketRegime.RECESSION),
        )
        alerts = InvestmentBrain.generate_alerts(prev, current)
        types = [a.alert_type for a in alerts]
        assert BrainAlertType.REGIME_CHANGE in types

    def test_no_alerts_on_first_run(self):
        current = InvestmentBrainDashboard(regime=RegimeClassification())
        alerts = InvestmentBrain.generate_alerts(None, current)
        assert alerts == []

    def test_new_opportunity_alert(self):
        prev = InvestmentBrainDashboard(
            regime=RegimeClassification(),
            opportunities=[DetectedOpportunity(ticker="AAPL", opportunity_type=OpportunityType.UNDERVALUED, alpha_score=70, confidence=0.7)],
        )
        current = InvestmentBrainDashboard(
            regime=RegimeClassification(),
            opportunities=[
                DetectedOpportunity(ticker="AAPL", opportunity_type=OpportunityType.UNDERVALUED, alpha_score=70, confidence=0.7),
                DetectedOpportunity(ticker="NVDA", opportunity_type=OpportunityType.MOMENTUM_BREAKOUT, alpha_score=85, confidence=0.8),
            ],
        )
        alerts = InvestmentBrain.generate_alerts(prev, current)
        types = [a.alert_type for a in alerts]
        assert BrainAlertType.NEW_OPPORTUNITY in types

    def test_no_alerts_when_identical(self):
        dashboard = InvestmentBrainDashboard(regime=RegimeClassification())
        alerts = InvestmentBrain.generate_alerts(dashboard, dashboard)
        assert len(alerts) == 0
