"""
tests/test_walk_forward.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Walk-Forward Validation Engine.

Covers:
  - WindowGenerator (rolling + anchored modes)
  - StabilityAnalyzer (component scores and classification)
  - Pydantic models (serialisation, defaults)
  - DB table definitions
"""

from __future__ import annotations

from datetime import date

import pytest

from src.engines.alpha_signals.models import SignalCategory
from src.engines.walk_forward.models import (
    StabilityClassification,
    WalkForwardConfig,
    WalkForwardFold,
    WalkForwardMode,
    WalkForwardRun,
    WFSignalFoldResult,
    WFSignalSummary,
)
from src.engines.walk_forward.stability_analyzer import (
    StabilityAnalyzer,
    _classify_stability,
)
from src.engines.walk_forward.window_generator import WindowGenerator


# ─── Window Generator Tests ─────────────────────────────────────────────────

class TestWindowGenerator:
    """Tests for temporal fold generation."""

    def test_rolling_mode_generates_folds(self):
        config = WalkForwardConfig(
            universe=["AAPL"],
            start_date=date(2015, 1, 1),
            end_date=date(2025, 1, 1),
            train_days=756,   # ~3 years
            test_days=126,    # ~6 months
            mode=WalkForwardMode.ROLLING,
        )
        gen = WindowGenerator()
        folds = gen.generate(config)

        assert len(folds) >= 1
        assert all(isinstance(f, WalkForwardFold) for f in folds)
        # Folds should be ordered
        for i in range(len(folds) - 1):
            assert folds[i].fold_index < folds[i + 1].fold_index
        # Train end should be before test start
        for f in folds:
            assert f.train_end < f.test_start
            assert f.train_start < f.train_end
            assert f.test_start <= f.test_end

    def test_anchored_mode_has_fixed_start(self):
        config = WalkForwardConfig(
            universe=["AAPL"],
            start_date=date(2015, 1, 1),
            end_date=date(2025, 1, 1),
            train_days=756,
            test_days=126,
            mode=WalkForwardMode.ANCHORED,
        )
        gen = WindowGenerator()
        folds = gen.generate(config)

        assert len(folds) >= 1
        # In anchored mode, all folds should start at the same date
        for f in folds:
            assert f.train_start == date(2015, 1, 1)
        # Train window should grow (or stay same for last)
        if len(folds) > 1:
            assert folds[-1].train_end >= folds[0].train_end

    def test_no_folds_when_range_too_short(self):
        config = WalkForwardConfig(
            universe=["AAPL"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 1),   # Only ~5 months
            train_days=756,               # 3 years needed
            test_days=126,
        )
        gen = WindowGenerator()
        folds = gen.generate(config)
        assert len(folds) == 0

    def test_custom_step_days(self):
        config = WalkForwardConfig(
            universe=["AAPL"],
            start_date=date(2015, 1, 1),
            end_date=date(2025, 1, 1),
            train_days=756,
            test_days=126,
            step_days=63,  # ~3 month step (more overlap)
        )
        gen = WindowGenerator()
        folds = gen.generate(config)
        # With smaller step, should get more folds
        assert len(folds) >= 2

    def test_no_overlapping_test_windows(self):
        config = WalkForwardConfig(
            universe=["AAPL"],
            start_date=date(2015, 1, 1),
            end_date=date(2025, 1, 1),
            train_days=756,
            test_days=126,
        )
        gen = WindowGenerator()
        folds = gen.generate(config)

        for f in folds:
            assert f.test_end <= config.end_date


# ─── Stability Analyzer Tests ───────────────────────────────────────────────

class TestStabilityAnalyzer:
    """Tests for cross-fold stability scoring."""

    def _make_fold_results(
        self,
        signal_id: str = "test.signal",
        n_folds: int = 8,
        qualified_ratio: float = 1.0,
        oos_hit_rates: list[float] | None = None,
        oos_sharpes: list[float] | None = None,
        oos_alphas: list[float] | None = None,
    ) -> list[WFSignalFoldResult]:
        """Helper to create synthetic fold results."""
        results = []
        for i in range(n_folds):
            qualified = i < int(n_folds * qualified_ratio)
            result = WFSignalFoldResult(
                signal_id=signal_id,
                signal_name="Test Signal",
                fold_index=i,
                is_hit_rate=0.60,
                is_sharpe=0.80,
                is_alpha=0.005,
                is_firings=50,
                qualified=qualified,
            )
            if qualified and oos_hit_rates:
                idx = min(i, len(oos_hit_rates) - 1)
                result.oos_hit_rate = oos_hit_rates[idx]
                result.oos_sharpe = oos_sharpes[idx] if oos_sharpes else 0.5
                result.oos_alpha = oos_alphas[idx] if oos_alphas else 0.005
                result.oos_firings = 20
            results.append(result)
        return results

    def test_robust_signal(self):
        # All folds positive, consistent
        results = self._make_fold_results(
            n_folds=8,
            oos_hit_rates=[0.65, 0.60, 0.58, 0.62, 0.55, 0.63, 0.59, 0.61],
            oos_sharpes=[1.2, 1.1, 0.9, 1.0, 0.8, 1.3, 1.0, 1.1],
            oos_alphas=[0.01, 0.008, 0.005, 0.007, 0.003, 0.012, 0.006, 0.009],
        )
        analyzer = StabilityAnalyzer()
        summaries = analyzer.analyze(
            results,
            {"test.signal": ("Test Signal", SignalCategory.MOMENTUM)},
            total_folds=8,
        )
        assert len(summaries) == 1
        s = summaries[0]
        assert s.stability_class == StabilityClassification.ROBUST
        assert s.stability_score >= 0.75
        assert s.consistency_ratio == 1.0  # All folds > 50%
        assert s.alpha_persistence == 1.0  # All alphas > 0

    def test_overfit_signal(self):
        # Inconsistent OOS performance
        results = self._make_fold_results(
            n_folds=8,
            qualified_ratio=0.375,   # Only 3/8 qualified
            oos_hit_rates=[0.40, 0.35, 0.45],
            oos_sharpes=[-0.5, -0.3, 0.1],
            oos_alphas=[-0.01, -0.005, 0.001],
        )
        analyzer = StabilityAnalyzer()
        summaries = analyzer.analyze(
            results,
            {"test.signal": ("Test Signal", SignalCategory.VALUE)},
            total_folds=8,
        )
        assert len(summaries) == 1
        s = summaries[0]
        assert s.stability_class == StabilityClassification.OVERFIT
        assert s.stability_score < 0.25

    def test_classify_stability_boundaries(self):
        assert _classify_stability(0.75) == StabilityClassification.ROBUST
        assert _classify_stability(0.80) == StabilityClassification.ROBUST
        assert _classify_stability(0.50) == StabilityClassification.MODERATE
        assert _classify_stability(0.74) == StabilityClassification.MODERATE
        assert _classify_stability(0.25) == StabilityClassification.WEAK
        assert _classify_stability(0.49) == StabilityClassification.WEAK
        assert _classify_stability(0.24) == StabilityClassification.OVERFIT
        assert _classify_stability(0.0) == StabilityClassification.OVERFIT

    def test_consistency_ratio(self):
        analyzer = StabilityAnalyzer()
        assert analyzer._consistency_ratio([0.6, 0.7, 0.3, 0.8]) == 0.75
        assert analyzer._consistency_ratio([0.3, 0.4]) == 0.0
        assert analyzer._consistency_ratio([]) == 0.0

    def test_sharpe_stability(self):
        analyzer = StabilityAnalyzer()
        # Identical Sharpes → CV=0 → stability=1.0
        assert analyzer._sharpe_stability([1.0, 1.0, 1.0]) == 1.0
        # Single value → 0.0
        assert analyzer._sharpe_stability([1.0]) == 0.0
        # Empty → 0.0
        assert analyzer._sharpe_stability([]) == 0.0

    def test_alpha_persistence(self):
        analyzer = StabilityAnalyzer()
        assert analyzer._alpha_persistence([0.01, 0.02, -0.01, 0.005]) == 0.75
        assert analyzer._alpha_persistence([-0.01, -0.02]) == 0.0
        assert analyzer._alpha_persistence([]) == 0.0


# ─── Model Tests ─────────────────────────────────────────────────────────────

class TestWFModels:
    """Tests for Pydantic model contracts."""

    def test_config_defaults(self):
        cfg = WalkForwardConfig(
            universe=["AAPL"],
            start_date=date(2015, 1, 1),
        )
        assert cfg.train_days == 756
        assert cfg.test_days == 126
        assert cfg.mode == WalkForwardMode.ROLLING
        assert cfg.effective_step_days == 126
        assert cfg.benchmark_ticker == "SPY"
        assert cfg.is_hit_rate_threshold == 0.50

    def test_config_custom_step(self):
        cfg = WalkForwardConfig(
            universe=["AAPL"],
            start_date=date(2015, 1, 1),
            step_days=63,
        )
        assert cfg.effective_step_days == 63

    def test_fold_result_serialisation(self):
        fr = WFSignalFoldResult(
            signal_id="value.fcf_yield_high",
            signal_name="FCF Yield High",
            fold_index=0,
            is_hit_rate=0.65,
            is_sharpe=1.2,
            is_alpha=0.008,
            is_firings=42,
            qualified=True,
            oos_hit_rate=0.58,
            oos_sharpe=0.9,
            oos_alpha=0.005,
            oos_firings=15,
        )
        d = fr.model_dump()
        assert d["signal_id"] == "value.fcf_yield_high"
        assert d["qualified"] is True
        assert d["oos_hit_rate"] == 0.58

    def test_signal_summary_defaults(self):
        s = WFSignalSummary(
            signal_id="test",
            category=SignalCategory.VALUE,
        )
        assert s.stability_score == 0.0
        assert s.stability_class == StabilityClassification.OVERFIT
        assert s.fold_results == []

    def test_run_has_uuid(self):
        cfg = WalkForwardConfig(
            universe=["AAPL"],
            start_date=date(2015, 1, 1),
        )
        run = WalkForwardRun(config=cfg)
        assert len(run.run_id) == 36  # UUID format


# ─── DB Table Tests ──────────────────────────────────────────────────────────

class TestWFDatabaseTables:
    """Verify walk-forward tables exist in the ORM."""

    def test_walk_forward_runs_table(self):
        from src.data.database import WalkForwardRunRecord
        assert WalkForwardRunRecord.__tablename__ == "walk_forward_runs"
        cols = {c.name for c in WalkForwardRunRecord.__table__.columns}
        assert "run_id" in cols
        assert "config_json" in cols
        assert "total_folds" in cols
        assert "robust_signals_json" in cols
        assert "status" in cols

    def test_walk_forward_folds_table(self):
        from src.data.database import WalkForwardFoldRecord
        assert WalkForwardFoldRecord.__tablename__ == "walk_forward_folds"
        cols = {c.name for c in WalkForwardFoldRecord.__table__.columns}
        assert "run_id" in cols
        assert "fold_index" in cols
        assert "train_start" in cols
        assert "test_end" in cols

    def test_walk_forward_signal_results_table(self):
        from src.data.database import WalkForwardSignalResultRecord
        assert WalkForwardSignalResultRecord.__tablename__ == "walk_forward_signal_results"
        cols = {c.name for c in WalkForwardSignalResultRecord.__table__.columns}
        assert "fold_id" in cols
        assert "signal_id" in cols
        assert "is_hit_rate" in cols
        assert "oos_hit_rate" in cols
        assert "qualified" in cols
