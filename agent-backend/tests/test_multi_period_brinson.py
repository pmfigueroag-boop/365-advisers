"""
tests/test_multi_period_brinson.py — Tests for multi-period Brinson attribution.
"""
from __future__ import annotations
import pytest
from src.engines.attribution.multi_period_brinson import (
    MultiPeriodBrinson, PeriodData, LinkedAttribution,
)


def _period(label, pw, bw, pr, br):
    return PeriodData(
        period_label=label,
        portfolio_weights=pw, benchmark_weights=bw,
        portfolio_returns=pr, benchmark_returns=br,
    )


W_P = {"Tech": 0.40, "Health": 0.30, "Fin": 0.30}
W_B = {"Tech": 0.30, "Health": 0.35, "Fin": 0.35}


class TestMultiPeriodBrinson:

    def test_single_period_matches_single(self):
        p = _period("Q1", W_P, W_B,
                     {"Tech": 0.08, "Health": 0.02, "Fin": 0.05},
                     {"Tech": 0.06, "Health": 0.03, "Fin": 0.04})
        result = MultiPeriodBrinson.attribute_multi_period([p])
        assert result.n_periods == 1
        assert abs(result.total_active_return - result.period_results[0].active_return) < 1e-4

    def test_multi_period_decomposition_sums(self):
        periods = [
            _period("M1", W_P, W_B,
                    {"Tech": 0.05, "Health": 0.02, "Fin": 0.03},
                    {"Tech": 0.04, "Health": 0.01, "Fin": 0.02}),
            _period("M2", W_P, W_B,
                    {"Tech": 0.03, "Health": -0.01, "Fin": 0.04},
                    {"Tech": 0.02, "Health": 0.00, "Fin": 0.03}),
            _period("M3", W_P, W_B,
                    {"Tech": 0.06, "Health": 0.01, "Fin": 0.02},
                    {"Tech": 0.05, "Health": 0.02, "Fin": 0.01}),
        ]
        result = MultiPeriodBrinson.attribute_multi_period(periods)
        linked_sum = result.linked_allocation + result.linked_selection + result.linked_interaction
        assert abs(result.total_active_return - linked_sum) < 0.005  # Tolerance for linking

    def test_compounding_returns(self):
        periods = [
            _period("M1", W_P, W_B,
                    {"Tech": 0.10, "Health": 0.05, "Fin": 0.03},
                    {"Tech": 0.08, "Health": 0.04, "Fin": 0.02}),
            _period("M2", W_P, W_B,
                    {"Tech": 0.05, "Health": 0.02, "Fin": 0.04},
                    {"Tech": 0.03, "Health": 0.01, "Fin": 0.03}),
        ]
        result = MultiPeriodBrinson.attribute_multi_period(periods)
        # Compounded return ≠ sum of period returns
        simple_sum = sum(r.portfolio_return for r in result.period_results)
        assert result.total_portfolio_return != pytest.approx(simple_sum, abs=1e-4)

    def test_zero_return_periods(self):
        periods = [
            _period("M1", W_P, W_B,
                    {"Tech": 0.0, "Health": 0.0, "Fin": 0.0},
                    {"Tech": 0.0, "Health": 0.0, "Fin": 0.0}),
        ]
        result = MultiPeriodBrinson.attribute_multi_period(periods)
        assert result.total_active_return == pytest.approx(0, abs=1e-6)

    def test_period_labels_preserved(self):
        periods = [
            _period("2024-Q1", W_P, W_B,
                    {"Tech": 0.05, "Health": 0.02, "Fin": 0.03},
                    {"Tech": 0.04, "Health": 0.01, "Fin": 0.02}),
            _period("2024-Q2", W_P, W_B,
                    {"Tech": 0.03, "Health": 0.01, "Fin": 0.04},
                    {"Tech": 0.02, "Health": 0.00, "Fin": 0.03}),
        ]
        result = MultiPeriodBrinson.attribute_multi_period(periods)
        assert result.period_labels == ["2024-Q1", "2024-Q2"]

    def test_empty_periods(self):
        result = MultiPeriodBrinson.attribute_multi_period([])
        assert result.n_periods == 0

    def test_result_contract(self):
        periods = [
            _period("Q1", W_P, W_B,
                    {"Tech": 0.05, "Health": 0.02, "Fin": 0.03},
                    {"Tech": 0.04, "Health": 0.01, "Fin": 0.02}),
        ]
        result = MultiPeriodBrinson.attribute_multi_period(periods)
        assert isinstance(result, LinkedAttribution)
        d = result.model_dump()
        assert "linked_allocation" in d
        assert "total_active_return" in d
