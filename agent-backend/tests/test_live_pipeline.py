"""
tests/test_live_pipeline.py
--------------------------------------------------------------------------
Tests for SignalScanner, AlertManager, and ReturnTracker backfill.
"""

from __future__ import annotations

import pytest
import pandas as pd
import numpy as np
from datetime import date

from src.engines.backtesting.models import SignalEvent, SignalStrength
from src.engines.backtesting.signal_scanner import (
    SignalScanner,
    ScanConfig,
    ScanResult,
)
from src.engines.backtesting.alert_manager import (
    AlertManager,
    AlertConfig,
    AlertReport,
)
from src.engines.backtesting.return_tracker import ReturnTracker


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_event(
    signal_id: str = "sig.test",
    ticker: str = "AAPL",
    fired_date: date = date(2024, 1, 15),
    confidence: float = 0.75,
    excess_return: float = 0.01,
) -> SignalEvent:
    return SignalEvent(
        signal_id=signal_id,
        ticker=ticker,
        fired_date=fired_date,
        strength=SignalStrength.MODERATE,
        confidence=confidence,
        value=1.0,
        price_at_fire=100.0,
        forward_returns={20: excess_return + 0.005},
        benchmark_returns={20: 0.005},
        excess_returns={20: excess_return},
    )


def _make_detector(n_signals: int = 2, confidence: float = 0.70):
    """Create a simple detector function for testing."""
    def detector_fn(ticker: str, scan_date: date) -> list[SignalEvent]:
        events = []
        for i in range(n_signals):
            events.append(SignalEvent(
                signal_id=f"sig.test_{i}",
                ticker=ticker,
                fired_date=scan_date,
                strength=SignalStrength.MODERATE,
                confidence=confidence,
                value=1.0,
                price_at_fire=100.0,
                forward_returns={},
                benchmark_returns={},
                excess_returns={},
            ))
        return events
    return detector_fn


def _make_price_df(
    start_date: str = "2024-01-01",
    n_days: int = 100,
    start_price: float = 100.0,
    drift: float = 0.001,
) -> pd.DataFrame:
    """Create a simple price DataFrame for testing."""
    dates = pd.bdate_range(start=start_date, periods=n_days)
    prices = [start_price]
    for i in range(1, n_days):
        prices.append(prices[-1] * (1 + drift))
    return pd.DataFrame({"Close": prices}, index=dates)


# ─── SignalScanner Tests ─────────────────────────────────────────────────────

class TestSignalScanner:

    def test_scan_with_detector(self):
        """Scanner with detector produces events."""
        detector = _make_detector(n_signals=3)
        config = ScanConfig(universe_name="test")
        scanner = SignalScanner(detector_fn=detector, config=config)
        result = scanner.scan(scan_date=date(2024, 6, 1))

        assert result.tickers_scanned == 10  # test universe = 10
        assert result.total_events == 30  # 10 tickers × 3 signals
        assert result.tickers_with_signals == 10

    def test_scan_no_detector(self):
        """Scanner with no-op detector produces nothing."""
        config = ScanConfig(universe_name="test")
        scanner = SignalScanner(config=config)
        result = scanner.scan()

        assert result.tickers_scanned == 10
        assert result.total_events == 0

    def test_confidence_filter(self):
        """Low confidence events filtered out."""
        detector = _make_detector(confidence=0.40)
        config = ScanConfig(universe_name="test", min_confidence=0.50)
        scanner = SignalScanner(detector_fn=detector, config=config)
        result = scanner.scan()

        assert result.total_events == 0

    def test_signal_id_filter(self):
        """Signal ID filter restricts which signals are recorded."""
        detector = _make_detector(n_signals=3)
        config = ScanConfig(
            universe_name="test",
            signal_ids=["sig.test_0"],
        )
        scanner = SignalScanner(detector_fn=detector, config=config)
        result = scanner.scan()

        assert result.total_events == 10  # Only sig.test_0 from each ticker

    def test_max_tickers(self):
        """max_tickers caps universe size."""
        detector = _make_detector(n_signals=1)
        config = ScanConfig(universe_name="test", max_tickers=3)
        scanner = SignalScanner(detector_fn=detector, config=config)
        result = scanner.scan()

        assert result.tickers_scanned == 3
        assert result.total_events == 3

    def test_events_by_signal_counted(self):
        """Events are counted by signal ID."""
        detector = _make_detector(n_signals=2)
        config = ScanConfig(universe_name="test")
        scanner = SignalScanner(detector_fn=detector, config=config)
        result = scanner.scan()

        assert "sig.test_0" in result.events_by_signal
        assert "sig.test_1" in result.events_by_signal
        assert result.events_by_signal["sig.test_0"] == 10

    def test_error_handling(self):
        """Errors in detector don't crash scanner."""
        def bad_detector(ticker: str, sd: date) -> list[SignalEvent]:
            if ticker == "AAPL":
                raise ValueError("data unavailable")
            return [_make_event(ticker=ticker, fired_date=sd)]

        config = ScanConfig(universe_name="test")
        scanner = SignalScanner(detector_fn=bad_detector, config=config)
        result = scanner.scan()

        assert len(result.errors) == 1
        assert result.tickers_scanned == 10
        assert result.total_events == 9  # 10 - 1 error

    def test_available_universes(self):
        """Lists all universes."""
        universes = SignalScanner.available_universes()
        assert "test" in universes
        assert "mega_cap" in universes
        assert universes["test"] == 10


# ─── AlertManager Tests ─────────────────────────────────────────────────────

class TestAlertManager:

    def test_high_confidence_generates_alert(self):
        """High confidence event → alert generated."""
        manager = AlertManager(AlertConfig(min_confidence=0.50))
        events = [_make_event(confidence=0.80)]
        report = manager.process_events(events)

        assert report.alerts_generated == 1
        assert report.alerts[0].ticker == "AAPL"

    def test_low_confidence_filtered(self):
        """Low confidence → no alert."""
        manager = AlertManager(AlertConfig(min_confidence=0.80))
        events = [_make_event(confidence=0.50)]
        report = manager.process_events(events)

        assert report.alerts_generated == 0

    def test_dedup_limits_per_signal(self):
        """Max alerts per signal per day enforced."""
        manager = AlertManager(AlertConfig(
            min_confidence=0.50,
            max_alerts_per_signal=2,
        ))
        events = [
            _make_event(ticker=f"T{i}", confidence=0.80)
            for i in range(5)
        ]
        report = manager.process_events(events)

        assert report.alerts_generated == 2
        assert report.alerts_suppressed == 3

    def test_ic_threshold(self):
        """Signal below IC threshold → no alert."""
        manager = AlertManager(AlertConfig(min_ic=0.05))
        quality = {"sig.test": {"ic": 0.01, "is_usable": True}}
        events = [_make_event(confidence=0.80)]
        report = manager.process_events(events, signal_quality=quality)

        assert report.alerts_generated == 0

    def test_unusable_signal_no_alert(self):
        """Unusable signals → no alert."""
        manager = AlertManager()
        quality = {"sig.test": {"ic": 0.10, "is_usable": False}}
        events = [_make_event(confidence=0.80)]
        report = manager.process_events(events, signal_quality=quality)

        assert report.alerts_generated == 0

    def test_disabled_no_alerts(self):
        """Disabled alert manager → zero alerts."""
        manager = AlertManager(AlertConfig(enabled=False))
        events = [_make_event(confidence=0.90)]
        report = manager.process_events(events)

        assert report.alerts_generated == 0

    def test_clear_history(self):
        """clear_history resets dedup."""
        manager = AlertManager(AlertConfig(
            min_confidence=0.50,
            max_alerts_per_signal=1,
        ))
        events = [_make_event(confidence=0.80)]

        report1 = manager.process_events(events)
        assert report1.alerts_generated == 1

        report2 = manager.process_events(events)
        assert report2.alerts_generated == 0  # dedup

        manager.clear_history()
        report3 = manager.process_events(events)
        assert report3.alerts_generated == 1  # fresh after clear


# ─── ReturnTracker Backfill Tests ────────────────────────────────────────────

class TestReturnTrackerBackfill:

    def test_backfill_fills_missing_windows(self):
        """Events missing forward returns get backfilled."""
        price_df = _make_price_df(start_date="2024-01-01", n_days=100)
        tracker = ReturnTracker(benchmark_ohlcv=pd.DataFrame())

        # Event with no forward returns
        event = SignalEvent(
            signal_id="sig.test",
            ticker="AAPL",
            fired_date=date(2024, 1, 2),  # Second business day
            strength=SignalStrength.MODERATE,
            confidence=0.7,
            value=1.0,
            price_at_fire=100.0,
            forward_returns={},
            benchmark_returns={},
            excess_returns={},
        )

        updated, n_filled = tracker.backfill_pending(
            events=[event],
            forward_windows=[5, 10, 20],
            price_data={"AAPL": price_df},
        )

        assert n_filled == 3
        assert 5 in updated[0].forward_returns
        assert 10 in updated[0].forward_returns
        assert 20 in updated[0].forward_returns

    def test_backfill_skips_existing(self):
        """Events with existing returns are not overwritten."""
        price_df = _make_price_df(start_date="2024-01-01", n_days=100)
        tracker = ReturnTracker(benchmark_ohlcv=pd.DataFrame())

        event = SignalEvent(
            signal_id="sig.test",
            ticker="AAPL",
            fired_date=date(2024, 1, 2),
            strength=SignalStrength.MODERATE,
            confidence=0.7,
            value=1.0,
            price_at_fire=100.0,
            forward_returns={5: 0.05},  # Already has window=5
            benchmark_returns={},
            excess_returns={},
        )

        updated, n_filled = tracker.backfill_pending(
            events=[event],
            forward_windows=[5, 10],
            price_data={"AAPL": price_df},
        )

        assert n_filled == 1  # Only filled window=10
        assert updated[0].forward_returns[5] == 0.05  # Original preserved

    def test_backfill_no_price_data(self):
        """No price data → no backfill."""
        tracker = ReturnTracker(benchmark_ohlcv=pd.DataFrame())
        event = _make_event()

        updated, n_filled = tracker.backfill_pending(
            events=[event],
            forward_windows=[5, 10],
            price_data={},
        )

        assert n_filled == 0
