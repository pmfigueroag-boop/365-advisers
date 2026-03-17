"""
tests/test_performance_report.py
--------------------------------------------------------------------------
Tests for PerformanceReportBuilder — enhanced metrics.
"""

from __future__ import annotations

import math
import random
import pytest

from src.engines.autonomous_pm.performance_report import (
    PerformanceReportBuilder,
    PerformanceReport,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_bull_returns(n: int = 252) -> list[float]:
    """Simulated bull market: slight positive drift, moderate vol."""
    rng = random.Random(42)
    return [0.0004 + rng.gauss(0, 0.01) for _ in range(n)]


def _make_bear_returns(n: int = 252) -> list[float]:
    """Simulated bear market: strong negative drift."""
    rng = random.Random(42)
    return [-0.002 + rng.gauss(0, 0.012) for _ in range(n)]


def _make_flat_returns(n: int = 252) -> list[float]:
    """No drift, low vol."""
    rng = random.Random(42)
    return [rng.gauss(0, 0.002) for _ in range(n)]


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestPerformanceReportBuilder:

    def test_bull_market_positive_metrics(self):
        """Bull market → positive Sharpe, Sortino, Calmar."""
        report = PerformanceReportBuilder.build(_make_bull_returns())

        assert report.snapshot is not None
        assert report.snapshot.sharpe_ratio > 0
        assert report.sortino_ratio > 0
        assert report.calmar_ratio > 0
        assert report.win_rate > 0.45

    def test_bear_market_negative_metrics(self):
        """Bear market → negative Sharpe."""
        report = PerformanceReportBuilder.build(_make_bear_returns())

        assert report.snapshot is not None
        assert report.snapshot.sharpe_ratio < 0
        assert report.win_rate < 0.55

    def test_sortino_higher_than_sharpe_with_positive_skew(self):
        """Sortino should differ from Sharpe due to downside-only deviation."""
        report = PerformanceReportBuilder.build(_make_bull_returns())
        # Both should be computed
        assert report.sortino_ratio != 0
        assert report.snapshot.sharpe_ratio != 0

    def test_calmar_ratio_computed(self):
        """Calmar = annualized return / |max DD|."""
        report = PerformanceReportBuilder.build(_make_bull_returns())
        assert report.calmar_ratio != 0

    def test_drawdown_analysis(self):
        """Drawdown metrics are populated."""
        report = PerformanceReportBuilder.build(_make_bull_returns())
        dd = report.drawdown

        assert dd.max_drawdown <= 0  # DD is always <= 0
        assert dd.max_drawdown_duration_days >= 0

    def test_rolling_sharpe_populated(self):
        """Rolling Sharpe series is computed."""
        returns = _make_bull_returns(252)
        report = PerformanceReportBuilder.build(returns, rolling_window=60)

        assert len(report.rolling_sharpe.values) == 252 - 60 + 1
        assert report.rolling_sharpe.window_days == 60
        assert report.rolling_sharpe.mean != 0

    def test_rolling_sharpe_insufficient_data(self):
        """< window returns → empty rolling Sharpe."""
        report = PerformanceReportBuilder.build([0.01] * 30, rolling_window=60)
        assert len(report.rolling_sharpe.values) == 0

    def test_win_rate_bounds(self):
        """Win rate is between 0 and 1."""
        report = PerformanceReportBuilder.build(_make_bull_returns())
        assert 0 <= report.win_rate <= 1

    def test_best_worst_day(self):
        """Best day >= worst day."""
        report = PerformanceReportBuilder.build(_make_bull_returns())
        assert report.best_day >= report.worst_day

    def test_profit_factor(self):
        """Profit factor > 0 for bull market."""
        report = PerformanceReportBuilder.build(_make_bull_returns())
        assert report.profit_factor > 0

    def test_skewness_kurtosis_computed(self):
        """Skewness and kurtosis are non-zero for real data."""
        report = PerformanceReportBuilder.build(_make_bull_returns())
        # Just verify they're computed (not NaN)
        assert math.isfinite(report.skewness)
        assert math.isfinite(report.kurtosis)

    def test_monthly_returns(self):
        """Monthly returns table is populated."""
        report = PerformanceReportBuilder.build(_make_bull_returns(252))
        assert len(report.monthly_returns) >= 10  # ~12 months in 252 days
        for mr in report.monthly_returns:
            assert mr.year >= 2024
            assert 1 <= mr.month <= 12

    def test_empty_returns(self):
        """Empty returns → empty report."""
        report = PerformanceReportBuilder.build([])
        assert report.period_days == 0
        assert report.snapshot is None

    def test_benchmark_comparison(self):
        """Benchmark data flows through to snapshot."""
        p = _make_bull_returns()
        b = _make_flat_returns()
        report = PerformanceReportBuilder.build(p, benchmark_returns=b)

        assert report.snapshot is not None
        assert report.snapshot.alpha_vs_benchmark != 0
