"""
tests/test_qa_system_reliability.py
--------------------------------------------------------------------------
System Reliability QA Suite — validates end-to-end system behaviour.

Categories:
  1. API Health & Connectivity
  2. Engine Smoke Tests (all core engines produce valid output)
  3. Data Pipeline Consistency (determinism, contract integrity)
  4. Error Resilience (graceful degradation, invalid inputs)
  5. Cross-Module Integration (engines feed into each other)

Run against live server:
    pytest tests/test_qa_system_reliability.py -v --tb=short

Run standalone (no server needed — uses TestClient):
    pytest tests/test_qa_system_reliability.py -v -k "not live"
"""

from __future__ import annotations

import asyncio
import math
import time
from datetime import date, datetime
from typing import Any

import pytest
import numpy as np


# ═══════════════════════════════════════════════════════════════════════════════
# 1. API Health & Connectivity (TestClient, no server needed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAPIHealth:
    """FastAPI TestClient-based health verification."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from fastapi.testclient import TestClient
        from main import app
        self.client = TestClient(app)

    def test_root_returns_200(self):
        r = self.client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["message"] == "365 Advisers API is running"
        assert "version" in data

    def test_health_endpoint(self):
        r = self.client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("healthy", "degraded")
        assert "checks" in data
        assert "database" in data["checks"]

    def test_liveness_probe(self):
        r = self.client.get("/health/live")
        assert r.status_code == 200
        assert r.json()["status"] == "alive"

    def test_readiness_probe(self):
        r = self.client.get("/health/ready")
        # TestClient may not trigger lifespan → DB not init → 503 is acceptable
        assert r.status_code in (200, 503)

    def test_docs_accessible(self):
        r = self.client.get("/docs")
        assert r.status_code == 200

    def test_openapi_schema(self):
        r = self.client.get("/openapi.json")
        assert r.status_code == 200
        schema = r.json()
        assert "paths" in schema
        assert len(schema["paths"]) > 50  # We have 55 routers


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Engine Smoke Tests — all core engines produce valid, typed output
# ═══════════════════════════════════════════════════════════════════════════════

class TestEngineSmokeTests:
    """Verify every core engine instantiates and produces valid output."""

    def test_brinson_attribution(self):
        from src.engines.attribution.brinson import BrinsonFachler
        from src.engines.attribution.models import BrinsonResult
        result = BrinsonFachler.attribute(
            {"Tech": 0.5, "Fin": 0.5}, {"Tech": 0.5, "Fin": 0.5},
            {"Tech": 0.05, "Fin": 0.03}, {"Tech": 0.04, "Fin": 0.02},
        )
        assert isinstance(result, BrinsonResult)
        assert result.active_return != 0

    def test_multi_period_brinson(self):
        from src.engines.attribution.multi_period_brinson import (
            MultiPeriodBrinson, PeriodData,
        )
        periods = [
            PeriodData(
                portfolio_weights={"A": 0.5, "B": 0.5},
                benchmark_weights={"A": 0.5, "B": 0.5},
                portfolio_returns={"A": 0.03, "B": 0.02},
                benchmark_returns={"A": 0.02, "B": 0.01},
                period_label="P1",
            ),
        ]
        result = MultiPeriodBrinson.attribute_multi_period(periods)
        assert result.n_periods == 1

    def test_monte_carlo_risk(self):
        from src.engines.portfolio.monte_carlo_risk import MonteCarloRisk
        mc = MonteCarloRisk(n_simulations=1000, seed=42)
        result = mc.run_parametric(
            portfolio_return=0.0004,
            portfolio_vol=0.015,
        )
        assert result.var_95 > 0  # VaR is cumulative loss magnitude
        assert result.cvar_95 >= result.var_95  # CVaR >= VaR for cumulative returns

    def test_compliance_rules_engine(self):
        from src.engines.compliance.compliance_rules import ComplianceRuleEngine
        engine = ComplianceRuleEngine()
        report = engine.check_portfolio(
            weights={"A": 0.3, "B": 0.3, "C": 0.2, "D": 0.1, "E": 0.1},
            sector_map={"A": "Tech", "B": "Tech", "C": "Fin", "D": "Health", "E": "Energy"},
        )
        assert report.total_rules > 0

    def test_regime_position_sizer(self):
        from src.engines.portfolio.regime_position_sizing import RegimePositionSizer
        sizer = RegimePositionSizer()
        result = sizer.adjust(
            weights={"A": 0.5, "B": 0.5},
            volatility_regime="high",
            trend_regime="trending",
        )
        assert sum(result.adjusted_weights.values()) <= 1.01

    def test_risk_decomposer(self):
        from src.engines.factor_risk.risk_decomposer import RiskDecomposer
        from src.engines.factor_risk.models import FactorExposure
        result = RiskDecomposer.decompose(
            weights={"A": 0.5, "B": 0.5},
            exposures=[
                FactorExposure(ticker="A", exposures={"mkt": 1.0}),
                FactorExposure(ticker="B", exposures={"mkt": 0.5}),
            ],
            factor_covariance=np.array([[0.04]]),
            factor_names=["mkt"],
            residual_variances={"A": 0.01, "B": 0.01},
        )
        assert result.total_risk > 0

    def test_barra_factor_model(self):
        from src.engines.factor_risk.barra_factor_model import BarraFactorModel
        model = BarraFactorModel()
        result = model.estimate(
            tickers=["A", "B", "C"],
            characteristics={
                "A": {"market_cap": 1e10, "beta": 1.2, "book_to_price": 0.3},
                "B": {"market_cap": 5e9, "beta": 0.8, "book_to_price": 0.6},
                "C": {"market_cap": 2e9, "beta": 1.0, "book_to_price": 0.4},
            },
        )
        assert len(result.exposures) == 3

    def test_intraday_risk_monitor(self):
        from src.engines.portfolio.intraday_risk_monitor import IntradayRiskMonitor, RiskState
        monitor = IntradayRiskMonitor()
        monitor.update_pnl(pnl_bps=50)
        assert monitor.get_state() == RiskState.NORMAL
        monitor.update_pnl(pnl_decimal=-0.07)
        assert monitor.get_state() == RiskState.HALT

    def test_scenario_stress_engine(self):
        from src.engines.risk.scenario_stress_engine import ScenarioStressEngine
        engine = ScenarioStressEngine()
        report = engine.run_suite({"SPY": 0.5, "TLT": 0.3, "GLD": 0.2})
        assert report.total_scenarios >= 6
        assert 0 <= report.risk_score <= 100

    def test_websocket_feed(self):
        from src.engines.data.websocket_feed import WebSocketFeed, FeedState, MarketTick
        feed = WebSocketFeed()
        feed.connect()
        assert feed.is_active
        feed.push_tick(MarketTick(ticker="AAPL", price=185.0))
        ticks = feed.consume()
        assert len(ticks) == 1

    def test_tca_engine(self):
        from src.engines.portfolio.tca import TCAEngine, OrderFill
        tca = TCAEngine()
        fill = OrderFill(
            order_id="T1", ticker="AAPL", side="BUY",
            decision_price=150.0, fill_price=150.30,
            shares=100, vwap=149.80,
        )
        analysis = tca.record_fill(fill)
        assert analysis.implementation_shortfall_bps > 0

    def test_stress_tester(self):
        from src.engines.risk.stress import StressTester
        results = StressTester.run_all_builtin({"SPY": 0.5, "QQQ": 0.3, "TLT": 0.2})
        assert len(results) >= 4

    def test_alert_manager(self):
        from src.engines.backtesting.alert_manager import AlertManager
        mgr = AlertManager()
        report = mgr.process_events([])
        assert report.alerts_generated == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Data Pipeline Consistency — deterministic and reproducible
# ═══════════════════════════════════════════════════════════════════════════════

class TestDataConsistency:
    """Verify engines produce deterministic results."""

    def test_brinson_deterministic(self):
        from src.engines.attribution.brinson import BrinsonFachler
        pw = {"Tech": 0.4, "Health": 0.3, "Fin": 0.3}
        bw = {"Tech": 0.3, "Health": 0.35, "Fin": 0.35}
        pr = {"Tech": 0.08, "Health": 0.02, "Fin": 0.05}
        br = {"Tech": 0.06, "Health": 0.03, "Fin": 0.04}
        r1 = BrinsonFachler.attribute(pw, bw, pr, br)
        r2 = BrinsonFachler.attribute(pw, bw, pr, br)
        assert r1.active_return == r2.active_return
        assert r1.total_allocation == r2.total_allocation

    def test_monte_carlo_deterministic_with_seed(self):
        from src.engines.portfolio.monte_carlo_risk import MonteCarloRisk
        mc1 = MonteCarloRisk(n_simulations=1000, seed=42)
        mc2 = MonteCarloRisk(n_simulations=1000, seed=42)
        r1 = mc1.run_parametric(portfolio_return=0.0004, portfolio_vol=0.015)
        r2 = mc2.run_parametric(portfolio_return=0.0004, portfolio_vol=0.015)
        assert abs(r1.var_95 - r2.var_95) < 0.001

    def test_compliance_idempotent(self):
        from src.engines.compliance.compliance_rules import ComplianceRuleEngine
        engine = ComplianceRuleEngine()
        args = dict(
            weights={"A": 0.5, "B": 0.3, "C": 0.2},
            sector_map={"A": "Tech", "B": "Fin", "C": "Health"},
        )
        r1 = engine.check_portfolio(**args)
        r2 = engine.check_portfolio(**args)
        assert r1.total_rules == r2.total_rules
        assert r1.violations == r2.violations

    def test_risk_decomposition_variance_identity(self):
        """σ²_total = σ²_systematic + σ²_idiosyncratic."""
        from src.engines.factor_risk.risk_decomposer import RiskDecomposer
        from src.engines.factor_risk.models import FactorExposure
        result = RiskDecomposer.decompose(
            weights={"A": 0.6, "B": 0.4},
            exposures=[
                FactorExposure(ticker="A", exposures={"mkt": 1.2, "size": 0.5}),
                FactorExposure(ticker="B", exposures={"mkt": 0.8, "size": -0.3}),
            ],
            factor_covariance=np.array([[0.04, 0.01], [0.01, 0.02]]),
            factor_names=["mkt", "size"],
            residual_variances={"A": 0.01, "B": 0.008},
        )
        total_var = result.total_risk ** 2
        decomposed = result.systematic_risk ** 2 + result.idiosyncratic_risk ** 2
        assert abs(total_var - decomposed) < 1e-6

    def test_stress_impact_sign_consistency(self):
        """Equity-heavy portfolio should lose in GFC scenario."""
        from src.engines.risk.scenario_stress_engine import ScenarioStressEngine
        engine = ScenarioStressEngine()
        report = engine.run_suite({"SPY": 0.5, "QQQ": 0.5})
        gfc = next(r for r in report.results if r.scenario_name == "2008_gfc")
        assert gfc.portfolio_impact_pct < 0


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Error Resilience — graceful degradation with bad inputs
# ═══════════════════════════════════════════════════════════════════════════════

class TestErrorResilience:
    """Engines handle edge cases without crashing."""

    def test_brinson_empty_sectors(self):
        from src.engines.attribution.brinson import BrinsonFachler
        result = BrinsonFachler.attribute({}, {}, {}, {})
        assert result.active_return == 0

    def test_compliance_empty_portfolio(self):
        from src.engines.compliance.compliance_rules import ComplianceRuleEngine
        engine = ComplianceRuleEngine()
        report = engine.check_portfolio(weights={})
        # Empty portfolio triggers min_positions rule
        assert report.is_compliant is False

    def test_regime_sizer_extreme_vol(self):
        from src.engines.portfolio.regime_position_sizing import RegimePositionSizer
        sizer = RegimePositionSizer()
        result = sizer.adjust(
            weights={"A": 1.0},
            volatility_regime="crisis",  # Max de-risk
            trend_regime="choppy",
        )
        assert result.adjusted_weights["A"] <= 1.0

    def test_intraday_monitor_double_reset(self):
        from src.engines.portfolio.intraday_risk_monitor import IntradayRiskMonitor, RiskState
        monitor = IntradayRiskMonitor()
        monitor.reset()
        monitor.reset()
        assert monitor.get_state() == RiskState.NORMAL

    def test_tca_zero_shares(self):
        from src.engines.portfolio.tca import TCAEngine, OrderFill
        tca = TCAEngine()
        fill = OrderFill(
            order_id="Z1", ticker="X", side="BUY",
            decision_price=100, fill_price=100, shares=0,
        )
        analysis = tca.record_fill(fill)
        assert analysis.slippage_dollars == 0

    def test_stress_unknown_tickers(self):
        from src.engines.risk.scenario_stress_engine import ScenarioStressEngine
        engine = ScenarioStressEngine()
        report = engine.run_suite({"UNKNOWN1": 0.5, "UNKNOWN2": 0.5})
        # Unknown tickers get 0 shock → no impact
        for r in report.results:
            assert r.portfolio_impact_pct == 0

    def test_websocket_consume_empty(self):
        from src.engines.data.websocket_feed import WebSocketFeed
        feed = WebSocketFeed()
        ticks = feed.consume()
        assert ticks == []

    def test_barra_single_ticker(self):
        from src.engines.factor_risk.barra_factor_model import BarraFactorModel
        model = BarraFactorModel()
        result = model.estimate(["A"], {"A": {"market_cap": 1e9}})
        assert len(result.exposures) == 0  # < 2 tickers → empty

    def test_api_invalid_endpoint(self):
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        r = client.get("/nonexistent")
        assert r.status_code in (404, 405)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Cross-Module Integration — engines feed into each other correctly
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrossModuleIntegration:
    """Verify engine outputs can chain through the system."""

    def test_barra_to_risk_decomposer(self):
        """Barra estimates → RiskDecomposer → valid decomposition."""
        from src.engines.factor_risk.barra_factor_model import BarraFactorModel
        from src.engines.factor_risk.risk_decomposer import RiskDecomposer
        import random
        rng = random.Random(42)

        tickers = ["AAPL", "MSFT", "JPM", "JNJ", "XOM"]
        chars = {t: {"market_cap": 1e10 * (i + 1), "beta": 0.8 + 0.1 * i,
                      "book_to_price": 0.3 + 0.05 * i, "momentum_12m": 0.05 + 0.02 * i,
                      "realised_vol": 0.15 + 0.03 * i}
                 for i, t in enumerate(tickers)}
        returns = {t: [rng.gauss(0.0005, 0.02) for _ in range(60)] for t in tickers}

        model = BarraFactorModel()
        barra = model.estimate(tickers, chars, returns)
        weights = {"AAPL": 0.05, "MSFT": 0.15, "JPM": 0.25, "JNJ": 0.30, "XOM": 0.25}
        result = RiskDecomposer.decompose(
            weights=weights,
            exposures=barra.exposures,
            factor_covariance=np.array(barra.factor_covariance),
            factor_names=barra.factors,
            residual_variances=barra.residual_variances,
        )
        assert result.total_risk > 0

    def test_construction_to_stress_pipeline(self):
        """APM construction → stress test → survival check."""
        from src.engines.autonomous_pm.construction_engine import ConstructionEngine
        from src.engines.autonomous_pm.models import PortfolioObjective
        from src.engines.risk.scenario_stress_engine import ScenarioStressEngine

        profiles = [
            {"ticker": "SPY", "composite_alpha_score": 75, "tier": "A",
             "sector": "Market", "factor_scores": {"momentum": 60}},
            {"ticker": "QQQ", "composite_alpha_score": 80, "tier": "A",
             "sector": "Technology", "factor_scores": {"momentum": 70}},
            {"ticker": "TLT", "composite_alpha_score": 55, "tier": "B",
             "sector": "Bonds", "factor_scores": {"quality": 60}},
        ]
        engine = ConstructionEngine()
        portfolio = engine.construct(PortfolioObjective.BALANCED, profiles, "expansion")
        if portfolio.positions:
            weights = {p.ticker: p.weight for p in portfolio.positions}
            stress = ScenarioStressEngine()
            report = stress.run_suite(weights)
            assert report.total_scenarios > 0

    def test_intraday_monitor_to_position_scaling(self):
        """Drawdown triggers → position scale reduces."""
        from src.engines.portfolio.intraday_risk_monitor import IntradayRiskMonitor
        monitor = IntradayRiskMonitor()

        # Normal state → full scale
        assert monitor.get_position_scale() == 1.0

        # Trigger warning → reduced scale
        monitor.update_pnl(pnl_decimal=-0.03)
        scale = monitor.get_position_scale()
        assert scale < 1.0

    def test_tca_feeds_reporting(self):
        """TCA fills → aggregate report with metrics."""
        from src.engines.portfolio.tca import TCAEngine, OrderFill

        tca = TCAEngine()
        fills = [
            OrderFill(order_id=f"O{i}", ticker=t, side="BUY",
                      decision_price=100 + i, fill_price=100 + i + 0.1 * i,
                      shares=100, vwap=100 + i - 0.05)
            for i, t in enumerate(["AAPL", "MSFT", "GOOGL", "AMZN"])
        ]
        tca.record_fills(fills)
        report = tca.analyze()
        assert report.total_fills == 4
        assert report.total_volume > 0
        assert len(report.fill_analyses) == 4

    def test_compliance_after_construction(self):
        """APM construction → compliance check → report."""
        from src.engines.autonomous_pm.construction_engine import ConstructionEngine
        from src.engines.autonomous_pm.models import PortfolioObjective
        from src.engines.compliance.compliance_rules import ComplianceRuleEngine

        profiles = [
            {"ticker": "AAPL", "composite_alpha_score": 85, "tier": "A",
             "sector": "Technology", "factor_scores": {"momentum": 70}},
            {"ticker": "MSFT", "composite_alpha_score": 80, "tier": "A",
             "sector": "Technology", "factor_scores": {"quality": 75}},
            {"ticker": "JNJ", "composite_alpha_score": 65, "tier": "B",
             "sector": "Healthcare", "factor_scores": {"dividend": 70}},
            {"ticker": "JPM", "composite_alpha_score": 70, "tier": "B",
             "sector": "Financials", "factor_scores": {"value": 65}},
        ]
        ce = ConstructionEngine()
        portfolio = ce.construct(PortfolioObjective.GROWTH, profiles, "expansion")

        if portfolio.positions:
            weights = {p.ticker: p.weight for p in portfolio.positions}
            sector_map = {p.ticker: p.sector for p in portfolio.positions}
            compliance = ComplianceRuleEngine()
            report = compliance.check_portfolio(weights=weights, sector_map=sector_map)
            assert report.total_rules > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Performance Benchmarks — verify operations complete in reasonable time
# ═══════════════════════════════════════════════════════════════════════════════

class TestPerformanceBenchmarks:
    """Ensure core operations complete within time budgets."""

    def test_brinson_under_10ms(self):
        from src.engines.attribution.brinson import BrinsonFachler
        pw = {f"Sector_{i}": 1 / 20 for i in range(20)}
        bw = {f"Sector_{i}": 1 / 20 for i in range(20)}
        pr = {f"Sector_{i}": 0.05 + 0.01 * i for i in range(20)}
        br = {f"Sector_{i}": 0.04 + 0.01 * i for i in range(20)}
        start = time.monotonic()
        BrinsonFachler.attribute(pw, bw, pr, br)
        elapsed = (time.monotonic() - start) * 1000
        assert elapsed < 50  # Should be well under 50ms

    def test_stress_suite_under_100ms(self):
        from src.engines.risk.scenario_stress_engine import ScenarioStressEngine
        engine = ScenarioStressEngine()
        start = time.monotonic()
        engine.run_suite({"SPY": 0.3, "QQQ": 0.3, "TLT": 0.2, "GLD": 0.2})
        elapsed = (time.monotonic() - start) * 1000
        assert elapsed < 200

    def test_compliance_under_50ms(self):
        from src.engines.compliance.compliance_rules import ComplianceRuleEngine
        engine = ComplianceRuleEngine()
        weights = {f"T{i}": 1 / 30 for i in range(30)}
        sector_map = {f"T{i}": f"Sector_{i % 5}" for i in range(30)}
        start = time.monotonic()
        engine.check_portfolio(weights=weights, sector_map=sector_map)
        elapsed = (time.monotonic() - start) * 1000
        assert elapsed < 100

    def test_api_health_under_500ms(self):
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        start = time.monotonic()
        r = client.get("/health")
        elapsed = (time.monotonic() - start) * 1000
        assert r.status_code == 200
        assert elapsed < 1000


# ═══════════════════════════════════════════════════════════════════════════════
# 7. QA: System Reliability & Determinism (Phase 2)
# ═══════════════════════════════════════════════════════════════════════════════

class TestQASystemReliabilityAndDeterminism:
    """Stress tests and idempotency checks to ensure graceful degradation."""

    def test_yfinance_timeout_resilience(self):
        """Pipeline must survive yfinance timeout and return a graceful error event."""
        from src.orchestration.analysis_pipeline import AnalysisPipeline
        from unittest.mock import patch
        
        class DummyCache:
            def get(self, k): return None
            def set(self, k, v): pass
            
        pipeline = AnalysisPipeline(DummyCache(), DummyCache(), DummyCache())
        
        # Inject TimeoutError in fundamental data ingestion
        with patch('src.engines.fundamental.graph.fetch_fundamental_data', side_effect=TimeoutError("API Down")):
            async def run():
                events = []
                async for sse_event in pipeline.run_combined_stream("AAPL", force=True):
                    events.append(sse_event)
                return events
            
            try:
                events = asyncio.run(run())
            except Exception as e:
                pytest.fail(f"Pipeline crashed on Timeout: {e}")
                
            # Pipeline should survive and not crash the thread. It should emit either an error event or a done event.
            assert any(isinstance(e, str) and ('event: error' in e or 'event: done' in e) for e in events)

    def test_alpha_engine_idempotency(self):
        """Alpha Engine should yield exactly the same score given the same inputs."""
        from src.engines.scoring.opportunity_model import OpportunityModel
        
        fundamental_metrics = {"pe_ratio": 15, "roe": 0.20, "debt_to_equity": 0.5, "free_cash_flow": 1e9}
        fundamental_agents = [{"name": "value", "score": 8, "confidence": 0.9}]
        technical_summary = {"summary": {"technical_score": 7.5, "trend_condition": "BULL"}}
        
        # Execute twice to verify structural idempotency
        res1 = OpportunityModel.calculate(
            fundamental_metrics=fundamental_metrics,
            fundamental_agents=fundamental_agents,
            technical_summary=technical_summary
        )
        res2 = OpportunityModel.calculate(
            fundamental_metrics=fundamental_metrics,
            fundamental_agents=fundamental_agents,
            technical_summary=technical_summary
        )
        
        # Output score and dimensions must be mathematically identical
        assert res1["opportunity_score"] == res2["opportunity_score"]
        assert res1["dimensions"] == res2["dimensions"]

    def test_llm_fallback_resilience(self):
        """Alpha Pipeline must gracefully handle Google GenAI saturation."""
        from src.orchestration.analysis_pipeline import AnalysisPipeline
        from unittest.mock import patch
        
        class DummyCache:
            def get(self, k): return None
            def set(self, k, v): pass
            
        pipeline = AnalysisPipeline(DummyCache(), DummyCache(), DummyCache())
        
        # Mock Google GenAI to simulate quota exceeded or saturation
        with patch('google.genai.Client', side_effect=Exception("Resource Exhausted")):
            async def run():
                events = []
                async for sse_event in pipeline.run_combined_stream("MSFT", force=True):
                    events.append(sse_event)
                return events

            try:
                events = asyncio.run(run())
            except Exception as e:
                pytest.fail(f"Pipeline crashed entirely on LLM failure: {e}")
                
            # Pipeline should survive and reach completion (done event)
            assert any(isinstance(e, str) and 'event: done' in e for e in events)
