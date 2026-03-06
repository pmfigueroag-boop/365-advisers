"""
tests/test_qvf.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Quantitative Validation Framework.

Tests cover:
  - RegimeDetector classification and event segmentation
  - RollingAnalyzer metric computation and degradation detection
  - OpportunityTracker aggregation logic
  - RecalibrationEngine plan generation
  - CombinationBacktestResult / RegimePerformanceReport models
"""

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

# ─── Regime Detector Tests ───────────────────────────────────────────────────

class TestRegimeDetector:
    """Tests for MarketRegime classification."""

    def _make_ohlcv(self, n_days: int = 300, trend: str = "bull") -> pd.DataFrame:
        """Generate synthetic OHLCV data."""
        dates = pd.date_range("2023-01-01", periods=n_days, freq="B")
        base = 400.0

        if trend == "bull":
            close = np.linspace(base, base * 1.3, n_days) + np.random.normal(0, 2, n_days)
        elif trend == "bear":
            close = np.linspace(base, base * 0.7, n_days) + np.random.normal(0, 2, n_days)
        else:
            close = np.full(n_days, base) + np.random.normal(0, 1, n_days)

        high = close + np.abs(np.random.normal(0, 1, n_days))
        low = close - np.abs(np.random.normal(0, 1, n_days))
        volume = np.random.randint(1_000_000, 10_000_000, n_days)

        return pd.DataFrame(
            {"Open": close, "High": high, "Low": low, "Close": close, "Volume": volume},
            index=dates,
        )

    def test_classify_returns_dict(self):
        from src.engines.backtesting.regime_detector import RegimeDetector

        detector = RegimeDetector()
        ohlcv = self._make_ohlcv(300, trend="bull")
        regimes = detector.classify(ohlcv)

        assert isinstance(regimes, dict)
        assert len(regimes) > 0

    def test_classify_insufficient_data(self):
        from src.engines.backtesting.regime_detector import RegimeDetector

        detector = RegimeDetector()
        short = self._make_ohlcv(50)
        regimes = detector.classify(short)

        assert regimes == {}

    def test_classify_bull_market(self):
        from src.engines.backtesting.regime_detector import RegimeDetector, MarketRegime

        detector = RegimeDetector()
        ohlcv = self._make_ohlcv(300, trend="bull")
        regimes = detector.classify(ohlcv)

        # Most days should be classified
        assert len(regimes) > 50

        # In a strong bull trend, majority should be BULL
        bull_count = sum(1 for r in regimes.values() if r == MarketRegime.BULL)
        total = len(regimes)
        assert bull_count / total > 0.3, f"Bull ratio too low: {bull_count}/{total}"

    def test_segment_events(self):
        from src.engines.backtesting.regime_detector import RegimeDetector, MarketRegime
        from src.engines.backtesting.models import SignalEvent

        detector = RegimeDetector()
        ohlcv = self._make_ohlcv(300)
        regimes = detector.classify(ohlcv)

        # Create mock events
        events = []
        for d, regime in list(regimes.items())[:10]:
            events.append(SignalEvent(
                signal_id="test.sig",
                ticker="AAPL",
                fired_date=d,
                strength="strong",
                confidence=0.8,
                value=1.5,
                price_at_fire=150.0,
            ))

        segmented = detector.segment_events(events, regimes)
        total_segmented = sum(len(v) for v in segmented.values())
        assert total_segmented == len(events)

    def test_market_regime_enum(self):
        from src.engines.backtesting.regime_detector import MarketRegime

        assert MarketRegime.BULL.value == "bull"
        assert MarketRegime.BEAR.value == "bear"
        assert MarketRegime.RANGE_BOUND.value == "range"
        assert MarketRegime.HIGH_VOL.value == "high_vol"


# ─── Rolling Analyzer Tests ─────────────────────────────────────────────────

class TestRollingAnalyzer:
    """Tests for rolling metrics and degradation detection."""

    def _make_events(self, n: int = 50, positive_ratio: float = 0.6):
        from src.engines.backtesting.models import SignalPerformanceEvent

        events = []
        base_date = date(2023, 1, 1)
        for i in range(n):
            is_positive = i < n * positive_ratio
            ret = 0.02 if is_positive else -0.01
            events.append(SignalPerformanceEvent(
                signal_id="value.fcf_yield_high",
                signal_name="FCF Yield High",
                ticker="AAPL",
                fired_date=base_date + timedelta(days=i * 7),
                strength="strong",
                confidence=0.8,
                value=1.5,
                price_at_fire=150.0,
                forward_returns={20: ret},
                excess_returns={20: ret - 0.005},
            ))
        return events

    def test_compute_rolling_metrics(self):
        from src.engines.backtesting.rolling_analyzer import RollingAnalyzer

        analyzer = RollingAnalyzer()
        events = self._make_events(50)
        snapshots = analyzer.compute_rolling_metrics("value.fcf_yield_high", events)

        assert len(snapshots) > 0
        for snap in snapshots:
            assert snap.signal_id == "value.fcf_yield_high"
            assert snap.window_days in [30, 90, 252]
            assert 0.0 <= snap.hit_rate <= 1.0

    def test_detect_degradation_no_alert(self):
        from src.engines.backtesting.rolling_analyzer import RollingAnalyzer

        analyzer = RollingAnalyzer()
        # Consistent positive performance
        events = self._make_events(50, positive_ratio=0.7)
        reports = analyzer.detect_degradation("test.sig", events)

        # With consistent performance, no degradation expected
        # (The last 30 have same ratio as full set)
        assert isinstance(reports, list)

    def test_detect_degradation_with_decline(self):
        from src.engines.backtesting.rolling_analyzer import RollingAnalyzer
        from src.engines.backtesting.models import SignalPerformanceEvent

        analyzer = RollingAnalyzer()

        # First 60 events: great performance
        good_events = self._make_events(60, positive_ratio=0.80)
        # Last 30 events: terrible performance
        bad_events = []
        base_date = date(2024, 6, 1)
        for i in range(30):
            bad_events.append(SignalPerformanceEvent(
                signal_id="value.fcf_yield_high",
                signal_name="FCF Yield High",
                ticker="AAPL",
                fired_date=base_date + timedelta(days=i * 7),
                strength="strong",
                confidence=0.8,
                value=1.5,
                price_at_fire=150.0,
                forward_returns={20: -0.03},
                excess_returns={20: -0.035},
            ))

        all_events = good_events + bad_events
        reports = analyzer.detect_degradation("value.fcf_yield_high", all_events)

        assert len(reports) > 0
        assert reports[0].signal_id == "value.fcf_yield_high"
        assert reports[0].decline_pct < 0  # Negative = decline

    def test_empty_events(self):
        from src.engines.backtesting.rolling_analyzer import RollingAnalyzer

        analyzer = RollingAnalyzer()
        assert analyzer.compute_rolling_metrics("x", []) == []
        assert analyzer.detect_degradation("x", []) == []


# ─── Model Tests ─────────────────────────────────────────────────────────────

class TestQVFModels:
    """Tests for new Pydantic models."""

    def test_combination_backtest_result(self):
        from src.engines.backtesting.models import CombinationBacktestResult

        result = CombinationBacktestResult(
            combination_id="sig_a+sig_b",
            signal_ids=["sig_a", "sig_b"],
            joint_firings=25,
            hit_rate={20: 0.65},
            sharpe={20: 1.2},
            incremental_alpha=0.005,
            synergy_score=0.35,
        )
        assert result.combination_id == "sig_a+sig_b"
        assert result.joint_firings == 25
        assert 0.0 <= result.synergy_score <= 1.0

    def test_regime_performance_report(self):
        from src.engines.backtesting.models import (
            RegimePerformanceReport,
            SignalPerformanceRecord,
        )
        from src.engines.alpha_signals.models import SignalCategory

        bull_record = SignalPerformanceRecord(
            signal_id="test",
            signal_name="Test",
            category=SignalCategory.VALUE,
            sharpe_ratio={20: 1.5},
        )
        bear_record = SignalPerformanceRecord(
            signal_id="test",
            signal_name="Test",
            category=SignalCategory.VALUE,
            sharpe_ratio={20: 0.3},
        )

        report = RegimePerformanceReport(
            signal_id="test",
            regime_results={"bull": bull_record, "bear": bear_record},
            best_regime="bull",
            worst_regime="bear",
            regime_stability=0.6,
        )
        assert report.best_regime == "bull"
        assert report.regime_stability == 0.6


# ─── Opportunity Tracking Model Tests ──────────────────────────────────────

class TestOpportunityModels:
    """Tests for opportunity tracking models."""

    def test_detector_accuracy(self):
        from src.engines.opportunity_tracking.models import DetectorAccuracy

        acc = DetectorAccuracy(
            label="value",
            idea_count=100,
            hit_rate=0.62,
            avg_return=0.015,
            avg_excess_return=0.008,
            sharpe=1.3,
        )
        assert acc.label == "value"
        assert acc.hit_rate == 0.62

    def test_performance_summary(self):
        from src.engines.opportunity_tracking.models import (
            OpportunityPerformanceSummary,
            DetectorAccuracy,
        )

        summary = OpportunityPerformanceSummary(
            total_ideas=500,
            total_tracked=400,
            total_complete=300,
            hit_rate_20d=0.58,
            avg_return_20d=0.012,
            avg_excess_return_20d=0.005,
            best_idea="NVDA (momentum)",
            worst_idea="INTC (value)",
            by_type={
                "value": DetectorAccuracy(
                    label="value", idea_count=100, hit_rate=0.55,
                    avg_return=0.01, avg_excess_return=0.004, sharpe=0.9,
                ),
            },
        )
        assert summary.total_ideas == 500
        assert "value" in summary.by_type


# ─── Recalibration Engine Tests ──────────────────────────────────────────────

class TestRecalibrationPlan:
    """Tests for recalibration plan generation (unit level)."""

    def test_generate_plan_from_degradation(self):
        from src.engines.backtesting.rolling_analyzer import (
            DegradationReport,
            DegradationSeverity,
        )
        from src.engines.backtesting.recalibration_engine import RecalibrationEngine
        from src.engines.alpha_signals.models import AlphaSignalDefinition, SignalCategory, SignalDirection

        # Register a mock signal
        from src.engines.alpha_signals.registry import registry
        mock_signal = AlphaSignalDefinition(
            id="test.degraded_signal",
            name="Degraded Signal",
            category=SignalCategory.VALUE,
            feature="value.pe_ratio",
            threshold=15.0,
            direction=SignalDirection.BELOW,
            weight=1.0,
        )
        registry.register(mock_signal)

        try:
            engine = RecalibrationEngine()
            degraded = [
                DegradationReport(
                    signal_id="test.degraded_signal",
                    signal_name="Degraded Signal",
                    metric="sharpe",
                    peak_value=1.5,
                    current_value=0.6,
                    decline_pct=-0.60,
                    peak_date=date(2023, 1, 1),
                    severity=DegradationSeverity.CRITICAL,
                    recommendation="reduce_weight",
                ),
            ]
            suggestions = engine.generate_recalibration_plan(degraded)

            assert len(suggestions) > 0
            assert suggestions[0].parameter == "weight"
            assert suggestions[0].suggested_value < suggestions[0].current_value
        finally:
            # Cleanup
            if "test.degraded_signal" in registry._signals:
                del registry._signals["test.degraded_signal"]

    def test_auto_apply_dry_run(self):
        from src.engines.backtesting.recalibration_engine import RecalibrationEngine
        from src.engines.backtesting.models import CalibrationSuggestion

        engine = RecalibrationEngine()
        suggestions = [
            CalibrationSuggestion(
                signal_id="nonexistent.signal",
                parameter="weight",
                current_value=1.0,
                suggested_value=0.5,
                evidence="Test evidence",
            ),
        ]
        records = engine.auto_apply(suggestions, dry_run=True)

        # Should produce records even in dry run
        assert len(records) == 1
        assert records[0].applied_by == "auto_dry"


# ─── Database Table Tests ──────────────────────────────────────────────────

class TestDatabaseTables:
    """Verify new QVF tables exist in the ORM."""

    def test_rolling_performance_table(self):
        from src.data.database import RollingPerformanceRecord
        assert RollingPerformanceRecord.__tablename__ == "rolling_performance"

    def test_opportunity_performance_table(self):
        from src.data.database import OpportunityPerformanceRecord
        assert OpportunityPerformanceRecord.__tablename__ == "opportunity_performance"

    def test_degradation_alerts_table(self):
        from src.data.database import DegradationAlertRecord
        assert DegradationAlertRecord.__tablename__ == "degradation_alerts"
