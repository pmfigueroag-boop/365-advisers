"""
tests/test_attribution.py — Brinson-Fachler performance attribution tests.
"""
import pytest
from src.engines.attribution.brinson import BrinsonFachler
from src.engines.attribution.engine import AttributionEngine


class TestBrinsonFachler:
    def _data(self):
        pw = {"Tech": 0.40, "Finance": 0.30, "Healthcare": 0.20, "Energy": 0.10}
        bw = {"Tech": 0.25, "Finance": 0.25, "Healthcare": 0.25, "Energy": 0.25}
        pr = {"Tech": 0.15, "Finance": 0.05, "Healthcare": 0.08, "Energy": -0.02}
        br = {"Tech": 0.10, "Finance": 0.06, "Healthcare": 0.07, "Energy": 0.03}
        return pw, bw, pr, br

    def test_active_return(self):
        pw, bw, pr, br = self._data()
        r = BrinsonFachler.attribute(pw, bw, pr, br)
        port_ret = sum(pw[s] * pr[s] for s in pw)
        bench_ret = sum(bw[s] * br[s] for s in bw)
        assert r.active_return == pytest.approx(port_ret - bench_ret, abs=0.001)

    def test_effects_sum_to_active_return(self):
        pw, bw, pr, br = self._data()
        r = BrinsonFachler.attribute(pw, bw, pr, br)
        effects_sum = r.total_allocation + r.total_selection + r.total_interaction
        assert effects_sum == pytest.approx(r.active_return, abs=0.001)

    def test_has_sector_details(self):
        pw, bw, pr, br = self._data()
        r = BrinsonFachler.attribute(pw, bw, pr, br)
        assert len(r.sector_attribution) == 4

    def test_top_contributors(self):
        pw, bw, pr, br = self._data()
        r = BrinsonFachler.attribute(pw, bw, pr, br)
        assert isinstance(r.top_contributors, list)

    def test_overweight_outperform(self):
        pw, bw, pr, br = self._data()
        r = BrinsonFachler.attribute(pw, bw, pr, br)
        # Tech is overweight and outperforms → positive total
        tech = next(s for s in r.sector_attribution if s.sector == "Tech")
        assert tech.total_effect > 0


class TestAttributionEngine:
    def test_single_period(self):
        pw = {"Tech": 0.50, "Finance": 0.50}
        bw = {"Tech": 0.50, "Finance": 0.50}
        pr = {"Tech": 0.10, "Finance": 0.05}
        br = {"Tech": 0.08, "Finance": 0.06}
        r = AttributionEngine.single_period(pw, bw, pr, br)
        assert r.active_return == pytest.approx(0.005, abs=0.01)

    def test_multi_period(self):
        periods = [
            {"period": "Q1", "portfolio_weights": {"A": 0.5, "B": 0.5},
             "benchmark_weights": {"A": 0.5, "B": 0.5},
             "portfolio_returns": {"A": 0.05, "B": 0.03},
             "benchmark_returns": {"A": 0.04, "B": 0.04}},
            {"period": "Q2", "portfolio_weights": {"A": 0.6, "B": 0.4},
             "benchmark_weights": {"A": 0.5, "B": 0.5},
             "portfolio_returns": {"A": 0.08, "B": 0.02},
             "benchmark_returns": {"A": 0.06, "B": 0.05}},
        ]
        results = AttributionEngine.multi_period(periods)
        assert len(results) == 2

    def test_cumulative(self):
        periods = AttributionEngine.multi_period([
            {"period": "Q1", "portfolio_weights": {"A": 1.0},
             "benchmark_weights": {"A": 1.0},
             "portfolio_returns": {"A": 0.10},
             "benchmark_returns": {"A": 0.08}},
        ])
        cum = AttributionEngine.cumulative_attribution(periods)
        assert cum["num_periods"] == 1
