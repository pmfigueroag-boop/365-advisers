"""
src/engines/backtesting/alert_manager.py
--------------------------------------------------------------------------
Alert Manager — dispatches notifications when significant signals fire.

Supports:
  - Log-based alerts (default)
  - Webhook-ready dispatch (URL + payload)
  - Configurable thresholds (min IC, min confidence, governor-clean)
  - Alert history for deduplication

Usage::

    manager = AlertManager()
    manager.process_events(scan_result.events, signal_quality)
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from collections import defaultdict

from pydantic import BaseModel, Field

from src.engines.backtesting.models import SignalEvent

logger = logging.getLogger("365advisers.backtesting.alerts")


# ── Contracts ────────────────────────────────────────────────────────────────

class AlertConfig(BaseModel):
    """Alert threshold configuration."""
    min_confidence: float = Field(
        0.60, ge=0.0, le=1.0,
        description="Minimum confidence to trigger alert",
    )
    min_ic: float = Field(
        0.03, ge=0.0,
        description="Minimum signal IC to trigger alert",
    )
    max_alerts_per_signal: int = Field(
        5, ge=1,
        description="Max alerts per signal per day (dedup)",
    )
    webhook_url: str | None = Field(
        None, description="Optional webhook URL for external dispatch",
    )
    enabled: bool = Field(True, description="Master switch for alerts")


class Alert(BaseModel):
    """A single alert notification."""
    alert_id: str = ""
    signal_id: str
    ticker: str
    confidence: float
    fired_date: date
    reason: str = ""
    dispatched: bool = False
    dispatched_at: datetime | None = None


class AlertReport(BaseModel):
    """Summary of alert processing."""
    total_events: int = 0
    alerts_generated: int = 0
    alerts_suppressed: int = 0
    alerts_dispatched: int = 0
    alerts: list[Alert] = Field(default_factory=list)


# ── Engine ───────────────────────────────────────────────────────────────────

class AlertManager:
    """
    Processes signal events and dispatches alerts for significant ones.

    Thresholds:
      - confidence >= min_confidence
      - IC >= min_ic (if quality data provided)
      - Deduplication: max N alerts per signal per day

    Integration
    ~~~~~~~~~~~
    - Log-based: always active
    - Webhook: set ``AlertConfig.webhook_url`` for external dispatch
    - Custom: subclass and override ``_dispatch``
    """

    def __init__(self, config: AlertConfig | None = None) -> None:
        self.config = config or AlertConfig()
        self._history: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int),
        )

    def process_events(
        self,
        events: list[SignalEvent],
        signal_quality: dict[str, dict] | None = None,
    ) -> AlertReport:
        """
        Process events and generate alerts.

        Parameters
        ----------
        events : list[SignalEvent]
            Signal events from a scanner run.
        signal_quality : dict[str, dict] | None
            Optional quality data: {signal_id: {"ic": 0.08, "is_usable": True, ...}}

        Returns
        -------
        AlertReport
            Report of generated and dispatched alerts.
        """
        if not self.config.enabled or not events:
            return AlertReport(total_events=len(events))

        quality = signal_quality or {}
        alerts: list[Alert] = []
        suppressed = 0

        for event in events:
            # Check confidence threshold
            if event.confidence < self.config.min_confidence:
                continue

            # Check IC threshold (if quality data available)
            sq = quality.get(event.signal_id, {})
            ic = sq.get("ic", self.config.min_ic)  # assume passes if no data
            if ic < self.config.min_ic:
                continue

            # Check usability
            if not sq.get("is_usable", True):
                continue

            # Dedup: check per-signal daily limit
            day_key = event.fired_date.isoformat()
            count = self._history[day_key][event.signal_id]
            if count >= self.config.max_alerts_per_signal:
                suppressed += 1
                continue

            # Generate alert
            alert = Alert(
                alert_id=f"{event.signal_id}:{event.ticker}:{day_key}",
                signal_id=event.signal_id,
                ticker=event.ticker,
                confidence=event.confidence,
                fired_date=event.fired_date,
                reason=f"Signal {event.signal_id} fired on {event.ticker} "
                       f"(confidence={event.confidence:.2f})",
            )

            # Dispatch
            dispatched = self._dispatch(alert)
            alert.dispatched = dispatched
            if dispatched:
                alert.dispatched_at = datetime.now(timezone.utc)

            alerts.append(alert)
            self._history[day_key][event.signal_id] += 1

        n_dispatched = sum(1 for a in alerts if a.dispatched)

        logger.info(
            "ALERTS: %d events → %d alerts generated, %d dispatched, %d suppressed",
            len(events), len(alerts), n_dispatched, suppressed,
        )

        return AlertReport(
            total_events=len(events),
            alerts_generated=len(alerts),
            alerts_suppressed=suppressed,
            alerts_dispatched=n_dispatched,
            alerts=alerts,
        )

    def _dispatch(self, alert: Alert) -> bool:
        """
        Dispatch an alert via log and optional webhook.

        Returns True if dispatch succeeded.
        """
        # Always log
        logger.info(
            "🔔 ALERT: %s | %s | conf=%.2f | %s",
            alert.signal_id, alert.ticker,
            alert.confidence, alert.reason,
        )

        # Webhook (if configured)
        if self.config.webhook_url:
            try:
                self._send_webhook(alert)
            except Exception as e:
                logger.error("ALERT: Webhook failed: %s", e)
                return False

        return True

    def _send_webhook(self, alert: Alert) -> None:
        """
        Send alert to webhook URL.

        This is a placeholder for production integration.
        In production, use httpx or aiohttp.
        """
        # Placeholder — in production, this would be:
        # import httpx
        # httpx.post(self.config.webhook_url, json=alert.model_dump())
        logger.info(
            "ALERT-WEBHOOK: Would send to %s: %s",
            self.config.webhook_url, alert.alert_id,
        )

    def clear_history(self) -> None:
        """Clear alert dedup history."""
        self._history.clear()
