"""
tests/test_scenario_stress.py — Tests for ScenarioStressEngine.
"""
from __future__ import annotations
import pytest
from src.engines.risk.scenario_stress_engine import (
    ScenarioStressEngine, EnhancedStressResult, StressSuiteReport,
    ENHANCED_SCENARIOS,
)
from src.engines.risk.models import StressScenario


PORT = {"SPY": 0.30, "QQQ": 0.25, "TLT": 0.15, "GLD": 0.10, "XLF": 0.10, "XLV": 0.10}
SECTORS = {"SPY": "Market", "QQQ": "Tech", "TLT": "Bonds", "GLD": "Commodities",
           "XLF": "Financials", "XLV": "Healthcare"}


class TestScenarioStress:

    def test_suite_runs_all_builtin(self):
        engine = ScenarioStressEngine()
        report = engine.run_suite(PORT, SECTORS)
        assert report.total_scenarios == len(ENHANCED_SCENARIOS)
        assert len(report.results) == report.total_scenarios

    def test_worst_scenario_identified(self):
        engine = ScenarioStressEngine()
        report = engine.run_suite(PORT, SECTORS)
        assert report.worst_scenario != ""
        assert report.max_drawdown_pct > 0

    def test_sector_impacts_present(self):
        engine = ScenarioStressEngine()
        report = engine.run_suite(PORT, SECTORS)
        for r in report.results:
            assert len(r.sector_impacts) > 0

    def test_survival_assessment(self):
        engine = ScenarioStressEngine(max_acceptable_drawdown=0.50)
        report = engine.run_suite(PORT, SECTORS)
        assert report.scenarios_survived >= 1

    def test_risk_score_bounded(self):
        engine = ScenarioStressEngine()
        report = engine.run_suite(PORT, SECTORS)
        assert 0 <= report.risk_score <= 100

    def test_correlation_adjusted_less_severe(self):
        engine = ScenarioStressEngine()
        report = engine.run_suite(PORT, SECTORS)
        for r in report.results:
            if r.portfolio_impact_pct < 0:
                # Diversified portfolio should have less severe adjusted impact
                assert abs(r.correlation_adjusted_impact) <= abs(r.portfolio_impact_pct) + 0.01

    def test_parametric_scenario(self):
        scenario = ScenarioStressEngine.parametric_scenario(
            name="custom_crash", market_shock=-0.25, vol_multiplier=1.5,
        )
        assert scenario.name == "custom_crash"
        assert scenario.shocks["SPY"] == pytest.approx(-0.375)  # -0.25 * 1.0 * 1.5
        assert scenario.shocks["QQQ"] == pytest.approx(-0.4875)  # -0.25 * 1.3 * 1.5

    def test_custom_scenarios(self):
        custom = [StressScenario(
            name="mild_correction",
            description="5% correction",
            shocks={"SPY": -0.05, "QQQ": -0.07},
        )]
        engine = ScenarioStressEngine()
        report = engine.run_suite(PORT, SECTORS, scenarios=custom)
        assert report.total_scenarios == 1

    def test_portfolio_impact_sign(self):
        """GFC scenario should produce negative portfolio impact for equity-heavy port."""
        engine = ScenarioStressEngine()
        report = engine.run_suite({"SPY": 0.50, "QQQ": 0.50})
        gfc = next(r for r in report.results if r.scenario_name == "2008_gfc")
        assert gfc.portfolio_impact_pct < 0

    def test_dollar_impact(self):
        engine = ScenarioStressEngine()
        report = engine.run_suite(PORT, SECTORS, portfolio_value=2_000_000)
        for r in report.results:
            expected = r.portfolio_impact_pct / 100 * 2_000_000
            assert abs(r.portfolio_impact_amount - expected) < 1.0
