"""
tests/test_signal_ensemble.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Signal Ensemble Intelligence module.

Covers:
  - CoFireAnalyzer (pair detection, tolerance, no overlap)
  - SynergyScorer (positive synergy, negative synergy, insufficient data)
  - StabilityAnalyzer (stable combo, rolling windows)
  - EnsembleIntelligenceEngine (full pipeline, ensemble bonus)
  - Pydantic model contracts
  - DB table definition
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.engines.backtesting.models import SignalEvent
from src.engines.alpha_signals.models import SignalStrength
from src.engines.signal_ensemble.co_fire import CoFireAnalyzer
from src.engines.signal_ensemble.synergy import SynergyScorer
from src.engines.signal_ensemble.stability import StabilityAnalyzer
from src.engines.signal_ensemble.engine import EnsembleIntelligenceEngine
from src.engines.signal_ensemble.models import (
    CoFireEvent,
    EnsembleConfig,
    EnsembleReport,
    SignalCombination,
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
    dates = pd.bdate_range(start="2023-03-01", periods=n)
    np.random.seed(seed)
    events = []
    for d in dates:
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


def _make_cofire_events(
    sig_a: str, sig_b: str, n: int = 20, seed: int = 42,
) -> tuple[list[SignalEvent], list[SignalEvent]]:
    """Two signals that fire on the same dates (perfect co-fire)."""
    events_a = _make_events(sig_a, n, seed=seed)
    events_b = []
    np.random.seed(seed + 1)
    for e in events_a:
        r = 0.015 + np.random.normal(0, 0.02)
        events_b.append(SignalEvent(
            signal_id=sig_b,
            ticker=e.ticker,
            fired_date=e.fired_date,
            strength=SignalStrength.MODERATE,
            confidence=0.7,
            value=50.0,
            price_at_fire=150.0,
            forward_returns={5: r * 0.3, 10: r * 0.6, 20: r},
        ))
    return events_a, events_b


# ─── Co-Fire Tests ──────────────────────────────────────────────────────────

class TestCoFire:
    """Tests for co-fire detection."""

    def test_identical_dates_match(self):
        events_a, events_b = _make_cofire_events("sig.a", "sig.b", n=15)
        analyzer = CoFireAnalyzer(date_tolerance=0)
        pairs = analyzer.detect_pairs(
            {"sig.a": events_a, "sig.b": events_b},
            forward_window=20, min_co_fires=5,
        )
        assert ("sig.a", "sig.b") in pairs
        assert len(pairs[("sig.a", "sig.b")]) == 15

    def test_tolerance_window(self):
        events_a, events_b = _make_cofire_events("sig.a", "sig.b", n=15)
        # Shift B dates by 1 day
        for e in events_b:
            from datetime import timedelta
            e.fired_date = e.fired_date + timedelta(days=1)

        analyzer = CoFireAnalyzer(date_tolerance=2)
        pairs = analyzer.detect_pairs(
            {"sig.a": events_a, "sig.b": events_b},
            forward_window=20, min_co_fires=5,
        )
        assert ("sig.a", "sig.b") in pairs
        assert len(pairs[("sig.a", "sig.b")]) > 0

    def test_no_overlap(self):
        events_a = _make_events("sig.a", n=10, seed=1)
        events_b = _make_events("sig.b", n=10, seed=2)
        # Different tickers
        for e in events_b:
            e.ticker = "MSFT"

        analyzer = CoFireAnalyzer()
        pairs = analyzer.detect_pairs(
            {"sig.a": events_a, "sig.b": events_b},
            forward_window=20, min_co_fires=5,
        )
        assert len(pairs) == 0

    def test_min_co_fires_threshold(self):
        events_a, events_b = _make_cofire_events("sig.a", "sig.b", n=5)
        analyzer = CoFireAnalyzer()
        pairs = analyzer.detect_pairs(
            {"sig.a": events_a, "sig.b": events_b},
            forward_window=20, min_co_fires=10,
        )
        assert len(pairs) == 0


# ─── Synergy Tests ──────────────────────────────────────────────────────────

class TestSynergy:
    """Tests for synergy scoring."""

    def test_score_computation(self):
        events_a, events_b = _make_cofire_events("sig.a", "sig.b")
        co_fires = [
            CoFireEvent(
                ticker="AAPL", date=ea.fired_date.isoformat(),
                signal_ids=["sig.a", "sig.b"],
                returns={"sig.a": ea.forward_returns[20], "sig.b": eb.forward_returns[20]},
                joint_return=(ea.forward_returns[20] + eb.forward_returns[20]) / 2,
            )
            for ea, eb in zip(events_a, events_b)
        ]

        scorer = SynergyScorer()
        combo = scorer.score(
            ["sig.a", "sig.b"], co_fires,
            {"sig.a": events_a, "sig.b": events_b},
            forward_window=20,
        )

        assert isinstance(combo, SignalCombination)
        assert combo.co_fire_count == len(events_a)
        assert combo.joint_sharpe != 0
        assert combo.joint_hit_rate >= 0

    def test_sharpe_method(self):
        returns = [0.01, 0.02, -0.005, 0.015, 0.008]
        sharpe = SynergyScorer._sharpe(returns)
        assert sharpe > 0

    def test_hit_rate_method(self):
        returns = [0.01, 0.02, -0.01, 0.03, -0.005]
        hr = SynergyScorer._hit_rate(returns)
        assert hr == 0.6

    def test_empty_returns(self):
        assert SynergyScorer._sharpe([]) == 0.0
        assert SynergyScorer._hit_rate([]) == 0.0


# ─── Stability Tests ───────────────────────────────────────────────────────

class TestStability:
    """Tests for rolling stability analysis."""

    def test_stable_combo(self):
        # Create co-fires spanning 2 years with positive returns
        np.random.seed(42)
        co_fires = []
        dates = pd.bdate_range("2022-01-01", "2023-12-31")
        for d in dates[::5]:
            co_fires.append(CoFireEvent(
                ticker="AAPL", date=d.date().isoformat(),
                signal_ids=["a", "b"],
                joint_return=0.01 + np.random.normal(0, 0.005),
            ))

        analyzer = StabilityAnalyzer(window_months=6, stride_months=1)
        stab, stable_w, total_w = analyzer.evaluate(co_fires, 0.0)
        assert stab > 0.5
        assert total_w > 0

    def test_insufficient_data(self):
        co_fires = [
            CoFireEvent(ticker="AAPL", date="2023-01-01",
                       signal_ids=["a", "b"], joint_return=0.01),
        ]
        analyzer = StabilityAnalyzer()
        stab, stable_w, total_w = analyzer.evaluate(co_fires)
        assert stab == 0.0

    def test_window_generation(self):
        analyzer = StabilityAnalyzer(window_months=3, stride_months=1)
        windows = analyzer._generate_windows(date(2023, 1, 1), date(2023, 12, 31))
        assert len(windows) > 0
        for start, end in windows:
            assert start < end


# ─── Engine Tests ────────────────────────────────────────────────────────────

class TestEnsembleEngine:
    """Tests for the full EnsembleIntelligenceEngine."""

    def test_basic_analysis(self):
        events_a, events_b = _make_cofire_events("sig.a", "sig.b", n=20)
        events_c = _make_events("sig.c", n=20, seed=99)

        config = EnsembleConfig(min_co_fires=5, max_combo_size=2)
        engine = EnsembleIntelligenceEngine(config)
        report = engine.analyze({
            "sig.a": events_a,
            "sig.b": events_b,
            "sig.c": events_c,
        }, config)

        assert isinstance(report, EnsembleReport)
        assert report.total_pairs_analyzed > 0

    def test_ensemble_bonus_active(self):
        engine = EnsembleIntelligenceEngine()
        report = EnsembleReport(
            top_ensembles=[
                SignalCombination(
                    signals=["sig.a", "sig.b"],
                    ensemble_score=2.0,
                ),
            ],
        )
        bonus = engine.get_ensemble_bonus(report, ["sig.a", "sig.b"])
        assert bonus > 0

    def test_ensemble_bonus_partial(self):
        engine = EnsembleIntelligenceEngine()
        report = EnsembleReport(
            top_ensembles=[
                SignalCombination(
                    signals=["sig.a", "sig.b"],
                    ensemble_score=2.0,
                ),
            ],
        )
        # Only 1 of 2 signals active → 50% coverage
        bonus = engine.get_ensemble_bonus(report, ["sig.a"])
        assert bonus > 0
        # Bonus should be less than full coverage
        full_bonus = engine.get_ensemble_bonus(report, ["sig.a", "sig.b"])
        assert bonus < full_bonus

    def test_ensemble_bonus_no_match(self):
        engine = EnsembleIntelligenceEngine()
        report = EnsembleReport(
            top_ensembles=[
                SignalCombination(signals=["sig.a", "sig.b"], ensemble_score=2.0),
            ],
        )
        bonus = engine.get_ensemble_bonus(report, ["sig.c", "sig.d"])
        assert bonus == 0.0

    def test_ensemble_bonus_capped(self):
        config = EnsembleConfig(ensemble_bonus_cap=3.0)
        engine = EnsembleIntelligenceEngine(config)
        report = EnsembleReport(
            config=config,
            top_ensembles=[
                SignalCombination(signals=["a", "b"], ensemble_score=100.0),
            ],
        )
        bonus = engine.get_ensemble_bonus(report, ["a", "b"])
        assert bonus <= 3.0


# ─── Model Tests ─────────────────────────────────────────────────────────────

class TestEnsembleModels:
    """Tests for Pydantic models."""

    def test_config_defaults(self):
        cfg = EnsembleConfig()
        assert cfg.max_combo_size == 3
        assert cfg.min_co_fires == 10
        assert cfg.date_tolerance == 3
        assert cfg.min_stability == 0.60

    def test_combination_serialization(self):
        combo = SignalCombination(
            signals=["sig.a", "sig.b"],
            synergy_score=0.5,
            stability=0.8,
            ensemble_score=0.4,
        )
        d = combo.model_dump()
        assert d["synergy_score"] == 0.5
        assert len(d["signals"]) == 2

    def test_report_serialization(self):
        report = EnsembleReport(
            total_pairs_analyzed=10,
            synergistic_pairs=3,
            stable_ensembles=2,
        )
        d = report.model_dump()
        assert d["total_pairs_analyzed"] == 10


# ─── DB Table Tests ──────────────────────────────────────────────────────────

class TestEnsembleDatabaseTable:
    """Verify signal_ensemble_profiles table exists in the ORM."""

    def test_table_exists(self):
        from src.data.database import SignalEnsembleRecord
        assert SignalEnsembleRecord.__tablename__ == "signal_ensemble_profiles"
        cols = {c.name for c in SignalEnsembleRecord.__table__.columns}
        assert "run_id" in cols
        assert "signal_ids_json" in cols
        assert "synergy_score" in cols
        assert "stability" in cols
        assert "ensemble_score" in cols
        assert "joint_sharpe" in cols
        assert "joint_hit_rate" in cols
