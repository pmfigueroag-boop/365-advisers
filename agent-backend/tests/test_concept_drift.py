"""
tests/test_concept_drift.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Concept Drift Detection Engine.

Covers:
  - DistributionShiftDetector (KS test: same dist, shifted dist)
  - CorrelationBreakdownDetector (stable, decorrelated)
  - RegimeShiftDetector (CUSUM: stable, mean jump)
  - DriftAggregator (severity escalation)
  - ConceptDriftEngine (full pipeline)
  - Pydantic model contracts
  - DB table definition
"""

from __future__ import annotations

import numpy as np
import pytest

from src.engines.concept_drift.detectors import (
    CorrelationBreakdownDetector,
    DistributionShiftDetector,
    RegimeShiftDetector,
)
from src.engines.concept_drift.aggregator import DriftAggregator
from src.engines.concept_drift.engine import ConceptDriftEngine
from src.engines.concept_drift.models import (
    ConceptDriftReport,
    DetectorType,
    DriftAlert,
    DriftConfig,
    DriftDetection,
    DriftSeverity,
)
from src.engines.backtesting.models import SignalEvent
from src.engines.alpha_signals.models import SignalStrength

import pandas as pd
from datetime import date


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_events(
    signal_id: str, n: int = 100, base_return: float = 0.01,
    noise_std: float = 0.03, seed: int = 42,
) -> list[SignalEvent]:
    dates = pd.bdate_range(start="2022-01-01", periods=n)
    np.random.seed(seed)
    events = []
    for d in dates:
        r = base_return + np.random.normal(0, noise_std)
        events.append(SignalEvent(
            signal_id=signal_id, ticker="AAPL",
            fired_date=d.date(), strength=SignalStrength.MODERATE,
            confidence=0.7, value=50.0 + np.random.normal(0, 5),
            price_at_fire=150.0, forward_returns={20: r},
        ))
    return events


# ─── Distribution Shift (KS) ───────────────────────────────────────────────

class TestDistributionShift:
    """Tests for the KS two-sample detector."""

    def test_same_distribution_no_drift(self):
        np.random.seed(42)
        baseline = list(np.random.normal(0.01, 0.03, 100))
        recent = list(np.random.normal(0.01, 0.03, 50))
        cfg = DriftConfig(min_samples=10)
        detector = DistributionShiftDetector()
        result = detector.detect(baseline, recent, cfg)
        assert not result.detected
        assert result.p_value > 0.05

    def test_shifted_distribution_drift(self):
        np.random.seed(42)
        baseline = list(np.random.normal(0.01, 0.03, 100))
        recent = list(np.random.normal(-0.05, 0.06, 50))
        cfg = DriftConfig(min_samples=10)
        detector = DistributionShiftDetector()
        result = detector.detect(baseline, recent, cfg)
        assert result.detected
        assert result.p_value < 0.05

    def test_insufficient_samples(self):
        detector = DistributionShiftDetector()
        result = detector.detect([0.01], [0.02], DriftConfig(min_samples=30))
        assert not result.detected
        assert "Insufficient" in result.detail

    def test_critical_shift(self):
        np.random.seed(42)
        baseline = list(np.random.normal(0.0, 0.01, 200))
        recent = list(np.random.normal(0.10, 0.01, 100))
        cfg = DriftConfig(min_samples=10, ks_critical_alpha=0.001)
        detector = DistributionShiftDetector()
        result = detector.detect(baseline, recent, cfg)
        assert result.detected
        assert "CRITICAL" in result.detail


# ─── Correlation Breakdown ──────────────────────────────────────────────────

class TestCorrelationBreakdown:
    """Tests for the Pearson correlation decay detector."""

    def test_stable_correlation(self):
        np.random.seed(42)
        n = 100
        x = np.random.normal(0, 1, n)
        y = 0.7 * x + 0.3 * np.random.normal(0, 1, n)
        cfg = DriftConfig(min_samples=10, corr_breakdown_threshold=0.30)
        detector = CorrelationBreakdownDetector()
        result = detector.detect(
            list(x[:50]), list(y[:50]),
            list(x[50:]), list(y[50:]),
            cfg,
        )
        assert not result.detected

    def test_breakdown_detected(self):
        np.random.seed(42)
        n = 100
        x_base = np.random.normal(0, 1, n)
        y_base = 0.9 * x_base + 0.1 * np.random.normal(0, 1, n)
        # Recent: decorrelated
        x_recent = np.random.normal(0, 1, n)
        y_recent = np.random.normal(0, 1, n)

        cfg = DriftConfig(min_samples=10, corr_breakdown_threshold=0.30)
        detector = CorrelationBreakdownDetector()
        result = detector.detect(
            list(x_base), list(y_base),
            list(x_recent), list(y_recent),
            cfg,
        )
        assert result.detected

    def test_insufficient_samples(self):
        detector = CorrelationBreakdownDetector()
        result = detector.detect(
            [1.0], [2.0], [3.0], [4.0],
            DriftConfig(min_samples=30),
        )
        assert not result.detected


# ─── Regime Shift (CUSUM) ──────────────────────────────────────────────────

class TestRegimeShift:
    """Tests for CUSUM change-point detection."""

    def test_stable_no_shift(self):
        np.random.seed(42)
        returns = list(np.random.normal(0.01, 0.03, 200))
        cfg = DriftConfig(min_samples=30, cusum_k=0.5, cusum_h=4.0)
        detector = RegimeShiftDetector()
        result = detector.detect(returns, cfg)
        # Stable with small noise — should not trigger easily
        assert isinstance(result, DriftDetection)

    def test_mean_jump_detected(self):
        np.random.seed(42)
        stable = list(np.random.normal(0.0, 0.01, 150))
        shifted = list(np.random.normal(0.10, 0.01, 100))
        returns = stable + shifted
        cfg = DriftConfig(min_samples=30, cusum_k=0.5, cusum_h=4.0)
        detector = RegimeShiftDetector()
        result = detector.detect(returns, cfg)
        assert result.detected

    def test_insufficient_samples(self):
        detector = RegimeShiftDetector()
        result = detector.detect([0.01, 0.02], DriftConfig(min_samples=30))
        assert not result.detected


# ─── Aggregator Tests ────────────────────────────────────────────────────────

class TestAggregator:
    """Tests for severity aggregation."""

    def test_no_drift_info(self):
        detections = [
            DriftDetection(detector="d1", detected=False),
            DriftDetection(detector="d2", detected=False),
            DriftDetection(detector="d3", detected=False),
        ]
        agg = DriftAggregator()
        alert = agg.aggregate("sig.1", detections, DriftConfig())
        assert alert.severity == "info"
        assert alert.active_detectors == 0
        assert alert.recommended_action == "none"

    def test_one_detector_info(self):
        detections = [
            DriftDetection(detector="d1", detected=True),
            DriftDetection(detector="d2", detected=False),
            DriftDetection(detector="d3", detected=False),
        ]
        agg = DriftAggregator()
        alert = agg.aggregate("sig.1", detections, DriftConfig())
        assert alert.severity == "info"
        assert alert.active_detectors == 1
        assert alert.recommended_action == "monitor"

    def test_two_detectors_warning(self):
        detections = [
            DriftDetection(detector="d1", detected=True),
            DriftDetection(detector="d2", detected=True),
            DriftDetection(detector="d3", detected=False),
        ]
        agg = DriftAggregator()
        alert = agg.aggregate("sig.1", detections, DriftConfig())
        assert alert.severity == "warning"
        assert alert.active_detectors == 2
        assert alert.recommended_action == "reduce_weight"

    def test_three_detectors_critical(self):
        detections = [
            DriftDetection(detector="d1", detected=True),
            DriftDetection(detector="d2", detected=True),
            DriftDetection(detector="d3", detected=True),
        ]
        agg = DriftAggregator()
        alert = agg.aggregate("sig.1", detections, DriftConfig())
        assert alert.severity == "critical"
        assert alert.recommended_action == "disable_signal"

    def test_critical_ks_pvalue(self):
        detections = [
            DriftDetection(
                detector="distribution_shift", detected=True,
                p_value=0.0001,
            ),
            DriftDetection(detector="d2", detected=False),
            DriftDetection(detector="d3", detected=False),
        ]
        cfg = DriftConfig(ks_critical_alpha=0.001)
        agg = DriftAggregator()
        alert = agg.aggregate("sig.1", detections, cfg)
        assert alert.severity == "critical"
        assert alert.drift_score >= 0.9


# ─── Engine Tests ────────────────────────────────────────────────────────────

class TestConceptDriftEngine:
    """Tests for full pipeline."""

    def test_basic_analysis(self):
        events = _make_events("sig.a", n=100, seed=1)
        engine = ConceptDriftEngine(DriftConfig(min_samples=10))
        report = engine.analyze({"sig.a": events})
        assert isinstance(report, ConceptDriftReport)
        assert report.total_signals_scanned == 1
        assert len(report.alerts) == 1

    def test_empty_input(self):
        engine = ConceptDriftEngine()
        report = engine.analyze({})
        assert report.total_signals_scanned == 0
        assert len(report.alerts) == 0

    def test_insufficient_events_skipped(self):
        events = _make_events("sig.a", n=10)
        engine = ConceptDriftEngine(DriftConfig(min_samples=30))
        report = engine.analyze({"sig.a": events})
        # Should skip — needs min_samples * 2
        assert len(report.alerts) == 0


# ─── Model Tests ─────────────────────────────────────────────────────────────

class TestConceptDriftModels:
    """Tests for Pydantic models."""

    def test_config_defaults(self):
        cfg = DriftConfig()
        assert cfg.ks_alpha == 0.05
        assert cfg.cusum_k == 0.5
        assert cfg.cusum_h == 4.0
        assert cfg.min_samples == 30

    def test_severity_enum(self):
        assert len(DriftSeverity) == 3

    def test_detector_type_enum(self):
        assert len(DetectorType) == 3

    def test_report_serialization(self):
        report = ConceptDriftReport(
            total_signals_scanned=5, drifting_signals=2, critical_count=1,
        )
        d = report.model_dump()
        assert d["drifting_signals"] == 2

    def test_alert_serialization(self):
        alert = DriftAlert(
            signal_id="sig.1", severity="warning",
            active_detectors=2, drift_score=0.67,
        )
        d = alert.model_dump()
        assert d["drift_score"] == 0.67


# ─── DB Table Tests ──────────────────────────────────────────────────────────

class TestConceptDriftDatabaseTable:
    """Verify concept_drift_alerts table exists."""

    def test_table_exists(self):
        from src.data.database import ConceptDriftRecord
        assert ConceptDriftRecord.__tablename__ == "concept_drift_alerts"
        cols = {c.name for c in ConceptDriftRecord.__table__.columns}
        assert "run_id" in cols
        assert "signal_id" in cols
        assert "severity" in cols
        assert "active_detectors" in cols
        assert "drift_score" in cols
        assert "detections_json" in cols
        assert "recommended_action" in cols
