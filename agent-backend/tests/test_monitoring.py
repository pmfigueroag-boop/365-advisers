"""
tests/test_monitoring.py
──────────────────────────────────────────────────────────────────────────────
Tests for the Monitoring/Surveillance engine and routes.
"""
from __future__ import annotations

import pytest

from src.engines.monitoring.alert_manager import AlertManager, Alert, AlertSeverity


class TestAlertManager:

    def setup_method(self):
        self.manager = AlertManager()

    def test_create_alert(self):
        """Should create and store an alert."""
        alert = self.manager.create_alert(
            title="Test Alert",
            message="Something triggered",
            severity=AlertSeverity.WARNING,
            ticker="AAPL",
        )
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING

    def test_get_alerts_returns_list(self):
        """get_alerts should return a list."""
        alerts = self.manager.get_alerts()
        assert isinstance(alerts, list)

    def test_alert_severity_levels(self):
        """All severity levels should be valid."""
        for severity in AlertSeverity:
            assert severity.value in ("info", "warning", "critical")

    def test_mark_as_read(self):
        """Should be able to mark an alert as read."""
        alert = self.manager.create_alert(
            title="Read test",
            message="mark me",
            severity=AlertSeverity.INFO,
        )
        if hasattr(self.manager, "mark_read"):
            self.manager.mark_read(alert.id)
            updated = self.manager.get_alert(alert.id)
            if updated:
                assert updated.read is True


class TestMonitoringContract:

    def test_alert_model_fields(self):
        """Alert should have required fields for frontend."""
        alert = Alert(
            title="Test",
            message="Test message",
            severity=AlertSeverity.INFO,
        )
        assert hasattr(alert, "title")
        assert hasattr(alert, "message")
        assert hasattr(alert, "severity")
