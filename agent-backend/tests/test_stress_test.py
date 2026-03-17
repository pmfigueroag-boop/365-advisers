"""
tests/test_stress_test.py
--------------------------------------------------------------------------
Tests for StressTestEngine.
"""

from __future__ import annotations

import pytest

from src.engines.portfolio.stress_test import (
    StressTestEngine,
    StressTestReport,
    ScenarioShock,
    SCENARIOS,
)


class TestStressTestEngine:

    def test_all_scenarios_run(self):
        """Default: runs all 5 predefined scenarios."""
        engine = StressTestEngine()
        report = engine.run(weights={"AAPL": 0.5, "MSFT": 0.5})

        assert report.total_scenarios == 5
        assert report.worst_case_scenario != ""
        assert report.worst_case_loss < 0

    def test_specific_scenarios(self):
        """Run only selected scenarios."""
        engine = StressTestEngine()
        report = engine.run(
            weights={"AAPL": 0.5, "MSFT": 0.5},
            scenarios=["covid", "gfc_2008"],
        )

        assert report.total_scenarios == 2
        names = {r.scenario.name for r in report.scenario_results}
        assert "COVID Crash" in names
        assert "2008 Global Financial Crisis" in names

    def test_covid_impact_significant(self):
        """COVID scenario should produce ~-34% loss for beta=1 portfolio."""
        engine = StressTestEngine()
        report = engine.run(
            weights={"AAPL": 0.5, "MSFT": 0.5},
            scenarios=["covid"],
        )

        result = report.scenario_results[0]
        assert result.portfolio_impact < -0.30
        assert result.portfolio_loss_pct < -30

    def test_beta_adjusts_impact(self):
        """Higher beta → larger loss."""
        low_beta = StressTestEngine(betas={"AAPL": 0.5, "MSFT": 0.5})
        high_beta = StressTestEngine(betas={"AAPL": 1.5, "MSFT": 1.5})

        r_low = low_beta.run(
            weights={"AAPL": 0.5, "MSFT": 0.5},
            scenarios=["covid"],
        )
        r_high = high_beta.run(
            weights={"AAPL": 0.5, "MSFT": 0.5},
            scenarios=["covid"],
        )

        assert r_high.worst_case_loss < r_low.worst_case_loss

    def test_custom_scenario(self):
        """Custom scenario works."""
        engine = StressTestEngine()
        custom = ScenarioShock(
            name="Custom Crash",
            market_return=-0.50,
            duration_days=30,
            factor_shocks={"equity": -0.50},
        )
        report = engine.run(
            weights={"AAPL": 1.0},
            custom_scenarios=[custom],
        )

        assert report.total_scenarios == 1
        assert report.scenario_results[0].portfolio_impact == pytest.approx(-0.50, abs=0.01)

    def test_position_impacts_sorted(self):
        """Position impacts should be sorted by loss (worst first)."""
        engine = StressTestEngine(betas={"AAPL": 1.5, "MSFT": 0.8})
        report = engine.run(
            weights={"AAPL": 0.5, "MSFT": 0.5},
            scenarios=["covid"],
        )

        impacts = report.scenario_results[0].position_impacts
        assert len(impacts) == 2
        # First should be worst (AAPL with higher beta)
        assert impacts[0].estimated_loss <= impacts[1].estimated_loss

    def test_empty_weights(self):
        """Empty portfolio → empty report."""
        engine = StressTestEngine()
        report = engine.run(weights={})
        assert report.total_scenarios == 0

    def test_list_scenarios(self):
        """list_scenarios returns all predefined."""
        scenarios = StressTestEngine.list_scenarios()
        assert "covid" in scenarios
        assert "gfc_2008" in scenarios
        assert len(scenarios) == 5

    def test_worst_case_is_gfc(self):
        """GFC is typically worst scenario."""
        engine = StressTestEngine()
        report = engine.run(weights={"AAPL": 0.5, "MSFT": 0.5})
        assert report.worst_case_scenario == "2008 Global Financial Crisis"
