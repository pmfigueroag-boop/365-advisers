"""
tests/test_idea_backtest.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive test suite for the IDEA Backtesting + Calibration layer.

Coverage:
  A. Snapshots — creation, serialization, signal counts
  B. Outcome evaluation — multi-horizon, missing data, hit/miss
  C. Analytics — hit_rate, average_return, coverage, grouping, buckets
  D. Calibration — monotonicity, gap, empty buckets, edge cases
  E. Decay — best horizon, decay detection, summary
  F. API contracts — response schemas, filters
  G. Metrics — counters, gauges, timing

All tests are deterministic — no external market data.
Uses FakeMarketDataProvider throughout.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from src.engines.idea_generation.models import (
    IdeaType,
    ConfidenceLevel,
    SignalStrength,
    SignalDetail,
    IdeaCandidate,
    IdeaScanResult,
)
from src.engines.idea_generation.backtest.models import (
    EvaluationHorizon,
    OutcomeLabel,
    HitPolicy,
    BacktestConfig,
    IdeaSnapshot,
    OutcomeResult,
    GroupMetrics,
    CalibrationBucket,
    CalibrationReport,
    DecayPoint,
    DecayProfile,
)


# ─── Test Helpers ────────────────────────────────────────────────────────────


def _make_snapshot(
    ticker: str = "AAPL",
    detector: str = "value",
    idea_type: str = "value",
    signal_strength: float = 0.7,
    confidence_score: float = 0.6,
    alpha_score: float = 0.5,
    price_at_signal: float | None = 150.0,
    generated_at: datetime | None = None,
) -> IdeaSnapshot:
    return IdeaSnapshot(
        ticker=ticker,
        detector=detector,
        idea_type=idea_type,
        signal_strength=signal_strength,
        confidence_score=confidence_score,
        alpha_score=alpha_score,
        price_at_signal=price_at_signal,
        generated_at=generated_at or datetime(2025, 1, 15, tzinfo=timezone.utc),
        name=f"{ticker} Inc",
        sector="Technology",
        confidence_level="high" if confidence_score > 0.7 else "medium",
    )


def _make_outcome(
    snapshot_id: str,
    horizon: EvaluationHorizon = EvaluationHorizon.H20D,
    raw_return: float | None = 0.05,
    is_hit: bool = True,
    outcome_label: OutcomeLabel = OutcomeLabel.WIN,
    data_available: bool = True,
) -> OutcomeResult:
    return OutcomeResult(
        snapshot_id=snapshot_id,
        horizon=horizon,
        raw_return=raw_return,
        is_hit=is_hit,
        outcome_label=outcome_label,
        data_available=data_available,
        price_at_signal=150.0,
        price_at_horizon=150.0 * (1 + raw_return) if raw_return is not None else None,
    )


def _make_candidate(
    ticker: str = "AAPL",
    idea_type: IdeaType = IdeaType.VALUE,
    signal_strength: float = 0.7,
    confidence_score: float = 0.6,
    detector: str = "value",
) -> IdeaCandidate:
    return IdeaCandidate(
        ticker=ticker,
        name=f"{ticker} Inc",
        sector="Technology",
        idea_type=idea_type,
        confidence=ConfidenceLevel.MEDIUM,
        signal_strength=signal_strength,
        confidence_score=confidence_score,
        signals=[
            SignalDetail(name="s1", value=0.8, threshold=0.5, strength=SignalStrength.STRONG),
            SignalDetail(name="s2", value=0.6, threshold=0.5, strength=SignalStrength.MODERATE),
            SignalDetail(name="s3", value=0.3, threshold=0.5, strength=SignalStrength.WEAK),
        ],
        detector=detector,
        metadata={"composite_alpha_score": 0.5, "source": "legacy"},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# A. SNAPSHOTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestIdeaSnapshot:
    """Verify snapshot creation, serialization, and field integrity."""

    def test_snapshot_creation(self):
        snap = _make_snapshot()
        assert snap.ticker == "AAPL"
        assert snap.detector == "value"
        assert snap.idea_type == "value"
        assert len(snap.snapshot_id) == 16

    def test_snapshot_serialization(self):
        snap = _make_snapshot()
        data = snap.model_dump(mode="json")
        assert isinstance(data["snapshot_id"], str)
        assert data["ticker"] == "AAPL"
        assert data["signal_strength"] == 0.7
        assert data["confidence_score"] == 0.6

    def test_snapshot_required_fields(self):
        snap = _make_snapshot()
        required = [
            "snapshot_id", "generated_at", "ticker", "detector",
            "idea_type", "signal_strength", "confidence_score",
        ]
        data = snap.model_dump()
        for field in required:
            assert field in data

    def test_snapshot_signal_counts(self):
        snap = _make_snapshot()
        snap.active_signals_count = 5
        snap.strong_signals_count = 2
        snap.moderate_signals_count = 2
        snap.weak_signals_count = 1
        assert snap.active_signals_count == 5
        assert snap.strong_signals_count + snap.moderate_signals_count + snap.weak_signals_count == 5

    def test_snapshot_from_candidate(self):
        from src.engines.idea_generation.backtest.snapshot_service import SnapshotService
        svc = SnapshotService()
        candidate = _make_candidate()
        snap = svc.capture_from_candidate(candidate, scan_id="test-scan-1")
        assert snap.ticker == "AAPL"
        assert snap.detector == "value"
        assert snap.scan_id == "test-scan-1"
        assert snap.strong_signals_count == 1
        assert snap.moderate_signals_count == 1
        assert snap.weak_signals_count == 1
        assert snap.active_signals_count == 3

    def test_snapshot_unique_ids(self):
        s1 = _make_snapshot()
        s2 = _make_snapshot()
        assert s1.snapshot_id != s2.snapshot_id


class TestSnapshotService:
    """Verify snapshot service capture from scan results."""

    def test_capture_from_scan_result(self):
        from src.engines.idea_generation.backtest.snapshot_service import SnapshotService
        svc = SnapshotService()
        scan_result = IdeaScanResult(
            scan_id="scan-001",
            ideas=[_make_candidate("AAPL"), _make_candidate("MSFT")],
        )
        snapshots = svc.capture_from_scan(scan_result)
        assert len(snapshots) == 2
        assert snapshots[0].scan_id == "scan-001"

    def test_capture_disabled(self):
        from src.engines.idea_generation.backtest.snapshot_service import SnapshotService
        config = BacktestConfig(snapshot_enabled=False)
        svc = SnapshotService(config=config)
        scan_result = IdeaScanResult(ideas=[_make_candidate()])
        snapshots = svc.capture_from_scan(scan_result)
        assert len(snapshots) == 0

    def test_snapshot_to_dict(self):
        from src.engines.idea_generation.backtest.snapshot_service import SnapshotService
        snap = _make_snapshot()
        data = SnapshotService.snapshot_to_dict(snap)
        assert isinstance(data, dict)
        assert data["ticker"] == "AAPL"

    def test_capture_with_prices(self):
        from src.engines.idea_generation.backtest.snapshot_service import SnapshotService
        svc = SnapshotService()
        scan_result = IdeaScanResult(ideas=[_make_candidate("AAPL")])
        snapshots = svc.capture_from_scan(scan_result, prices={"AAPL": 175.50})
        assert snapshots[0].price_at_signal == 175.50


# ═══════════════════════════════════════════════════════════════════════════════
# B. OUTCOME EVALUATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestOutcomeEvaluation:
    """Verify outcome evaluation at multiple horizons."""

    def test_evaluate_single_horizon(self):
        from src.engines.idea_generation.backtest.outcome_evaluator import OutcomeEvaluator
        from src.engines.idea_generation.backtest.market_data_provider import FakeMarketDataProvider

        provider = FakeMarketDataProvider(base_prices={"AAPL": 150.0})
        evaluator = OutcomeEvaluator(provider=provider)
        snap = _make_snapshot(price_at_signal=150.0)
        outcomes = evaluator.evaluate(snap, horizons=[EvaluationHorizon.H1D])
        assert len(outcomes) == 1
        assert outcomes[0].snapshot_id == snap.snapshot_id
        assert outcomes[0].horizon == EvaluationHorizon.H1D

    def test_evaluate_all_horizons(self):
        from src.engines.idea_generation.backtest.outcome_evaluator import OutcomeEvaluator
        from src.engines.idea_generation.backtest.market_data_provider import FakeMarketDataProvider

        provider = FakeMarketDataProvider()
        evaluator = OutcomeEvaluator(provider=provider)
        snap = _make_snapshot()
        outcomes = evaluator.evaluate(snap)
        assert len(outcomes) == 4  # 1D, 5D, 20D, 60D

    def test_evaluate_computes_return(self):
        from src.engines.idea_generation.backtest.outcome_evaluator import OutcomeEvaluator
        from src.engines.idea_generation.backtest.market_data_provider import FakeMarketDataProvider

        provider = FakeMarketDataProvider(base_prices={"TEST": 100.0}, daily_return=0.01)
        evaluator = OutcomeEvaluator(provider=provider)
        snap = _make_snapshot(ticker="TEST")
        outcomes = evaluator.evaluate(snap, horizons=[EvaluationHorizon.H1D])
        assert outcomes[0].raw_return is not None
        assert outcomes[0].data_available is True

    def test_evaluate_missing_data(self):
        from src.engines.idea_generation.backtest.outcome_evaluator import OutcomeEvaluator
        from src.engines.idea_generation.backtest.market_data_provider import FakeMarketDataProvider

        provider = FakeMarketDataProvider(missing_tickers={"MISSING"})
        evaluator = OutcomeEvaluator(provider=provider)
        snap = _make_snapshot(ticker="MISSING", price_at_signal=None)
        outcomes = evaluator.evaluate(snap, horizons=[EvaluationHorizon.H5D])
        assert len(outcomes) == 1
        assert outcomes[0].data_available is False

    def test_evaluate_with_benchmark(self):
        from src.engines.idea_generation.backtest.outcome_evaluator import OutcomeEvaluator
        from src.engines.idea_generation.backtest.market_data_provider import FakeMarketDataProvider

        provider = FakeMarketDataProvider(
            base_prices={"AAPL": 150.0, "SPY": 400.0},
            daily_return=0.001,
        )
        config = BacktestConfig(benchmark_ticker="SPY")
        evaluator = OutcomeEvaluator(provider=provider, config=config)
        snap = _make_snapshot()
        outcomes = evaluator.evaluate(snap, horizons=[EvaluationHorizon.H20D])
        assert outcomes[0].excess_return is not None

    def test_evaluate_batch(self):
        from src.engines.idea_generation.backtest.outcome_evaluator import OutcomeEvaluator
        from src.engines.idea_generation.backtest.market_data_provider import FakeMarketDataProvider

        provider = FakeMarketDataProvider()
        evaluator = OutcomeEvaluator(provider=provider)
        snaps = [_make_snapshot("AAPL"), _make_snapshot("MSFT")]
        outcomes = evaluator.evaluate_batch(snaps, horizons=[EvaluationHorizon.H5D])
        assert len(outcomes) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# HIT POLICY
# ═══════════════════════════════════════════════════════════════════════════════


class TestHitPolicy:
    """Verify hit/miss classification."""

    def test_positive_return_is_win(self):
        policy = HitPolicy()
        label = policy.classify(0.05)
        assert label == OutcomeLabel.WIN

    def test_negative_return_is_loss(self):
        policy = HitPolicy()
        label = policy.classify(-0.05)
        assert label == OutcomeLabel.LOSS

    def test_near_zero_is_neutral(self):
        policy = HitPolicy(neutral_band=0.01)
        label = policy.classify(0.005)
        assert label == OutcomeLabel.NEUTRAL

    def test_custom_threshold(self):
        policy = HitPolicy(threshold=0.02, neutral_band=0.005)
        assert policy.classify(0.03) == OutcomeLabel.WIN
        assert policy.classify(0.01) == OutcomeLabel.LOSS

    def test_is_hit_convenience(self):
        policy = HitPolicy()
        assert policy.is_hit(0.05) is True
        assert policy.is_hit(-0.05) is False

    def test_none_return_is_neutral(self):
        policy = HitPolicy()
        assert policy.classify(None) == OutcomeLabel.NEUTRAL

    def test_excess_mode(self):
        policy = HitPolicy(mode="excess_above_threshold")
        assert policy.classify(0.05, excess_return=-0.02) == OutcomeLabel.LOSS


# ═══════════════════════════════════════════════════════════════════════════════
# C. ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAnalytics:
    """Verify aggregated analytics computations."""

    def test_hit_rate_computation(self):
        from src.engines.idea_generation.backtest.analytics_service import compute_group_metrics

        snaps = [_make_snapshot(ticker=f"T{i}") for i in range(10)]
        outcomes = []
        for i, snap in enumerate(snaps):
            outcomes.append(_make_outcome(
                snap.snapshot_id,
                raw_return=0.05 if i < 7 else -0.03,
                is_hit=i < 7,
                outcome_label=OutcomeLabel.WIN if i < 7 else OutcomeLabel.LOSS,
            ))

        metrics = compute_group_metrics(snaps, outcomes, "test", "all")
        assert metrics.hit_rate == 0.7
        assert metrics.total_ideas == 10
        assert metrics.total_evaluated == 10

    def test_average_return(self):
        from src.engines.idea_generation.backtest.analytics_service import compute_group_metrics

        snaps = [_make_snapshot()]
        outcomes = [_make_outcome(snaps[0].snapshot_id, raw_return=0.10)]
        metrics = compute_group_metrics(snaps, outcomes, "test", "all")
        assert metrics.average_return == 0.10

    def test_coverage_ratio(self):
        from src.engines.idea_generation.backtest.analytics_service import compute_group_metrics

        snaps = [_make_snapshot(ticker=f"T{i}") for i in range(10)]
        outcomes = [_make_outcome(snaps[i].snapshot_id) for i in range(5)]
        metrics = compute_group_metrics(snaps, outcomes, "test", "all")
        assert metrics.coverage_ratio == 0.5

    def test_analytics_by_detector(self):
        from src.engines.idea_generation.backtest.analytics_service import analytics_by_detector

        snaps = [
            _make_snapshot(detector="value", ticker="A"),
            _make_snapshot(detector="value", ticker="B"),
            _make_snapshot(detector="growth", ticker="C"),
        ]
        outcomes = [
            _make_outcome(snaps[0].snapshot_id, raw_return=0.05, is_hit=True),
            _make_outcome(snaps[1].snapshot_id, raw_return=-0.02, is_hit=False, outcome_label=OutcomeLabel.LOSS),
            _make_outcome(snaps[2].snapshot_id, raw_return=0.08, is_hit=True),
        ]
        results = analytics_by_detector(snaps, outcomes)
        assert len(results) == 2
        detector_names = {r.group_value for r in results}
        assert "value" in detector_names
        assert "growth" in detector_names

    def test_analytics_by_confidence_bucket(self):
        from src.engines.idea_generation.backtest.analytics_service import analytics_by_confidence_bucket

        snaps = [
            _make_snapshot(confidence_score=0.1, ticker="A"),
            _make_snapshot(confidence_score=0.5, ticker="B"),
            _make_snapshot(confidence_score=0.9, ticker="C"),
        ]
        outcomes = [
            _make_outcome(snaps[0].snapshot_id, raw_return=-0.01, is_hit=False, outcome_label=OutcomeLabel.LOSS),
            _make_outcome(snaps[1].snapshot_id, raw_return=0.02, is_hit=True),
            _make_outcome(snaps[2].snapshot_id, raw_return=0.08, is_hit=True),
        ]
        results = analytics_by_confidence_bucket(snaps, outcomes)
        assert len(results) >= 2

    def test_no_outcomes_returns_zeros(self):
        from src.engines.idea_generation.backtest.analytics_service import compute_group_metrics

        snaps = [_make_snapshot()]
        metrics = compute_group_metrics(snaps, [], "test", "all")
        assert metrics.total_evaluated == 0
        assert metrics.hit_rate == 0.0

    def test_analytics_summary(self):
        from src.engines.idea_generation.backtest.analytics_service import analytics_summary

        snaps = [_make_snapshot(ticker="A"), _make_snapshot(ticker="B")]
        outcomes = [
            _make_outcome(snaps[0].snapshot_id, raw_return=0.05, is_hit=True),
            _make_outcome(snaps[1].snapshot_id, raw_return=0.03, is_hit=True),
        ]
        summary = analytics_summary(snaps, outcomes)
        assert summary.group_key == "overall"
        assert summary.hit_rate == 1.0

    def test_win_loss_ratio(self):
        from src.engines.idea_generation.backtest.analytics_service import compute_group_metrics

        snaps = [_make_snapshot(ticker=f"T{i}") for i in range(4)]
        outcomes = [
            _make_outcome(snaps[0].snapshot_id, raw_return=0.05, is_hit=True, outcome_label=OutcomeLabel.WIN),
            _make_outcome(snaps[1].snapshot_id, raw_return=0.03, is_hit=True, outcome_label=OutcomeLabel.WIN),
            _make_outcome(snaps[2].snapshot_id, raw_return=0.01, is_hit=True, outcome_label=OutcomeLabel.WIN),
            _make_outcome(snaps[3].snapshot_id, raw_return=-0.05, is_hit=False, outcome_label=OutcomeLabel.LOSS),
        ]
        metrics = compute_group_metrics(snaps, outcomes, "test", "all")
        assert metrics.win_loss_ratio == 3.0


# ═══════════════════════════════════════════════════════════════════════════════
# D. CALIBRATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalibration:
    """Verify calibration analysis."""

    def test_calibration_with_monotonic_data(self):
        from src.engines.idea_generation.backtest.calibration_service import compute_calibration

        snaps = [
            _make_snapshot(confidence_score=0.1, ticker="A"),
            _make_snapshot(confidence_score=0.3, ticker="B"),
            _make_snapshot(confidence_score=0.5, ticker="C"),
            _make_snapshot(confidence_score=0.7, ticker="D"),
            _make_snapshot(confidence_score=0.9, ticker="E"),
        ]
        outcomes = [
            _make_outcome(snaps[0].snapshot_id, raw_return=-0.05, is_hit=False, outcome_label=OutcomeLabel.LOSS),
            _make_outcome(snaps[1].snapshot_id, raw_return=-0.02, is_hit=False, outcome_label=OutcomeLabel.LOSS),
            _make_outcome(snaps[2].snapshot_id, raw_return=0.01, is_hit=True),
            _make_outcome(snaps[3].snapshot_id, raw_return=0.05, is_hit=True),
            _make_outcome(snaps[4].snapshot_id, raw_return=0.10, is_hit=True),
        ]
        report = compute_calibration(snaps, outcomes)
        assert report.is_monotonic is True
        assert len(report.monotonicity_violations) == 0
        assert report.total_evaluated == 5
        assert len(report.buckets) == 5

    def test_calibration_detects_non_monotonic(self):
        from src.engines.idea_generation.backtest.calibration_service import compute_calibration

        snaps = [
            _make_snapshot(confidence_score=0.1, ticker="A"),
            _make_snapshot(confidence_score=0.9, ticker="B"),
        ]
        # Low confidence hits, high confidence misses
        outcomes = [
            _make_outcome(snaps[0].snapshot_id, raw_return=0.05, is_hit=True),
            _make_outcome(snaps[1].snapshot_id, raw_return=-0.05, is_hit=False, outcome_label=OutcomeLabel.LOSS),
        ]
        report = compute_calibration(snaps, outcomes)
        assert report.is_monotonic is False
        assert len(report.monotonicity_violations) > 0

    def test_calibration_gap(self):
        from src.engines.idea_generation.backtest.calibration_service import compute_calibration

        snaps = [_make_snapshot(confidence_score=0.9, ticker="A")]
        outcomes = [_make_outcome(snaps[0].snapshot_id, raw_return=-0.05, is_hit=False, outcome_label=OutcomeLabel.LOSS)]
        report = compute_calibration(snaps, outcomes)
        # Confidence ~0.9 but hit_rate = 0, gap should be ~0.9
        high_bucket = [b for b in report.buckets if b.bucket_label == "0.8–1.0"]
        assert len(high_bucket) == 1
        assert high_bucket[0].calibration_gap > 0.5  # Overconfident

    def test_calibration_empty_buckets(self):
        from src.engines.idea_generation.backtest.calibration_service import compute_calibration

        report = compute_calibration([], [])
        assert len(report.buckets) == 5
        assert all(b.total_count == 0 for b in report.buckets)
        assert report.overall_calibration_error == 0.0

    def test_calibration_single_bucket(self):
        from src.engines.idea_generation.backtest.calibration_service import compute_calibration

        snaps = [_make_snapshot(confidence_score=0.5, ticker="A")]
        outcomes = [_make_outcome(snaps[0].snapshot_id, raw_return=0.05, is_hit=True)]
        report = compute_calibration(snaps, outcomes)
        assert report.is_monotonic is True  # Only one non-empty bucket


# ═══════════════════════════════════════════════════════════════════════════════
# E. DECAY ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDecayAnalysis:
    """Verify alpha decay analysis."""

    def test_decay_profile_creation(self):
        from src.engines.idea_generation.backtest.decay_analysis import compute_decay_profile

        snap = _make_snapshot()
        outcomes = [
            _make_outcome(snap.snapshot_id, horizon=EvaluationHorizon.H1D, raw_return=0.05, is_hit=True),
            _make_outcome(snap.snapshot_id, horizon=EvaluationHorizon.H5D, raw_return=0.03, is_hit=True),
            _make_outcome(snap.snapshot_id, horizon=EvaluationHorizon.H20D, raw_return=0.01, is_hit=True),
            _make_outcome(snap.snapshot_id, horizon=EvaluationHorizon.H60D, raw_return=-0.02, is_hit=False, outcome_label=OutcomeLabel.LOSS),
        ]
        profile = compute_decay_profile("test", "all", [snap], outcomes)
        assert len(profile.points) == 4
        assert profile.best_horizon == "1D"

    def test_decay_detection(self):
        from src.engines.idea_generation.backtest.decay_analysis import compute_decay_profile

        snap = _make_snapshot()
        # Declining returns: strong decay
        outcomes = [
            _make_outcome(snap.snapshot_id, horizon=EvaluationHorizon.H1D, raw_return=0.10),
            _make_outcome(snap.snapshot_id, horizon=EvaluationHorizon.H5D, raw_return=0.06),
            _make_outcome(snap.snapshot_id, horizon=EvaluationHorizon.H20D, raw_return=0.02),
            _make_outcome(snap.snapshot_id, horizon=EvaluationHorizon.H60D, raw_return=-0.01, is_hit=False, outcome_label=OutcomeLabel.LOSS),
        ]
        profile = compute_decay_profile("test", "all", [snap], outcomes)
        assert profile.decay_detected is True
        assert "peaks at 1D" in profile.decay_description

    def test_decay_no_decay(self):
        from src.engines.idea_generation.backtest.decay_analysis import compute_decay_profile

        snap = _make_snapshot()
        # Improving returns: no decay
        outcomes = [
            _make_outcome(snap.snapshot_id, horizon=EvaluationHorizon.H1D, raw_return=0.01),
            _make_outcome(snap.snapshot_id, horizon=EvaluationHorizon.H5D, raw_return=0.03),
            _make_outcome(snap.snapshot_id, horizon=EvaluationHorizon.H20D, raw_return=0.06),
            _make_outcome(snap.snapshot_id, horizon=EvaluationHorizon.H60D, raw_return=0.10),
        ]
        profile = compute_decay_profile("test", "all", [snap], outcomes)
        assert profile.best_horizon == "60D"

    def test_decay_by_detector(self):
        from src.engines.idea_generation.backtest.decay_analysis import decay_by_detector

        snaps = [
            _make_snapshot(detector="value", ticker="A"),
            _make_snapshot(detector="growth", ticker="B"),
        ]
        outcomes = [
            _make_outcome(snaps[0].snapshot_id, horizon=EvaluationHorizon.H5D, raw_return=0.05),
            _make_outcome(snaps[1].snapshot_id, horizon=EvaluationHorizon.H5D, raw_return=0.03),
        ]
        profiles = decay_by_detector(snaps, outcomes)
        assert len(profiles) == 2

    def test_decay_summary(self):
        from src.engines.idea_generation.backtest.decay_analysis import decay_summary

        snap = _make_snapshot()
        outcomes = [
            _make_outcome(snap.snapshot_id, horizon=EvaluationHorizon.H1D, raw_return=0.02),
        ]
        profile = decay_summary([snap], outcomes)
        assert profile.group_key == "overall"

    def test_decay_insufficient_data(self):
        from src.engines.idea_generation.backtest.decay_analysis import compute_decay_profile

        profile = compute_decay_profile("test", "all", [], [])
        assert profile.decay_detected is False


# ═══════════════════════════════════════════════════════════════════════════════
# F. API CONTRACTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAPIContracts:
    """Verify API response schemas and models."""

    def test_backtest_summary_response_schema(self):
        from src.routes.ideas_backtest import BacktestSummaryResponse
        schema = BacktestSummaryResponse.model_json_schema()
        assert "overall" in schema["properties"]
        assert "by_detector" in schema["properties"]
        assert "total_snapshots" in schema["properties"]

    def test_calibration_report_schema(self):
        schema = CalibrationReport.model_json_schema()
        assert "buckets" in schema["properties"]
        assert "is_monotonic" in schema["properties"]
        assert "overall_calibration_error" in schema["properties"]

    def test_decay_profile_schema(self):
        schema = DecayProfile.model_json_schema()
        assert "points" in schema["properties"]
        assert "best_horizon" in schema["properties"]
        assert "decay_detected" in schema["properties"]

    def test_group_metrics_schema(self):
        schema = GroupMetrics.model_json_schema()
        expected_fields = [
            "hit_rate", "average_return", "median_return",
            "coverage_ratio", "false_positive_rate",
        ]
        for field in expected_fields:
            assert field in schema["properties"]

    def test_evaluate_request_schema(self):
        from src.routes.ideas_backtest import EvaluateRequest
        schema = EvaluateRequest.model_json_schema()
        assert "snapshot_ids" in schema["properties"]

    def test_evaluate_request_max_limit(self):
        from src.routes.ideas_backtest import EvaluateRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            EvaluateRequest(snapshot_ids=["x"] * 101)

    def test_evaluate_request_min_limit(self):
        from src.routes.ideas_backtest import EvaluateRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            EvaluateRequest(snapshot_ids=[])

    def test_decay_response_schema(self):
        from src.routes.ideas_backtest import DecayResponse
        schema = DecayResponse.model_json_schema()
        assert "overall" in schema["properties"]
        assert "by_detector" in schema["properties"]


# ═══════════════════════════════════════════════════════════════════════════════
# G. METRICS / OBSERVABILITY
# ═══════════════════════════════════════════════════════════════════════════════


class TestBacktestMetrics:
    """Verify backtest-specific observability metrics."""

    def test_snapshot_metrics(self):
        from src.engines.idea_generation.metrics import (
            InMemoryCollector, set_collector, get_collector,
        )
        from src.engines.idea_generation.backtest.snapshot_service import SnapshotService

        original = get_collector()
        mem = InMemoryCollector()
        set_collector(mem)
        try:
            svc = SnapshotService()
            scan_result = IdeaScanResult(ideas=[_make_candidate()])
            svc.capture_from_scan(scan_result)
            assert mem.get("idea_snapshots_created_total", detector="value", idea_type="value") == 1
        finally:
            set_collector(original)

    def test_evaluation_metrics(self):
        from src.engines.idea_generation.metrics import (
            InMemoryCollector, set_collector, get_collector,
        )
        from src.engines.idea_generation.backtest.outcome_evaluator import OutcomeEvaluator
        from src.engines.idea_generation.backtest.market_data_provider import FakeMarketDataProvider

        original = get_collector()
        mem = InMemoryCollector()
        set_collector(mem)
        try:
            provider = FakeMarketDataProvider()
            evaluator = OutcomeEvaluator(provider=provider)
            snap = _make_snapshot()
            evaluator.evaluate(snap, horizons=[EvaluationHorizon.H5D])

            assert mem.get("snapshot_evaluations_started_total", detector="value", idea_type="value") == 1
            assert mem.get("snapshot_evaluations_completed_total", detector="value", idea_type="value") == 1
            assert mem.total("outcomes_recorded_total") == 1
            timings = mem.get_timing("evaluation_duration_ms", detector="value")
            assert len(timings) == 1
        finally:
            set_collector(original)

    def test_calibration_metrics(self):
        from src.engines.idea_generation.metrics import (
            InMemoryCollector, set_collector, get_collector,
        )
        from src.engines.idea_generation.backtest.calibration_service import compute_calibration

        original = get_collector()
        mem = InMemoryCollector()
        set_collector(mem)
        try:
            compute_calibration([], [])
            assert mem.get("calibration_runs_total") == 1
        finally:
            set_collector(original)

    def test_metrics_tags_are_low_cardinality(self):
        """Verify we never use ticker/snapshot_id/scan_id as metric labels."""
        from src.engines.idea_generation.metrics import (
            InMemoryCollector, set_collector, get_collector,
        )
        from src.engines.idea_generation.backtest.outcome_evaluator import OutcomeEvaluator
        from src.engines.idea_generation.backtest.market_data_provider import FakeMarketDataProvider

        original = get_collector()
        mem = InMemoryCollector()
        set_collector(mem)
        try:
            provider = FakeMarketDataProvider()
            evaluator = OutcomeEvaluator(provider=provider)
            snap = _make_snapshot()
            evaluator.evaluate(snap)

            # Check all metric tags — none should contain high-cardinality values
            for (name, tags_tuple), _ in mem._counters.items():
                tag_keys = {k for k, _ in tags_tuple}
                assert "ticker" not in tag_keys, f"ticker found in tags for {name}"
                assert "snapshot_id" not in tag_keys, f"snapshot_id found in tags for {name}"
                assert "scan_id" not in tag_keys, f"scan_id found in tags for {name}"
        finally:
            set_collector(original)


# ═══════════════════════════════════════════════════════════════════════════════
# MARKET DATA PROVIDER
# ═══════════════════════════════════════════════════════════════════════════════


class TestFakeMarketDataProvider:
    """Verify fake market data provider."""

    def test_deterministic_prices(self):
        from src.engines.idea_generation.backtest.market_data_provider import FakeMarketDataProvider

        p = FakeMarketDataProvider(base_prices={"AAPL": 150.0})
        date = datetime(2025, 6, 1)
        price1 = p.get_price("AAPL", date)
        price2 = p.get_price("AAPL", date)
        assert price1 == price2
        assert price1 is not None

    def test_missing_ticker(self):
        from src.engines.idea_generation.backtest.market_data_provider import FakeMarketDataProvider

        p = FakeMarketDataProvider(missing_tickers={"MISSING"})
        assert p.get_price("MISSING", datetime(2025, 1, 1)) is None

    def test_override_prices(self):
        from src.engines.idea_generation.backtest.market_data_provider import FakeMarketDataProvider

        p = FakeMarketDataProvider()
        date = datetime(2025, 6, 1)
        p.set_price("TEST", date, 999.99)
        assert p.get_price("TEST", date) == 999.99

    def test_price_series(self):
        from src.engines.idea_generation.backtest.market_data_provider import FakeMarketDataProvider

        p = FakeMarketDataProvider()
        series = p.get_price_series(
            "AAPL",
            datetime(2025, 1, 1),
            datetime(2025, 1, 5),
        )
        assert len(series) == 5
        assert all(isinstance(date, datetime) and isinstance(price, float) for date, price in series)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMERATIONS & CONFIG
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnumsAndConfig:
    """Verify enumerations and configuration models."""

    def test_evaluation_horizons(self):
        assert len(EvaluationHorizon) == 4
        assert EvaluationHorizon.H1D.value == "1D"
        assert EvaluationHorizon.H60D.calendar_days == 90

    def test_outcome_labels(self):
        assert OutcomeLabel.WIN.value == "win"
        assert OutcomeLabel.LOSS.value == "loss"
        assert OutcomeLabel.NEUTRAL.value == "neutral"

    def test_backtest_config_defaults(self):
        config = BacktestConfig()
        assert config.snapshot_enabled is True
        assert len(config.horizons) == 4
        assert config.benchmark_ticker is None

    def test_backtest_config_custom(self):
        config = BacktestConfig(
            snapshot_enabled=False,
            horizons=[EvaluationHorizon.H5D, EvaluationHorizon.H20D],
            benchmark_ticker="SPY",
        )
        assert config.snapshot_enabled is False
        assert len(config.horizons) == 2

    def test_hit_policy_serialization(self):
        policy = HitPolicy(threshold=0.01, neutral_band=0.005)
        data = policy.model_dump()
        assert data["threshold"] == 0.01
        assert data["neutral_band"] == 0.005

    def test_outcome_result_serialization(self):
        outcome = OutcomeResult(
            snapshot_id="abc123",
            horizon=EvaluationHorizon.H20D,
            raw_return=0.05,
            is_hit=True,
            outcome_label=OutcomeLabel.WIN,
        )
        data = outcome.model_dump(mode="json")
        assert data["horizon"] == "20D"
        assert data["outcome_label"] == "win"
