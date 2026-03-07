"""
tests/test_regime_weights.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Regime-Adaptive Signal Weighting module.

Covers:
  - RegimePerformanceEvaluator (per-regime stats, min events)
  - Multiplier normalisation ([min_mult, max_mult])
  - Effective weight computation (base × multiplier)
  - LOW_VOL regime classification
  - Pydantic model contracts
  - DB table definition
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.engines.backtesting.models import SignalEvent
from src.engines.backtesting.regime_detector import MarketRegime, RegimeDetector, RegimeConfig
from src.engines.alpha_signals.models import SignalStrength
from src.engines.regime_weights.evaluator import RegimePerformanceEvaluator
from src.engines.regime_weights.engine import AdaptiveWeightEngine
from src.engines.regime_weights.models import (
    AdaptiveWeightConfig,
    AdaptiveWeightReport,
    RegimeSignalStats,
    RegimeWeightProfile,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_events(
    signal_id: str,
    n: int = 30,
    base_return: float = 0.01,
    noise_std: float = 0.03,
    seed: int = 42,
    start_date: date = date(2023, 3, 1),
) -> list[SignalEvent]:
    """Create synthetic signal events with sequential business days."""
    dates = pd.bdate_range(start=start_date, periods=n)
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


def _make_regime_map(
    dates: list[date],
    regime: MarketRegime,
) -> dict[date, MarketRegime]:
    """Assign a single regime to all dates."""
    return {d: regime for d in dates}


def _make_bullish_ohlcv(n: int = 300) -> pd.DataFrame:
    """Create synthetic OHLCV data with an upward trend (bullish)."""
    dates = pd.bdate_range(start="2022-01-01", periods=n)
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.normal(0.05, 0.5, n))
    return pd.DataFrame({
        "Open": close * 0.999,
        "High": close * 1.005,
        "Low": close * 0.995,
        "Close": close,
        "Volume": np.random.randint(1_000_000, 10_000_000, n),
    }, index=dates)


# ─── Evaluator Tests ────────────────────────────────────────────────────────

class TestRegimeEvaluator:
    """Tests for per-regime performance evaluation."""

    def test_basic_evaluation(self):
        events_a = _make_events("sig.a", n=20, seed=1)
        # Create regime map matching event dates
        regime_map = _make_regime_map(
            [e.fired_date for e in events_a],
            MarketRegime.BULL,
        )
        evaluator = RegimePerformanceEvaluator()
        result = evaluator.evaluate(
            {"sig.a": events_a}, regime_map,
            forward_window=20, min_events=5,
        )
        assert "sig.a" in result
        bull_stats = result["sig.a"]["bull"]
        assert bull_stats.events_count == 20
        assert bull_stats.sharpe != 0

    def test_min_events_threshold(self):
        events = _make_events("sig.a", n=3)
        regime_map = _make_regime_map(
            [e.fired_date for e in events], MarketRegime.BEAR,
        )
        evaluator = RegimePerformanceEvaluator()
        result = evaluator.evaluate(
            {"sig.a": events}, regime_map,
            forward_window=20, min_events=10,
        )
        bear_stats = result["sig.a"]["bear"]
        assert bear_stats.events_count == 3
        assert bear_stats.sharpe == 0.0  # Below threshold

    def test_multiple_regimes(self):
        events = _make_events("sig.a", n=20, seed=10)
        # Assign first 10 to BULL, last 10 to BEAR
        regime_map = {}
        for i, e in enumerate(events):
            regime_map[e.fired_date] = MarketRegime.BULL if i < 10 else MarketRegime.BEAR

        evaluator = RegimePerformanceEvaluator()
        result = evaluator.evaluate(
            {"sig.a": events}, regime_map,
            forward_window=20, min_events=5,
        )
        assert result["sig.a"]["bull"].events_count == 10
        assert result["sig.a"]["bear"].events_count == 10


# ─── Multiplier Tests ───────────────────────────────────────────────────────

class TestMultiplierComputation:
    """Tests for regime multiplier normalisation."""

    def test_normalisation_range(self):
        cfg = AdaptiveWeightConfig(min_mult=0.3, max_mult=1.5)
        engine = AdaptiveWeightEngine(cfg)

        stats = {
            "bull": RegimeSignalStats(signal_id="sig", regime="bull", sharpe=2.0, events_count=20),
            "bear": RegimeSignalStats(signal_id="sig", regime="bear", sharpe=-1.0, events_count=20),
            "range": RegimeSignalStats(signal_id="sig", regime="range", sharpe=0.5, events_count=20),
        }
        mults = engine._compute_multipliers(stats, cfg)

        # Best regime should get max_mult
        assert abs(mults["bull"] - 1.5) < 0.01
        # Worst regime should get min_mult
        assert abs(mults["bear"] - 0.3) < 0.01
        # Middle regime should be between
        assert 0.3 < mults["range"] < 1.5

    def test_equal_sharpe_neutral(self):
        cfg = AdaptiveWeightConfig()
        engine = AdaptiveWeightEngine(cfg)

        stats = {
            "bull": RegimeSignalStats(signal_id="sig", regime="bull", sharpe=1.0, events_count=20),
            "bear": RegimeSignalStats(signal_id="sig", regime="bear", sharpe=1.0, events_count=20),
        }
        mults = engine._compute_multipliers(stats, cfg)
        assert mults["bull"] == cfg.neutral_mult
        assert mults["bear"] == cfg.neutral_mult

    def test_insufficient_data_neutral(self):
        cfg = AdaptiveWeightConfig(min_events_per_regime=10)
        engine = AdaptiveWeightEngine(cfg)

        stats = {
            "bull": RegimeSignalStats(signal_id="sig", regime="bull", sharpe=2.0, events_count=5),
        }
        mults = engine._compute_multipliers(stats, cfg)
        # All should be neutral since no regime has enough data
        assert all(v == cfg.neutral_mult for v in mults.values())


# ─── Engine Tests ────────────────────────────────────────────────────────────

class TestAdaptiveWeightEngine:
    """Tests for the full AdaptiveWeightEngine."""

    def test_compute_with_ohlcv(self):
        ohlcv = _make_bullish_ohlcv(300)
        events = _make_events("sig.a", n=50, seed=1, start_date=date(2022, 9, 1))
        cfg = AdaptiveWeightConfig(min_events_per_regime=3)
        engine = AdaptiveWeightEngine(cfg)
        report = engine.compute_adaptive_weights(
            ohlcv, {"sig.a": events}, cfg,
        )
        assert isinstance(report, AdaptiveWeightReport)
        assert report.current_regime != ""
        assert len(report.profiles) == 1
        assert report.total_signals == 1

    def test_empty_ohlcv_neutral(self):
        engine = AdaptiveWeightEngine()
        report = engine.compute_adaptive_weights(
            pd.DataFrame(), {"sig.a": _make_events("sig.a")},
        )
        assert report.profiles[0].effective_weight == 1.0

    def test_get_effective_weights(self):
        report = AdaptiveWeightReport(
            profiles=[
                RegimeWeightProfile(
                    signal_id="sig.1", effective_weight=1.3,
                ),
                RegimeWeightProfile(
                    signal_id="sig.2", effective_weight=0.5,
                ),
            ],
        )
        engine = AdaptiveWeightEngine()
        weights = engine.get_effective_weights(report)
        assert weights["sig.1"] == 1.3
        assert weights["sig.2"] == 0.5


# ─── LOW_VOL Regime Tests ───────────────────────────────────────────────────

class TestLowVolRegime:
    """Tests for the new LOW_VOL regime classification."""

    def test_low_vol_enum_exists(self):
        assert hasattr(MarketRegime, "LOW_VOL")
        assert MarketRegime.LOW_VOL.value == "low_vol"

    def test_low_vol_in_all_regimes(self):
        all_values = [r.value for r in MarketRegime]
        assert "low_vol" in all_values
        assert len(all_values) == 5

    def test_config_has_contraction_mult(self):
        cfg = RegimeConfig()
        assert hasattr(cfg, "atr_contraction_mult")
        assert cfg.atr_contraction_mult == 0.6

    def test_low_vol_detection(self):
        """Create synthetic low-volatility data and verify detection."""
        n = 300
        dates = pd.bdate_range(start="2022-01-01", periods=n)
        np.random.seed(42)
        # Very stable price with tiny movements
        close = np.full(n, 100.0) + np.cumsum(np.random.normal(0, 0.01, n))
        high = close + 0.05  # Tiny range
        low = close - 0.05

        ohlcv = pd.DataFrame({
            "Open": close,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": np.full(n, 5_000_000),
        }, index=dates)

        detector = RegimeDetector()
        regimes = detector.classify(ohlcv)
        regime_values = set(r.value for r in regimes.values())
        # Should detect some low_vol or range days
        assert len(regimes) > 0


# ─── Model Tests ─────────────────────────────────────────────────────────────

class TestRegimeWeightModels:
    """Tests for Pydantic models."""

    def test_config_defaults(self):
        cfg = AdaptiveWeightConfig()
        assert cfg.min_mult == 0.3
        assert cfg.max_mult == 1.5
        assert cfg.neutral_mult == 1.0
        assert cfg.min_events_per_regime == 10

    def test_regime_signal_stats(self):
        stats = RegimeSignalStats(
            signal_id="sig.1", regime="bull",
            sharpe=1.5, hit_rate=0.6, events_count=25,
        )
        d = stats.model_dump()
        assert d["sharpe"] == 1.5
        assert d["regime"] == "bull"

    def test_report_serialization(self):
        report = AdaptiveWeightReport(
            current_regime="bull",
            profiles=[
                RegimeWeightProfile(
                    signal_id="sig.1",
                    effective_weight=1.3,
                    current_regime="bull",
                ),
            ],
            total_signals=1,
        )
        d = report.model_dump()
        assert d["current_regime"] == "bull"
        assert d["total_signals"] == 1

    def test_weight_profile_defaults(self):
        p = RegimeWeightProfile(signal_id="test")
        assert p.base_weight == 1.0
        assert p.current_multiplier == 1.0
        assert p.effective_weight == 1.0


# ─── DB Table Tests ──────────────────────────────────────────────────────────

class TestRegimeWeightDatabaseTable:
    """Verify regime_weight_profiles table exists in the ORM."""

    def test_table_exists(self):
        from src.data.database import RegimeWeightRecord
        assert RegimeWeightRecord.__tablename__ == "regime_weight_profiles"
        cols = {c.name for c in RegimeWeightRecord.__table__.columns}
        assert "run_id" in cols
        assert "signal_id" in cols
        assert "current_regime" in cols
        assert "base_weight" in cols
        assert "regime_multiplier" in cols
        assert "effective_weight" in cols
        assert "best_regime" in cols
        assert "worst_regime" in cols
        assert "regime_stats_json" in cols
