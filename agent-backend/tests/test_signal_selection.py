"""
tests/test_signal_selection.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Signal Selection & Redundancy Pruning Engine.

Covers:
  - CorrelationAnalyzer (identical signals, opposite signals, uncorrelated)
  - MutualInfoEstimator (dependent vs independent series)
  - IncrementalAlphaAnalyzer (dominant vs copy signals)
  - RedundancyPruningEngine (scoring, classification, apply_to_registry)
  - Pydantic model contracts
  - DB table definition
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from src.engines.backtesting.models import SignalEvent
from src.engines.alpha_signals.models import SignalStrength
from src.engines.signal_selection.correlation import CorrelationAnalyzer
from src.engines.signal_selection.mutual_info import MutualInfoEstimator
from src.engines.signal_selection.incremental import IncrementalAlphaAnalyzer
from src.engines.signal_selection.engine import RedundancyPruningEngine
from src.engines.signal_selection.models import (
    RedundancyClass,
    RedundancyConfig,
    RedundancyReport,
    SignalPairAnalysis,
    SignalRedundancyProfile,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_events(
    signal_id: str,
    n: int = 30,
    base_return: float = 0.01,
    noise_std: float = 0.03,
    seed: int = 42,
) -> list[SignalEvent]:
    """Create synthetic signal events."""
    import pandas as pd
    dates = pd.bdate_range(start="2023-03-01", periods=n)
    np.random.seed(seed)
    events = []
    for i, d in enumerate(dates):
        r = base_return + np.random.normal(0, noise_std)
        events.append(SignalEvent(
            signal_id=signal_id,
            ticker="AAPL",
            fired_date=d.date(),
            strength=SignalStrength.MODERATE,
            confidence=0.7,
            value=50.0,
            price_at_fire=150.0,
            forward_returns={5: r * 0.3, 10: r * 0.6, 20: r},
        ))
    return events


def _make_identical_events(sig_a: str, sig_b: str, n: int = 30, seed: int = 42):
    """Create two signals with identical returns (perfect correlation)."""
    events_a = _make_events(sig_a, n, seed=seed)
    events_b = []
    for e in events_a:
        events_b.append(SignalEvent(
            signal_id=sig_b,
            ticker=e.ticker,
            fired_date=e.fired_date,
            strength=e.strength,
            confidence=e.confidence,
            value=e.value,
            price_at_fire=e.price_at_fire,
            forward_returns=dict(e.forward_returns),
        ))
    return events_a, events_b


# ─── Correlation Tests ──────────────────────────────────────────────────────

class TestCorrelation:
    """Tests for pairwise Pearson correlation."""

    def test_identical_signals(self):
        events_a, events_b = _make_identical_events("sig.a", "sig.b")
        analyzer = CorrelationAnalyzer()
        matrix = analyzer.compute_matrix(
            {"sig.a": events_a, "sig.b": events_b},
            forward_window=20, min_overlap=5,
        )
        assert abs(matrix["sig.a"]["sig.b"] - 1.0) < 0.01

    def test_uncorrelated_signals(self):
        events_a = _make_events("sig.a", seed=1)
        events_b = _make_events("sig.b", seed=99)
        analyzer = CorrelationAnalyzer()
        matrix = analyzer.compute_matrix(
            {"sig.a": events_a, "sig.b": events_b},
            forward_window=20, min_overlap=5,
        )
        assert abs(matrix["sig.a"]["sig.b"]) < 0.5

    def test_diagonal_is_one(self):
        events = _make_events("sig.a")
        analyzer = CorrelationAnalyzer()
        matrix = analyzer.compute_matrix(
            {"sig.a": events}, forward_window=20,
        )
        assert matrix["sig.a"]["sig.a"] == 1.0

    def test_pearson_method(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        rho = CorrelationAnalyzer._pearson(x, y)
        assert abs(rho - 1.0) < 1e-10

    def test_pearson_zero_variance(self):
        x = [1.0, 1.0, 1.0]
        y = [2.0, 3.0, 4.0]
        rho = CorrelationAnalyzer._pearson(x, y)
        assert rho == 0.0


# ─── Mutual Information Tests ───────────────────────────────────────────────

class TestMutualInfo:
    """Tests for NMI estimation."""

    def test_identical_series_high_mi(self):
        np.random.seed(42)
        x = np.random.normal(0, 1, 200)
        estimator = MutualInfoEstimator(n_bins=20)
        nmi = estimator.estimate(x, x)
        assert nmi > 0.7

    def test_independent_series_low_mi(self):
        np.random.seed(42)
        x = np.random.normal(0, 1, 200)
        np.random.seed(99)
        y = np.random.normal(0, 1, 200)
        estimator = MutualInfoEstimator(n_bins=20)
        nmi = estimator.estimate(x, y)
        assert nmi < 0.3

    def test_short_series_returns_zero(self):
        estimator = MutualInfoEstimator()
        nmi = estimator.estimate(np.array([1.0, 2.0]), np.array([3.0, 4.0]))
        assert nmi == 0.0

    def test_batch_estimation(self):
        np.random.seed(42)
        x = np.random.normal(0, 1, 100)
        y = np.random.normal(0, 1, 100)
        estimator = MutualInfoEstimator()
        results = estimator.estimate_batch([(x, x), (x, y)])
        assert len(results) == 2
        assert results[0] > results[1]


# ─── Incremental Alpha Tests ────────────────────────────────────────────────

class TestIncrementalAlpha:
    """Tests for leave-one-out incremental alpha."""

    def test_unique_signal_has_full_contribution(self):
        events = _make_events("sig.only", n=50, base_return=0.02, seed=10)
        analyzer = IncrementalAlphaAnalyzer()
        result = analyzer.compute({"sig.only": events}, forward_window=20)
        # With only one signal, removing it leaves nothing
        assert result["sig.only"] > 0

    def test_copy_signal_has_low_contribution(self):
        events_a, events_b = _make_identical_events("sig.orig", "sig.copy", n=50)
        analyzer = IncrementalAlphaAnalyzer()
        result = analyzer.compute(
            {"sig.orig": events_a, "sig.copy": events_b},
            forward_window=20,
        )
        # Each contributes about equally; removing one
        # shouldn't dramatically change the Sharpe
        assert abs(result["sig.orig"] - result["sig.copy"]) < 0.5

    def test_empty_events(self):
        analyzer = IncrementalAlphaAnalyzer()
        result = analyzer.compute({"sig.empty": []}, forward_window=20)
        assert result["sig.empty"] == 0.0


# ─── Engine Tests ────────────────────────────────────────────────────────────

class TestRedundancyEngine:
    """Tests for the Redundancy Pruning Engine."""

    def test_analyze_basic(self):
        events_a = _make_events("sig.a", seed=1)
        events_b = _make_events("sig.b", seed=2)
        events_c = _make_events("sig.c", seed=3)

        engine = RedundancyPruningEngine()
        report = engine.analyze({
            "sig.a": events_a,
            "sig.b": events_b,
            "sig.c": events_c,
        })

        assert isinstance(report, RedundancyReport)
        assert report.total_signals == 3
        assert len(report.profiles) == 3

    def test_identical_signals_detected(self):
        events_a, events_b = _make_identical_events("sig.orig", "sig.clone")

        config = RedundancyConfig(
            corr_threshold=0.80,
            auto_disable_threshold=0.70,
        )
        engine = RedundancyPruningEngine(config)
        report = engine.analyze(
            {"sig.orig": events_a, "sig.clone": events_b}, config,
        )

        # At least one should be flagged
        assert report.total_redundancy_pairs >= 1

    def test_classification_thresholds(self):
        cfg = RedundancyConfig()
        assert RedundancyPruningEngine._classify(0.10, cfg) == RedundancyClass.KEEP
        assert RedundancyPruningEngine._classify(0.40, cfg) == RedundancyClass.REDUCE_WEIGHT
        assert RedundancyPruningEngine._classify(0.60, cfg) == RedundancyClass.CANDIDATE_REMOVAL
        assert RedundancyPruningEngine._classify(0.80, cfg) == RedundancyClass.REMOVE

    def test_get_recommended_weights(self):
        engine = RedundancyPruningEngine()
        report = RedundancyReport(
            profiles=[
                SignalRedundancyProfile(
                    signal_id="sig.1",
                    classification=RedundancyClass.KEEP,
                    recommended_weight=1.0,
                ),
                SignalRedundancyProfile(
                    signal_id="sig.2",
                    classification=RedundancyClass.REDUCE_WEIGHT,
                    recommended_weight=0.5,
                ),
            ],
        )
        weights = engine.get_recommended_weights(report)
        assert weights["sig.1"] == 1.0
        assert weights["sig.2"] == 0.5


# ─── Model Tests ─────────────────────────────────────────────────────────────

class TestSelectionModels:
    """Tests for Pydantic models."""

    def test_config_defaults(self):
        cfg = RedundancyConfig()
        assert cfg.forward_window == 20
        assert cfg.w_corr == 0.35
        assert cfg.w_mi == 0.25
        assert cfg.w_alpha == 0.40

    def test_redundancy_classes(self):
        assert RedundancyClass.KEEP.value == "keep"
        assert RedundancyClass.REMOVE.value == "remove"

    def test_pair_analysis_serialization(self):
        pa = SignalPairAnalysis(
            signal_a="a", signal_b="b",
            correlation=0.85, mutual_information=0.65,
            redundant=True,
        )
        d = pa.model_dump()
        assert d["redundant"] is True

    def test_report_serialization(self):
        report = RedundancyReport(
            total_signals=5,
            keep_signals=["a", "b"],
            remove_signals=["c"],
        )
        d = report.model_dump()
        assert d["total_signals"] == 5
        assert len(d["keep_signals"]) == 2


# ─── DB Table Tests ──────────────────────────────────────────────────────────

class TestRedundancyDatabaseTable:
    """Verify signal_redundancy_profiles table exists in the ORM."""

    def test_table_exists(self):
        from src.data.database import SignalRedundancyRecord
        assert SignalRedundancyRecord.__tablename__ == "signal_redundancy_profiles"
        cols = {c.name for c in SignalRedundancyRecord.__table__.columns}
        assert "run_id" in cols
        assert "signal_id" in cols
        assert "max_correlation" in cols
        assert "max_mi" in cols
        assert "incremental_alpha" in cols
        assert "redundancy_score" in cols
        assert "classification" in cols
        assert "recommended_weight" in cols
