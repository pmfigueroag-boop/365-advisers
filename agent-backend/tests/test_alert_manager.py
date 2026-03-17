"""
tests/test_alert_manager.py — Tests for Alert Manager.
"""
from __future__ import annotations
import pytest
from datetime import date
from src.engines.backtesting.alert_manager import (
    AlertConfig, AlertManager, AlertReport,
)
from src.engines.backtesting.models import SignalEvent
from src.engines.alpha_signals.models import SignalStrength


def _event(signal_id="mom_12m", ticker="AAPL", confidence=0.75, fired=None):
    return SignalEvent(
        signal_id=signal_id, ticker=ticker, confidence=confidence,
        fired_date=fired or date(2026, 3, 15),
        strength=SignalStrength.STRONG, value=1.5, price_at_fire=180.0,
    )


class TestAlertGeneration:

    def test_high_confidence_generates_alert(self):
        mgr = AlertManager()
        events = [_event(confidence=0.80)]
        report = mgr.process_events(events)
        assert report.alerts_generated == 1

    def test_low_confidence_filtered(self):
        mgr = AlertManager(AlertConfig(min_confidence=0.70))
        events = [_event(confidence=0.50)]
        report = mgr.process_events(events)
        assert report.alerts_generated == 0

    def test_low_ic_filtered(self):
        mgr = AlertManager(AlertConfig(min_ic=0.05))
        events = [_event(confidence=0.80)]
        quality = {"mom_12m": {"ic": 0.02, "is_usable": True}}
        report = mgr.process_events(events, quality)
        assert report.alerts_generated == 0

    def test_unusable_signal_filtered(self):
        mgr = AlertManager()
        events = [_event(confidence=0.80)]
        quality = {"mom_12m": {"ic": 0.10, "is_usable": False}}
        report = mgr.process_events(events, quality)
        assert report.alerts_generated == 0

    def test_no_quality_data_passes(self):
        """Without quality data, assumes signal is usable."""
        mgr = AlertManager()
        events = [_event(confidence=0.80)]
        report = mgr.process_events(events)
        assert report.alerts_generated == 1


class TestDeduplication:

    def test_dedup_limits_per_signal(self):
        mgr = AlertManager(AlertConfig(max_alerts_per_signal=2))
        events = [
            _event("sig1", "A", 0.80),
            _event("sig1", "B", 0.85),
            _event("sig1", "C", 0.90),  # Should be suppressed
        ]
        report = mgr.process_events(events)
        assert report.alerts_generated == 2
        assert report.alerts_suppressed == 1

    def test_different_signals_not_deduped(self):
        mgr = AlertManager(AlertConfig(max_alerts_per_signal=1))
        events = [
            _event("sig1", "A", 0.80),
            _event("sig2", "A", 0.80),
        ]
        report = mgr.process_events(events)
        assert report.alerts_generated == 2


class TestDispatch:

    def test_alerts_dispatched(self):
        mgr = AlertManager()
        events = [_event(confidence=0.80)]
        report = mgr.process_events(events)
        assert report.alerts_dispatched == 1
        assert report.alerts[0].dispatched is True

    def test_alert_has_dispatched_at(self):
        mgr = AlertManager()
        events = [_event()]
        report = mgr.process_events(events)
        assert report.alerts[0].dispatched_at is not None


class TestEdgeCases:

    def test_empty_events(self):
        mgr = AlertManager()
        report = mgr.process_events([])
        assert report.alerts_generated == 0

    def test_disabled_manager(self):
        mgr = AlertManager(AlertConfig(enabled=False))
        events = [_event(confidence=0.99)]
        report = mgr.process_events(events)
        assert report.alerts_generated == 0

    def test_clear_history(self):
        mgr = AlertManager(AlertConfig(max_alerts_per_signal=1))
        events = [_event("sig1", "A", 0.80)]
        mgr.process_events(events)
        mgr.clear_history()
        report = mgr.process_events(events)
        assert report.alerts_generated == 1  # Can fire again after clear

    def test_alert_id_format(self):
        mgr = AlertManager()
        report = mgr.process_events([_event("mom_12m", "AAPL", 0.80)])
        assert "mom_12m:AAPL:" in report.alerts[0].alert_id
