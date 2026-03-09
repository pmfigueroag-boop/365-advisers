"""tests/test_risk.py — VaR/CVaR Risk Engine tests."""
import numpy as np
import pytest
from src.engines.risk.models import VaRMethod, StressScenario
from src.engines.risk.var import VaRCalculator
from src.engines.risk.cvar import CVaRCalculator
from src.engines.risk.stress import StressTester, BUILTIN_SCENARIOS
from src.engines.risk.engine import RiskEngine

def _daily_returns(n=252, seed=42):
    np.random.seed(seed)
    return (np.random.randn(n) * 0.01 + 0.0003).tolist()

class TestVaR:
    def test_historical_var(self):
        r = VaRCalculator.historical(_daily_returns(), 0.95)
        assert r.var_pct > 0
        assert r.var_amount > 0
        assert r.method == VaRMethod.HISTORICAL

    def test_parametric_var(self):
        ret = _daily_returns()
        r = VaRCalculator.parametric(np.mean(ret), np.std(ret), 0.95)
        assert r.var_pct > 0

    def test_monte_carlo_var(self):
        r = VaRCalculator.monte_carlo(_daily_returns(), 0.95, n_sims=5000)
        assert r.var_pct > 0
        assert r.method == VaRMethod.MONTE_CARLO

    def test_higher_confidence_higher_var(self):
        ret = _daily_returns()
        var_95 = VaRCalculator.historical(ret, 0.95)
        var_99 = VaRCalculator.historical(ret, 0.99)
        assert var_99.var_pct >= var_95.var_pct

    def test_longer_horizon_higher_var(self):
        ret = _daily_returns()
        var_1d = VaRCalculator.historical(ret, 0.95, horizon_days=1)
        var_10d = VaRCalculator.historical(ret, 0.95, horizon_days=10)
        assert var_10d.var_pct > var_1d.var_pct

class TestCVaR:
    def test_historical_cvar(self):
        r = CVaRCalculator.historical(_daily_returns(), 0.95)
        assert r.cvar_pct > 0
        assert r.cvar_amount >= r.var_amount  # CVaR >= VaR

    def test_parametric_cvar(self):
        ret = _daily_returns()
        r = CVaRCalculator.parametric(np.mean(ret), np.std(ret), 0.95)
        assert r.cvar_pct > 0

class TestStressTester:
    def test_builtin_scenarios(self):
        assert len(BUILTIN_SCENARIOS) == 4

    def test_apply_scenario(self):
        weights = {"SPY": 0.6, "TLT": 0.3, "GLD": 0.1}
        r = StressTester.apply_scenario(weights, BUILTIN_SCENARIOS[0])
        assert r.portfolio_impact_pct < 0  # 2008 crisis → negative impact

    def test_all_builtin(self):
        weights = {"SPY": 0.7, "QQQ": 0.3}
        results = StressTester.run_all_builtin(weights)
        assert len(results) == 4
        assert all(r.portfolio_impact_pct < 0 for r in results)  # all negative

    def test_custom_scenario(self):
        s = StressTester.custom_scenario("black_swan", {"SPY": -0.50})
        assert s.name == "black_swan"
        weights = {"SPY": 1.0}
        r = StressTester.apply_scenario(weights, s)
        assert r.portfolio_impact_pct == pytest.approx(-50.0, abs=0.1)

class TestRiskEngine:
    def test_full_report(self):
        report = RiskEngine.full_report(
            _daily_returns(), portfolio_value=1_000_000, confidence=0.95,
            portfolio_weights={"SPY": 0.6, "TLT": 0.4},
        )
        assert report.var is not None
        assert report.cvar is not None
        assert len(report.stress_results) == 4
        assert "annualised_vol" in report.risk_summary
        assert "skewness" in report.risk_summary

    def test_report_no_weights(self):
        report = RiskEngine.full_report(_daily_returns())
        assert report.var is not None
        assert len(report.stress_results) == 0  # no weights → no stress

    def test_monte_carlo_report(self):
        report = RiskEngine.full_report(_daily_returns(), var_method=VaRMethod.MONTE_CARLO)
        assert report.var.method == VaRMethod.MONTE_CARLO
