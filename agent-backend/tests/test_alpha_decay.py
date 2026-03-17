"""
tests/test_alpha_decay.py
--------------------------------------------------------------------------
Tests for AlphaDecayEngine.
"""

from __future__ import annotations

import math
import random
import pytest
from datetime import date

from src.engines.backtesting.models import SignalEvent, SignalStrength
from src.engines.backtesting.alpha_decay import (
    AlphaDecayEngine,
    AlphaDecayReport,
    AlphaDecayResult,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_decay_events(
    signal_id: str,
    n_events: int = 50,
    alpha_0: float = 0.02,
    decay_rate: float = 0.03,
) -> list[SignalEvent]:
    """Create events where excess returns decay exponentially with window."""
    rng = random.Random(42)
    events = []

    for i in range(n_events):
        excess = {}
        for w in [5, 10, 20, 40, 60]:
            # α(t) = α₀ × e^(-λt) + noise
            alpha_t = alpha_0 * math.exp(-decay_rate * w)
            excess[w] = alpha_t + rng.gauss(0, 0.002)

        events.append(SignalEvent(
            signal_id=signal_id,
            ticker=f"T{i % 10}",
            fired_date=date(2024, 1, 1 + (i % 28)),
            strength=SignalStrength.MODERATE,
            confidence=0.7,
            value=1.0,
            price_at_fire=100.0,
            forward_returns={w: excess[w] + 0.005 for w in excess},
            benchmark_returns={w: 0.005 for w in excess},
            excess_returns=excess,
        ))

    return events


def _make_persistent_events(
    signal_id: str,
    n_events: int = 50,
    alpha: float = 0.015,
) -> list[SignalEvent]:
    """Events where alpha doesn't decay (persistent signal)."""
    rng = random.Random(123)
    events = []

    for i in range(n_events):
        excess = {}
        for w in [5, 10, 20, 40, 60]:
            excess[w] = alpha + rng.gauss(0, 0.002)  # Same alpha all windows

        events.append(SignalEvent(
            signal_id=signal_id,
            ticker=f"T{i % 10}",
            fired_date=date(2024, 1, 1 + (i % 28)),
            strength=SignalStrength.MODERATE,
            confidence=0.7,
            value=1.0,
            price_at_fire=100.0,
            forward_returns={w: excess[w] + 0.005 for w in excess},
            benchmark_returns={w: 0.005 for w in excess},
            excess_returns=excess,
        ))

    return events


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestAlphaDecayEngine:

    def test_decaying_signal_detected(self):
        """Signal with exponential decay → is_decaying=True."""
        events = _make_decay_events("decay.sig", alpha_0=0.03, decay_rate=0.05)
        engine = AlphaDecayEngine()
        report = engine.analyze(events)

        assert report.total_signals == 1
        result = report.signal_results[0]
        assert result.is_decaying is True
        assert result.decay_rate > 0
        assert result.half_life_days > 0
        assert result.r_squared > 0.3

    def test_half_life_reasonable(self):
        """Half-life should correspond to the input decay rate."""
        events = _make_decay_events("hl.sig", alpha_0=0.03, decay_rate=0.04)
        engine = AlphaDecayEngine()
        report = engine.analyze(events)

        result = report.signal_results[0]
        expected_hl = math.log(2) / 0.04  # ~17.3 days
        assert abs(result.half_life_days - expected_hl) < 10  # tolerance

    def test_persistent_signal_low_decay(self):
        """Persistent signal → decay_rate ≈ 0."""
        events = _make_persistent_events("persistent.sig")
        engine = AlphaDecayEngine()
        report = engine.analyze(events)

        result = report.signal_results[0]
        # Should have very low or zero decay rate
        assert result.decay_rate < 0.01

    def test_window_returns_populated(self):
        """All windows should have returns."""
        events = _make_decay_events("wr.sig")
        engine = AlphaDecayEngine()
        report = engine.analyze(events)

        result = report.signal_results[0]
        assert 5 in result.window_returns
        assert 60 in result.window_returns
        # Early window should have higher return than late
        assert result.window_returns[5] > result.window_returns[60]

    def test_optimal_holding_period(self):
        """Optimal holding period should be computed."""
        events = _make_decay_events("opt.sig")
        engine = AlphaDecayEngine()
        report = engine.analyze(events)

        result = report.signal_results[0]
        assert result.optimal_holding_days > 0
        assert result.optimal_holding_days in [5, 10, 20, 40, 60]

    def test_multiple_signals(self):
        """Multiple signals analyzed independently."""
        fast = _make_decay_events("fast.sig", alpha_0=0.03, decay_rate=0.08)
        slow = _make_decay_events("slow.sig", alpha_0=0.03, decay_rate=0.01)
        engine = AlphaDecayEngine()
        report = engine.analyze(fast + slow)

        assert report.total_signals == 2
        fast_r = next(r for r in report.signal_results if r.signal_id == "fast.sig")
        slow_r = next(r for r in report.signal_results if r.signal_id == "slow.sig")
        assert fast_r.decay_rate > slow_r.decay_rate

    def test_insufficient_events_skipped(self):
        """< min_events → signal skipped."""
        events = _make_decay_events("few.sig", n_events=5)
        engine = AlphaDecayEngine(min_events=20)
        report = engine.analyze(events)

        assert report.total_signals == 0

    def test_empty_events(self):
        """No events → empty report."""
        engine = AlphaDecayEngine()
        report = engine.analyze([])
        assert report.total_signals == 0

    def test_fast_decay_count(self):
        """Report counts signals with fast decay (half-life < 10 days)."""
        fast = _make_decay_events("fast.sig", alpha_0=0.03, decay_rate=0.10)
        slow = _make_decay_events("slow.sig", alpha_0=0.03, decay_rate=0.005)
        engine = AlphaDecayEngine()
        report = engine.analyze(fast + slow)

        assert report.fast_decay_count >= 1  # fast.sig should qualify

    def test_signal_meta_propagated(self):
        """Signal names propagated to results."""
        events = _make_decay_events("meta.sig")
        engine = AlphaDecayEngine()
        report = engine.analyze(events, signal_meta={"meta.sig": "MACD Cross"})
        assert report.signal_results[0].signal_name == "MACD Cross"
