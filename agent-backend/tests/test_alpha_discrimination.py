"""
tests/test_alpha_discrimination.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Alpha Discrimination Test (Quintile Spread).

All tests use synthetic DataFrames — no DB or network calls required.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from src.research.alpha_tests.models import (
    AlphaDecayPoint,
    AlphaSpreadResult,
    BucketMetrics,
    ScoreTestComparison,
    SignificanceResult,
)
from src.research.alpha_tests.quintile_spread_test import (
    build_quintile_buckets,
    calculate_bucket_metrics,
    check_monotonicity,
    compute_alpha_decay_curve,
    compute_alpha_spread,
    compute_significance,
    deduplicate_observations,
    run_full_test,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_df(
    n: int = 500,
    correlated: bool = True,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate a synthetic DataFrame mimicking OpportunityTracker data.

    If correlated=True, scores and returns are positively correlated
    (the system "works").  If False, returns are pure noise.
    """
    rng = np.random.default_rng(seed)

    tickers = [f"TKR{i:03d}" for i in range(50)]
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)

    rows = []
    for i in range(n):
        score = rng.uniform(1.0, 10.0)
        if correlated:
            # Noisy positive relationship: higher score → higher return
            r5 = (score - 5) * 0.005 + rng.normal(0, 0.02)
            r20 = (score - 5) * 0.01 + rng.normal(0, 0.03)
        else:
            r5 = rng.normal(0, 0.02)
            r20 = rng.normal(0, 0.03)

        rows.append({
            "ticker": rng.choice(tickers),
            "generated_at": base_time + timedelta(days=int(i * 0.5)),
            "opportunity_score": round(score, 2),
            "case_score": round(rng.uniform(20, 90), 1),
            "fundamental_score": round(rng.uniform(3, 9), 1),
            "technical_score": round(rng.uniform(2, 9), 1),
            "return_1d": round(r5 * 0.2, 6),
            "return_5d": round(r5, 6),
            "return_20d": round(r20, 6),
            "return_60d": round(r20 * 2.5 + rng.normal(0, 0.01), 6),
        })

    return pd.DataFrame(rows)


def _make_concentrated_df(n: int = 100, seed: int = 42) -> pd.DataFrame:
    """DataFrame where one ticker dominates >10% of observations."""
    rng = np.random.default_rng(seed)
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)

    rows = []
    for i in range(n):
        # 50% of observations are AAPL
        ticker = "AAPL" if i < n // 2 else f"TKR{i:03d}"
        rows.append({
            "ticker": ticker,
            "generated_at": base_time + timedelta(days=i),
            "opportunity_score": round(rng.uniform(1, 10), 2),
            "return_5d": round(rng.normal(0, 0.02), 6),
            "return_20d": round(rng.normal(0, 0.03), 6),
        })

    return pd.DataFrame(rows)


# ── Bucket Construction ───────────────────────────────────────────────────────


class TestBuildQuintileBuckets:
    """Tests for build_quintile_buckets()."""

    def test_creates_5_buckets_from_500_obs(self):
        df = _make_df(500)
        buckets = build_quintile_buckets(df, "opportunity_score", n_buckets=5)
        assert len(buckets) >= 4  # qcut may merge if not enough unique values
        assert all(label.startswith("Q") for label in buckets.keys())

    def test_falls_back_to_terciles_below_200(self):
        df = _make_df(100)
        buckets = build_quintile_buckets(df, "opportunity_score", n_buckets=5)
        # Should auto-fallback to 3 buckets
        assert len(buckets) <= 3
        assert all(label.startswith("T") for label in buckets.keys())

    def test_empty_df_returns_empty(self):
        df = pd.DataFrame(columns=["opportunity_score", "return_5d", "return_20d"])
        buckets = build_quintile_buckets(df, "opportunity_score")
        assert len(buckets) == 0

    def test_too_few_obs_returns_empty(self):
        df = _make_df(10)
        buckets = build_quintile_buckets(df, "opportunity_score")
        assert len(buckets) == 0

    def test_all_observations_are_distributed(self):
        df = _make_df(500)
        buckets = build_quintile_buckets(df, "opportunity_score", n_buckets=5)
        total = sum(len(b) for b in buckets.values())
        # Should contain all non-NaN observations
        expected = df["opportunity_score"].notna().sum()
        assert total == expected


# ── Bucket Metrics ────────────────────────────────────────────────────────────


class TestCalculateBucketMetrics:
    """Tests for calculate_bucket_metrics()."""

    def test_metrics_per_bucket(self):
        df = _make_df(500)
        buckets = build_quintile_buckets(df, "opportunity_score", n_buckets=5)
        metrics = calculate_bucket_metrics(buckets)

        assert len(metrics) == len(buckets)
        for m in metrics:
            assert m.count > 0
            assert 0.0 <= m.hit_rate_5d <= 1.0
            assert 0.0 <= m.hit_rate_20d <= 1.0
            assert m.std_return_20d >= 0

    def test_mean_return_is_float(self):
        df = _make_df(500)
        buckets = build_quintile_buckets(df, "opportunity_score")
        metrics = calculate_bucket_metrics(buckets)
        for m in metrics:
            assert isinstance(m.mean_return_20d, float)


# ── Alpha Spread ──────────────────────────────────────────────────────────────


class TestComputeAlphaSpread:
    """Tests for compute_alpha_spread()."""

    def test_positive_spread_with_correlated_data(self):
        df = _make_df(500, correlated=True)
        buckets = build_quintile_buckets(df, "opportunity_score")
        metrics = calculate_bucket_metrics(buckets)
        spread = compute_alpha_spread(metrics)

        assert spread["alpha_spread_5d"] > 0, "5d spread should be positive for correlated data"
        assert spread["alpha_spread_20d"] > 0, "20d spread should be positive for correlated data"

    def test_spread_near_zero_with_random_data(self):
        df = _make_df(500, correlated=False, seed=123)
        buckets = build_quintile_buckets(df, "opportunity_score")
        metrics = calculate_bucket_metrics(buckets)
        spread = compute_alpha_spread(metrics)

        # With uncorrelated data, spread should be small (within noise)
        assert abs(spread["alpha_spread_20d"]) < 0.05

    def test_insufficient_buckets(self):
        metrics = [BucketMetrics(bucket_label="Q1")]
        spread = compute_alpha_spread(metrics)
        assert spread["alpha_spread_20d"] == 0.0


# ── Statistical Significance ─────────────────────────────────────────────────


class TestComputeSignificance:
    """Tests for compute_significance()."""

    def test_correlated_data_has_positive_spearman(self):
        df = _make_df(500, correlated=True)
        buckets = build_quintile_buckets(df, "opportunity_score")
        sig = compute_significance(df, "opportunity_score", buckets)

        assert sig.spearman_correlation > 0
        assert sig.spearman_p_value is not None
        assert sig.spearman_p_value < 0.05

    def test_welch_t_test_significant_for_correlated(self):
        df = _make_df(500, correlated=True)
        buckets = build_quintile_buckets(df, "opportunity_score")
        sig = compute_significance(df, "opportunity_score", buckets)

        assert sig.welch_t_statistic is not None
        assert sig.welch_t_statistic > 0
        assert sig.welch_p_value is not None
        assert sig.welch_p_value < 0.05

    def test_bootstrap_ci_computed(self):
        df = _make_df(500, correlated=True)
        buckets = build_quintile_buckets(df, "opportunity_score")
        sig = compute_significance(df, "opportunity_score", buckets, n_bootstrap=200)

        assert sig.bootstrap_ci_lower is not None
        assert sig.bootstrap_ci_upper is not None
        assert sig.bootstrap_ci_lower < sig.bootstrap_ci_upper

    def test_kendall_tau_positive_for_correlated(self):
        df = _make_df(500, correlated=True)
        buckets = build_quintile_buckets(df, "opportunity_score")
        sig = compute_significance(df, "opportunity_score", buckets)

        assert sig.kendall_tau is not None
        assert sig.kendall_tau > 0

    def test_uncorrelated_data_not_significant(self):
        df = _make_df(500, correlated=False, seed=99)
        buckets = build_quintile_buckets(df, "opportunity_score")
        sig = compute_significance(df, "opportunity_score", buckets)

        # Spearman should be near zero
        assert abs(sig.spearman_correlation) < 0.15


# ── Deduplication ─────────────────────────────────────────────────────────────


class TestDeduplicateObservations:
    """Tests for deduplicate_observations()."""

    def test_removes_same_ticker_duplicates_within_window(self):
        base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        df = pd.DataFrame([
            {"ticker": "AAPL", "generated_at": base_time, "opportunity_score": 7.0, "return_20d": 0.01},
            {"ticker": "AAPL", "generated_at": base_time + timedelta(days=1), "opportunity_score": 7.2, "return_20d": 0.012},
            {"ticker": "AAPL", "generated_at": base_time + timedelta(days=6), "opportunity_score": 7.5, "return_20d": 0.015},
            {"ticker": "MSFT", "generated_at": base_time, "opportunity_score": 6.0, "return_20d": 0.008},
            {"ticker": "MSFT", "generated_at": base_time + timedelta(days=2), "opportunity_score": 6.3, "return_20d": 0.009},
        ])

        deduped, warnings = deduplicate_observations(df, window_days=5)

        # AAPL: keep day 0, skip day 1 (within 5d), keep day 6 (>5d gap)
        # MSFT: keep day 0, skip day 2 (within 5d)
        assert len(deduped) == 3
        assert len(warnings) > 0

    def test_empty_df_passes_through(self):
        df = pd.DataFrame(columns=["ticker", "generated_at"])
        deduped, warnings = deduplicate_observations(df)
        assert len(deduped) == 0

    def test_no_duplicates_passes_through(self):
        base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        df = pd.DataFrame([
            {"ticker": "AAPL", "generated_at": base_time, "opportunity_score": 7.0},
            {"ticker": "MSFT", "generated_at": base_time, "opportunity_score": 6.0},
            {"ticker": "GOOG", "generated_at": base_time, "opportunity_score": 8.0},
        ])
        deduped, warnings = deduplicate_observations(df, window_days=5)
        assert len(deduped) == 3


class TestConcentrationWarning:
    """Tests for concentration warning in deduplication."""

    def test_warns_on_high_concentration(self):
        df = _make_concentrated_df(100)
        _, warnings = deduplicate_observations(df, window_days=1)

        concentration_warnings = [w for w in warnings if "Concentration" in w]
        assert len(concentration_warnings) > 0


# ── Monotonicity ──────────────────────────────────────────────────────────────


class TestCheckMonotonicity:
    """Tests for check_monotonicity()."""

    def test_perfectly_monotonic(self):
        metrics = [
            BucketMetrics(bucket_label="Q1", mean_return_20d=-0.02),
            BucketMetrics(bucket_label="Q2", mean_return_20d=-0.005),
            BucketMetrics(bucket_label="Q3", mean_return_20d=0.005),
            BucketMetrics(bucket_label="Q4", mean_return_20d=0.015),
            BucketMetrics(bucket_label="Q5", mean_return_20d=0.035),
        ]
        result = check_monotonicity(metrics)
        assert result["is_monotonic"] is True
        assert len(result["violations"]) == 0

    def test_non_monotonic_detects_violations(self):
        metrics = [
            BucketMetrics(bucket_label="Q1", mean_return_20d=-0.02),
            BucketMetrics(bucket_label="Q2", mean_return_20d=0.01),
            BucketMetrics(bucket_label="Q3", mean_return_20d=-0.005),  # violation
            BucketMetrics(bucket_label="Q4", mean_return_20d=0.015),
            BucketMetrics(bucket_label="Q5", mean_return_20d=0.035),
        ]
        result = check_monotonicity(metrics)
        assert result["is_monotonic"] is False
        assert len(result["violations"]) == 1


# ── Alpha Decay Curve ─────────────────────────────────────────────────────────


class TestAlphaDecayCurve:
    """Tests for compute_alpha_decay_curve()."""

    def test_returns_4_points(self):
        df = _make_df(500, correlated=True)
        curve = compute_alpha_decay_curve(df, "opportunity_score")

        assert len(curve) == 4
        labels = [p.horizon_label for p in curve]
        assert labels == ["1d", "5d", "20d", "60d"]

    def test_correlated_data_has_positive_spreads(self):
        df = _make_df(500, correlated=True)
        curve = compute_alpha_decay_curve(df, "opportunity_score")

        for point in curve:
            if point.alpha_spread is not None:
                # With correlated data, spread should be positive
                assert point.alpha_spread > 0, f"Spread at {point.horizon_label} should be positive"


# ── Full Test Orchestrator ────────────────────────────────────────────────────


class TestRunFullTest:
    """Tests for run_full_test()."""

    def test_correlated_data_detects_signal(self):
        df = _make_df(500, correlated=True)
        result = run_full_test(score_col="opportunity_score", df=df)

        assert result.observations == 500
        assert result.alpha_spread_20d > 0
        assert result.significance.spearman_correlation > 0
        assert "Predictive" in result.signal

    def test_random_data_no_signal(self):
        df = _make_df(500, correlated=False, seed=99)
        result = run_full_test(score_col="opportunity_score", df=df)

        assert result.observations == 500
        # Should NOT pass strict acceptance with random data
        assert "Predictive ranking detected" != result.signal

    def test_empty_data(self):
        df = pd.DataFrame()
        result = run_full_test(score_col="opportunity_score", df=df)
        assert "No data" in result.signal

    def test_missing_score_column(self):
        df = _make_df(100)
        result = run_full_test(score_col="nonexistent_score", df=df)
        assert "not found" in result.signal

    def test_insufficient_observations(self):
        df = _make_df(15)
        result = run_full_test(score_col="opportunity_score", df=df)
        assert "Insufficient" in result.signal or "too few" in result.signal.lower() or len(result.buckets) == 0

    def test_acceptance_criteria_structure(self):
        df = _make_df(500, correlated=True)
        result = run_full_test(score_col="opportunity_score", df=df)

        assert "spread_positive" in result.acceptance_details
        assert "spread_significant" in result.acceptance_details
        assert "hit_rate_pass" in result.acceptance_details
        assert "spearman_positive" in result.acceptance_details


# ── Model Serialization ───────────────────────────────────────────────────────


class TestModelSerialization:
    """Tests for Pydantic model serialization/deserialization."""

    def test_alpha_spread_result_roundtrip(self):
        result = AlphaSpreadResult(
            score_column="opportunity_score",
            observations=500,
            alpha_spread_20d=0.048,
        )
        data = result.model_dump()
        recovered = AlphaSpreadResult.model_validate(data)
        assert recovered.alpha_spread_20d == 0.048

    def test_significance_result_defaults(self):
        sig = SignificanceResult()
        assert sig.spearman_correlation == 0.0
        assert sig.welch_p_value is None

    def test_score_test_comparison_empty(self):
        comp = ScoreTestComparison()
        assert comp.results == {}
        assert comp.best_score == ""

    def test_bucket_metrics_serialization(self):
        bm = BucketMetrics(
            bucket_label="Q5",
            count=120,
            mean_return_20d=0.035,
            hit_rate_20d=0.63,
        )
        data = bm.model_dump()
        assert data["bucket_label"] == "Q5"
        assert data["hit_rate_20d"] == 0.63

    def test_alpha_decay_point(self):
        point = AlphaDecayPoint(
            horizon_label="20d",
            horizon_days=20,
            alpha_spread=0.048,
        )
        data = point.model_dump()
        assert data["alpha_spread"] == 0.048
