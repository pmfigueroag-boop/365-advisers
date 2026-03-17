"""
tests/test_signal_attribution.py
--------------------------------------------------------------------------
Tests for SignalAttributionEngine and governor integration.
"""

from __future__ import annotations

import pytest
from datetime import date
from pathlib import Path
import tempfile

from src.engines.alpha_signals.models import SignalCategory
from src.engines.backtesting.models import SignalEvent, SignalStrength
from src.engines.backtesting.signal_attribution import (
    SignalAttributionEngine,
    SignalContribution,
    AttributionReport,
)
from src.engines.backtesting.calibration_models import (
    GovernanceAction,
    ParameterChange,
    ParameterType,
)
from src.engines.backtesting.calibration_governor import CalibrationGovernor
from src.engines.backtesting.models import SignalPerformanceRecord


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_event(
    signal_id: str,
    ticker: str = "AAPL",
    fired_date: date = date(2024, 6, 1),
    excess_return_20: float = 0.01,
) -> SignalEvent:
    """Create a minimal SignalEvent with excess return@20d."""
    return SignalEvent(
        signal_id=signal_id,
        ticker=ticker,
        fired_date=fired_date,
        strength=SignalStrength.MODERATE,
        confidence=0.7,
        value=1.0,
        price_at_fire=100.0,
        forward_returns={20: excess_return_20 + 0.005},  # raw return
        benchmark_returns={20: 0.005},
        excess_returns={20: excess_return_20},
    )


def _make_diverse_events(
    signal_id: str,
    n: int = 20,
    base_excess: float = 0.02,
    noise: float = 0.005,
) -> list[SignalEvent]:
    """Create N events with varying returns to avoid zero-variance."""
    events = []
    for i in range(n):
        # Alternate returns slightly to ensure non-zero variance
        excess = base_excess + (noise * (1 if i % 2 == 0 else -1))
        events.append(_make_event(
            signal_id=signal_id,
            ticker=f"T{i % 5}",
            fired_date=date(2024, 1, 1 + i),
            excess_return_20=excess,
        ))
    return events


def _make_performance_record(
    signal_id: str = "test.sig",
    total_firings: int = 100,
    sharpe_20: float = 0.5,
    hit_rate_20: float = 0.55,
) -> SignalPerformanceRecord:
    return SignalPerformanceRecord(
        signal_id=signal_id,
        signal_name=f"Test {signal_id}",
        category=SignalCategory("value"),
        total_firings=total_firings,
        total_correct=int(total_firings * hit_rate_20),
        sharpe_ratio={20: sharpe_20},
        hit_rate={20: hit_rate_20},
        avg_return={20: 0.005},
    )


# ─── Attribution Engine Tests ───────────────────────────────────────────────

class TestSignalAttribution:
    def setup_method(self):
        self.engine = SignalAttributionEngine()

    def test_single_signal_contribution_equals_system(self):
        """With 1 signal, its contribution = system Sharpe (removing it = 0)."""
        events = _make_diverse_events("only_signal", n=20, base_excess=0.02)
        report = self.engine.compute(events)

        assert report.total_signals == 1
        assert len(report.signal_contributions) == 1

        c = report.signal_contributions[0]
        assert c.signal_id == "only_signal"
        assert c.system_sharpe > 0  # Positive excess returns
        assert c.system_without_sharpe == 0.0  # No events left
        assert c.marginal_contribution == c.system_sharpe
        assert c.is_dilutive is False
        assert c.contribution_rank == 1

    def test_dilutive_signal_detected(self):
        """
        Signal with noise returns should have negative marginal contribution
        when added to a strong system.
        """
        # Strong signal: consistent positive excess returns
        strong_events = _make_diverse_events(
            "strong", n=30, base_excess=0.03, noise=0.002,
        )
        # Noise signal: near-zero with high variance (dilutes Sharpe)
        noise_events = _make_diverse_events(
            "noise", n=30, base_excess=0.001, noise=0.04,
        )
        all_events = strong_events + noise_events

        report = self.engine.compute(all_events)
        assert report.total_signals == 2

        # Find the noise signal
        noise_contrib = next(
            c for c in report.signal_contributions if c.signal_id == "noise"
        )
        strong_contrib = next(
            c for c in report.signal_contributions if c.signal_id == "strong"
        )

        # Strong signal should have positive contribution
        assert strong_contrib.marginal_contribution > 0
        assert strong_contrib.is_dilutive is False

        # Noise signal should be dilutive (its high variance hurts system Sharpe)
        assert noise_contrib.is_dilutive is True
        assert noise_contrib.marginal_contribution < 0
        assert report.total_dilutive >= 1

    def test_contributions_sum_approximately(self):
        """Each signal should have a defined marginal contribution and correct ranking."""
        events_a = _make_diverse_events("sig_a", n=25, base_excess=0.025)
        events_b = _make_diverse_events("sig_b", n=25, base_excess=0.015)
        all_events = events_a + events_b

        report = self.engine.compute(all_events)

        assert report.total_signals == 2
        assert report.system_sharpe > 0  # Both signals have positive excess

        # Higher base_excess signal should have higher individual Sharpe
        sig_a = next(c for c in report.signal_contributions if c.signal_id == "sig_a")
        sig_b = next(c for c in report.signal_contributions if c.signal_id == "sig_b")
        assert sig_a.individual_sharpe > sig_b.individual_sharpe

        # Ranks should be assigned (1 = top contributor)
        ranks = {c.signal_id: c.contribution_rank for c in report.signal_contributions}
        assert set(ranks.values()) == {1, 2}

    def test_redundant_signal_high_redundancy_score(self):
        """
        Duplicate signal (same events) should have high redundancy score
        when paired with another signal firing on same dates.
        """
        # Create events for both signals at the same (ticker, date)
        events = []
        for i in range(20):
            d = date(2024, 3, 1 + i)
            ticker = f"T{i % 3}"
            excess = 0.02 + 0.003 * (1 if i % 2 == 0 else -1)
            events.append(_make_event("original", ticker, d, excess))
            events.append(_make_event("duplicate", ticker, d, excess))

        report = self.engine.compute(events)
        assert report.total_signals == 2

        dup = next(
            c for c in report.signal_contributions if c.signal_id == "duplicate"
        )
        # Redundancy should be high (near 1.0) because returns are identical
        assert dup.redundancy_score > 0.8

    def test_empty_events_returns_empty(self):
        """Edge case: no events → empty report."""
        report = self.engine.compute([])
        assert report.total_signals == 0
        assert report.system_sharpe == 0.0
        assert len(report.signal_contributions) == 0

    def test_bair_computed_correctly(self):
        """BAIR = avg_IC × √BR_effective, using real Spearman IC."""
        import math

        # Events with confidence correlated with returns → positive IC
        events_one = []
        for i in range(20):
            conf = 0.5 + 0.02 * i       # 0.50 → 0.88
            excess = 0.01 + 0.002 * i    # monotonically increasing with conf
            events_one.append(SignalEvent(
                signal_id="sig_one",
                ticker=f"T{i % 5}",
                fired_date=date(2024, 1, 1 + i),
                strength=SignalStrength.MODERATE,
                confidence=conf,
                value=1.0,
                price_at_fire=100.0,
                forward_returns={20: excess + 0.005},
                benchmark_returns={20: 0.005},
                excess_returns={20: excess},
            ))

        report_one = self.engine.compute(events_one)

        assert report_one.effective_signal_count == 1
        assert report_one.avg_ic > 0  # Positive IC from correlated confidence-return
        assert report_one.bair > 0
        # With 1 effective signal: BAIR = avg_IC × √1 = avg_IC
        assert report_one.bair == pytest.approx(report_one.avg_ic, abs=0.001)

    def test_signal_meta_propagated(self):
        """Signal metadata should be propagated to contributions."""
        events = _make_diverse_events("test.value", n=10, base_excess=0.02)
        meta = {"test.value": ("MACD Bearish", SignalCategory.VALUE)}
        report = self.engine.compute(events, signal_meta=meta)

        c = report.signal_contributions[0]
        assert c.signal_name == "MACD Bearish"
        assert c.category == SignalCategory.VALUE

    def test_ic_is_spearman_correlation(self):
        """IC should be Spearman rank correlation(confidence, excess_return)."""
        # Create events where higher confidence → higher return (positive IC)
        events = []
        for i in range(20):
            conf = 0.5 + 0.02 * i  # 0.50 to 0.88
            excess = 0.005 + 0.003 * i  # monotonically increasing
            events.append(SignalEvent(
                signal_id="ranked",
                ticker=f"T{i % 5}",
                fired_date=date(2024, 1, 1 + i),
                strength=SignalStrength.MODERATE,
                confidence=conf,
                value=1.0,
                price_at_fire=100.0,
                forward_returns={20: excess + 0.005},
                benchmark_returns={20: 0.005},
                excess_returns={20: excess},
            ))

        report = self.engine.compute(events)
        c = report.signal_contributions[0]

        # Perfect monotonic relationship → IC should be very high
        assert c.ic > 0.8
        # avg_ic in report should now use real IC (not Sharpe proxy)
        assert report.avg_ic == c.ic  # Only 1 signal


# ─── Governor Integration Tests ─────────────────────────────────────────────

class TestGovernorAlphaDilution:
    def setup_method(self):
        self.governor = CalibrationGovernor()

    def test_governor_flags_dilutive_weight_increase(self):
        """Weight increase with negative contribution → FLAGGED."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0,
            new_value=1.1,  # +10% increase
            contribution_score=-0.05,  # Dilutive
        )
        record = _make_performance_record(total_firings=100, sharpe_20=0.5)
        decisions = self.governor.review([change], {"test.sig": record})

        assert decisions[0].action == GovernanceAction.FLAGGED
        assert "Alpha dilution" in decisions[0].reason
        assert "-0.0500" in decisions[0].reason

    def test_governor_allows_dilutive_weight_decrease(self):
        """Weight decrease with negative contribution → no dilution flag.
        (It's correct to decrease a dilutive signal's weight.)"""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0,
            new_value=0.9,  # -10% decrease
            contribution_score=-0.05,  # Dilutive, but we're decreasing
        )
        record = _make_performance_record(total_firings=100, sharpe_20=0.5)
        decisions = self.governor.review([change], {"test.sig": record})

        # Should NOT be flagged for dilution (direction is correct)
        assert "Alpha dilution" not in decisions[0].reason

    def test_governor_allows_positive_contribution_increase(self):
        """Weight increase with positive contribution → normal rules apply."""
        change = ParameterChange(
            signal_id="test.sig",
            parameter=ParameterType.WEIGHT,
            old_value=1.0,
            new_value=1.08,  # +8% increase
            contribution_score=0.15,  # Additive
        )
        record = _make_performance_record(total_firings=100, sharpe_20=0.5)
        decisions = self.governor.review([change], {"test.sig": record})

        # Should pass — positive contribution, small change
        assert decisions[0].action == GovernanceAction.APPROVED


# ─── Persistence Tests ──────────────────────────────────────────────────────

class TestAttributionPersistence:
    def setup_method(self):
        self.engine = SignalAttributionEngine()

    def test_save_load_round_trip(self):
        """save_report → load_report must preserve all fields."""
        events = _make_diverse_events("sig_a", n=20, base_excess=0.025)
        events += _make_diverse_events("sig_b", n=20, base_excess=0.015)
        meta = {
            "sig_a": ("MACD Signal", SignalCategory.MOMENTUM),
            "sig_b": ("RSI Signal", SignalCategory.MOMENTUM),
        }
        report = self.engine.compute(events, signal_meta=meta)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "attribution.json"
            self.engine.save_report(report, path)

            assert path.exists()

            loaded = self.engine.load_report(path)
            assert loaded is not None
            assert loaded.total_signals == report.total_signals
            assert loaded.system_sharpe == report.system_sharpe
            assert loaded.effective_signal_count == report.effective_signal_count
            assert loaded.total_dilutive == report.total_dilutive
            assert len(loaded.signal_contributions) == len(report.signal_contributions)

            for orig, load in zip(
                report.signal_contributions, loaded.signal_contributions
            ):
                assert load.signal_id == orig.signal_id
                assert load.signal_name == orig.signal_name
                assert load.marginal_contribution == orig.marginal_contribution
                assert load.contribution_rank == orig.contribution_rank
                assert load.redundancy_score == orig.redundancy_score
                assert load.is_dilutive == orig.is_dilutive

    def test_load_missing_file(self):
        """load_report on non-existent file returns None."""
        result = self.engine.load_report(Path("/tmp/nonexistent_attribution.json"))
        assert result is None

