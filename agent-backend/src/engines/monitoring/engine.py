"""
src/engines/monitoring/engine.py
──────────────────────────────────────────────────────────────────────────────
Opportunity Monitoring Engine — snapshot-diff change detection.

Compares current state against previous snapshots to detect meaningful
changes in scores, signals, tiers, and alpha thresholds.

Pipeline:
  1. Capture current snapshot per ticker
  2. Load previous snapshot from SnapshotStore
  3. Run 4 delta detectors
  4. Store current snapshot as new baseline
  5. Persist alerts to DB
  6. Return MonitoringResult
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from src.data.database import SessionLocal, OpportunityAlertRecord
from src.engines.monitoring.models import (
    AlertSeverity,
    AlertType,
    MonitoringConfig,
    MonitoringResult,
    OpportunityAlert,
    OpportunitySnapshot,
)
from src.engines.monitoring.snapshot_store import SnapshotStore

logger = logging.getLogger("365advisers.monitoring.engine")


class MonitoringEngine:
    """
    Detects changes in opportunity scores and signals.

    Usage
    -----
    engine = MonitoringEngine()
    result = engine.scan(
        tickers=["AAPL", "MSFT"],
        case_scores={"AAPL": 72.0, "MSFT": 68.0},
        opp_scores={"AAPL": 7.8, "MSFT": 7.2},
        signals={"AAPL": ["val.fcf", "mom.rsi"], "MSFT": ["qual.roe"]},
    )
    """

    def __init__(self, config: MonitoringConfig | None = None) -> None:
        self.config = config or MonitoringConfig()

    # ── Public API ────────────────────────────────────────────────────────

    def scan(
        self,
        tickers: list[str],
        case_scores: dict[str, float] | None = None,
        opp_scores: dict[str, float] | None = None,
        signals: dict[str, list[str]] | None = None,
        uos_scores: dict[str, float] | None = None,
        tiers: dict[str, str] | None = None,
    ) -> MonitoringResult:
        """
        Run a monitoring scan across tickers.

        Parameters
        ----------
        tickers : list[str]
            Tickers to monitor.
        case_scores : dict
            {ticker: CASE score 0-100}.
        opp_scores : dict
            {ticker: opportunity score 0-10}.
        signals : dict
            {ticker: [signal_id, ...]}.
        uos_scores : dict
            {ticker: UOS 0-100}.
        tiers : dict
            {ticker: tier label}.
        """
        start = time.time()
        case_scores = case_scores or {}
        opp_scores = opp_scores or {}
        signals = signals or {}
        uos_scores = uos_scores or {}
        tiers = tiers or {}

        all_alerts: list[OpportunityAlert] = []
        snapshots: dict[str, OpportunitySnapshot] = {}

        for ticker in tickers:
            # 1. Build current snapshot
            current = OpportunitySnapshot(
                ticker=ticker,
                case_score=case_scores.get(ticker, 0.0),
                opportunity_score=opp_scores.get(ticker, 0.0),
                uos=uos_scores.get(ticker, 0.0),
                tier=tiers.get(ticker, ""),
                fired_signals=signals.get(ticker, []),
                signal_count=len(signals.get(ticker, [])),
            )
            snapshots[ticker] = current

            # 2. Load previous
            previous = SnapshotStore.get(ticker)

            # 3. Diff
            if previous is not None:
                ticker_alerts = self._diff(previous, current)
                # Limit alerts per ticker
                ticker_alerts = ticker_alerts[:self.config.max_alerts_per_ticker]
                all_alerts.extend(ticker_alerts)

            # 4. Store current as baseline
            SnapshotStore.put(current)

        # 5. Persist alerts
        self._persist_alerts(all_alerts)

        elapsed_ms = (time.time() - start) * 1000

        logger.info(
            f"MONITOR: Scanned {len(tickers)} tickers, "
            f"{len(all_alerts)} alerts generated"
        )

        return MonitoringResult(
            alerts=all_alerts,
            snapshots=snapshots,
            tickers_monitored=len(tickers),
            alerts_generated=len(all_alerts),
            scan_duration_ms=round(elapsed_ms, 1),
        )

    def get_alerts(
        self,
        ticker: str | None = None,
        severity: str | None = None,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[OpportunityAlert]:
        """Query stored alerts with optional filters."""
        try:
            session = SessionLocal()
            query = session.query(OpportunityAlertRecord)

            if ticker:
                query = query.filter(OpportunityAlertRecord.ticker == ticker)
            if severity:
                query = query.filter(OpportunityAlertRecord.severity == severity)
            if unread_only:
                query = query.filter(OpportunityAlertRecord.read == False)

            query = query.order_by(OpportunityAlertRecord.created_at.desc())
            records = query.limit(limit).all()

            return [
                OpportunityAlert(
                    id=r.id,
                    ticker=r.ticker,
                    alert_type=AlertType(r.alert_type),
                    severity=AlertSeverity(r.severity),
                    title=r.title or "",
                    description=r.description or "",
                    previous_value=r.prev_value or 0.0,
                    current_value=r.curr_value or 0.0,
                    delta=r.delta or 0.0,
                    new_signals=json.loads(r.new_signals or "[]"),
                    created_at=r.created_at,
                    read=r.read or False,
                )
                for r in records
            ]
        except Exception as exc:
            logger.error(f"MONITOR: Failed to query alerts — {exc}")
            return []
        finally:
            session.close()

    def mark_read(self, alert_id: str) -> bool:
        """Mark an alert as read."""
        try:
            session = SessionLocal()
            record = session.query(OpportunityAlertRecord).filter_by(
                id=alert_id
            ).first()
            if not record:
                return False
            record.read = True
            session.commit()
            return True
        except Exception as exc:
            logger.error(f"MONITOR: Failed to mark alert {alert_id} — {exc}")
            return False
        finally:
            session.close()

    # ── Delta Detectors ───────────────────────────────────────────────────

    def _diff(
        self,
        prev: OpportunitySnapshot,
        curr: OpportunitySnapshot,
    ) -> list[OpportunityAlert]:
        """Compare two snapshots and generate alerts."""
        alerts: list[OpportunityAlert] = []

        alerts.extend(self._detect_score_surge(prev, curr))
        alerts.extend(self._detect_new_signals(prev, curr))
        alerts.extend(self._detect_tier_change(prev, curr))
        alerts.extend(self._detect_alpha_shift(prev, curr))

        return alerts

    def _detect_score_surge(
        self,
        prev: OpportunitySnapshot,
        curr: OpportunitySnapshot,
    ) -> list[OpportunityAlert]:
        """Detect significant CASE or OppScore increases."""
        alerts: list[OpportunityAlert] = []
        cfg = self.config

        # CASE score surge
        case_delta = curr.case_score - prev.case_score
        if abs(case_delta) >= cfg.case_delta_threshold:
            direction = "↑" if case_delta > 0 else "↓"
            severity = (
                AlertSeverity.HIGH if abs(case_delta) >= 20
                else AlertSeverity.MEDIUM
            )
            alerts.append(OpportunityAlert(
                ticker=curr.ticker,
                alert_type=AlertType.SCORE_SURGE,
                severity=severity,
                title=f"{curr.ticker}: CASE {direction}{abs(case_delta):.1f}",
                description=(
                    f"Composite Alpha Score changed from "
                    f"{prev.case_score:.1f} to {curr.case_score:.1f}"
                ),
                previous_value=prev.case_score,
                current_value=curr.case_score,
                delta=round(case_delta, 2),
            ))

        # OppScore surge
        opp_delta = curr.opportunity_score - prev.opportunity_score
        if abs(opp_delta) >= cfg.opp_delta_threshold:
            direction = "↑" if opp_delta > 0 else "↓"
            severity = (
                AlertSeverity.HIGH if abs(opp_delta) >= 2.5
                else AlertSeverity.MEDIUM
            )
            alerts.append(OpportunityAlert(
                ticker=curr.ticker,
                alert_type=AlertType.SCORE_SURGE,
                severity=severity,
                title=f"{curr.ticker}: OppScore {direction}{abs(opp_delta):.1f}",
                description=(
                    f"Opportunity Score changed from "
                    f"{prev.opportunity_score:.1f} to {curr.opportunity_score:.1f}"
                ),
                previous_value=prev.opportunity_score,
                current_value=curr.opportunity_score,
                delta=round(opp_delta, 2),
            ))

        return alerts

    def _detect_new_signals(
        self,
        prev: OpportunitySnapshot,
        curr: OpportunitySnapshot,
    ) -> list[OpportunityAlert]:
        """Detect newly fired signals not in the previous snapshot."""
        prev_set = set(prev.fired_signals)
        curr_set = set(curr.fired_signals)
        new = list(curr_set - prev_set)

        if len(new) < self.config.new_signal_threshold:
            return []

        severity = AlertSeverity.HIGH if len(new) >= 3 else AlertSeverity.MEDIUM

        return [OpportunityAlert(
            ticker=curr.ticker,
            alert_type=AlertType.NEW_SIGNAL,
            severity=severity,
            title=f"{curr.ticker}: {len(new)} new signal(s)",
            description=f"New signals: {', '.join(new[:5])}",
            previous_value=float(len(prev_set)),
            current_value=float(len(curr_set)),
            delta=float(len(new)),
            new_signals=new,
        )]

    def _detect_tier_change(
        self,
        prev: OpportunitySnapshot,
        curr: OpportunitySnapshot,
    ) -> list[OpportunityAlert]:
        """Detect UOS tier upgrades or downgrades."""
        if not prev.tier or not curr.tier or prev.tier == curr.tier:
            return []

        tier_order = ["Avoid", "Weak", "Moderate", "Strong", "Top Tier"]
        prev_idx = tier_order.index(prev.tier) if prev.tier in tier_order else -1
        curr_idx = tier_order.index(curr.tier) if curr.tier in tier_order else -1

        if prev_idx < 0 or curr_idx < 0:
            return []

        jump = curr_idx - prev_idx
        if jump == 0:
            return []

        direction = "Upgraded" if jump > 0 else "Downgraded"
        severity = (
            AlertSeverity.CRITICAL if abs(jump) >= 2
            else AlertSeverity.HIGH if jump > 0
            else AlertSeverity.MEDIUM
        )

        return [OpportunityAlert(
            ticker=curr.ticker,
            alert_type=AlertType.TIER_CHANGE,
            severity=severity,
            title=f"{curr.ticker}: {direction} to {curr.tier}",
            description=f"Tier changed from {prev.tier} to {curr.tier}",
            previous_value=float(prev_idx),
            current_value=float(curr_idx),
            delta=float(jump),
        )]

    def _detect_alpha_shift(
        self,
        prev: OpportunitySnapshot,
        curr: OpportunitySnapshot,
    ) -> list[OpportunityAlert]:
        """Detect CASE crossing key thresholds (60 up, 40 down)."""
        alerts: list[OpportunityAlert] = []
        cfg = self.config

        # Bullish crossover: crossing 60 upward
        if prev.case_score < cfg.alpha_upper_threshold <= curr.case_score:
            alerts.append(OpportunityAlert(
                ticker=curr.ticker,
                alert_type=AlertType.ALPHA_SHIFT,
                severity=AlertSeverity.HIGH,
                title=f"{curr.ticker}: Alpha crossed {cfg.alpha_upper_threshold}↑",
                description=(
                    f"CASE crossed above {cfg.alpha_upper_threshold}: "
                    f"{prev.case_score:.1f} → {curr.case_score:.1f}"
                ),
                previous_value=prev.case_score,
                current_value=curr.case_score,
                delta=round(curr.case_score - prev.case_score, 2),
            ))

        # Bearish crossunder: crossing 40 downward
        if prev.case_score > cfg.alpha_lower_threshold >= curr.case_score:
            alerts.append(OpportunityAlert(
                ticker=curr.ticker,
                alert_type=AlertType.ALPHA_SHIFT,
                severity=AlertSeverity.LOW,
                title=f"{curr.ticker}: Alpha dropped below {cfg.alpha_lower_threshold}↓",
                description=(
                    f"CASE fell below {cfg.alpha_lower_threshold}: "
                    f"{prev.case_score:.1f} → {curr.case_score:.1f}"
                ),
                previous_value=prev.case_score,
                current_value=curr.case_score,
                delta=round(curr.case_score - prev.case_score, 2),
            ))

        return alerts

    # ── Persistence ───────────────────────────────────────────────────────

    @staticmethod
    def _persist_alerts(alerts: list[OpportunityAlert]) -> None:
        """Save alerts to the database."""
        if not alerts:
            return
        try:
            session = SessionLocal()
            for alert in alerts:
                record = OpportunityAlertRecord(
                    id=alert.id,
                    ticker=alert.ticker,
                    alert_type=alert.alert_type.value,
                    severity=alert.severity.value,
                    title=alert.title,
                    description=alert.description,
                    prev_value=alert.previous_value,
                    curr_value=alert.current_value,
                    delta=alert.delta,
                    new_signals=json.dumps(alert.new_signals),
                    created_at=alert.created_at,
                    read=False,
                )
                session.add(record)
            session.commit()
            logger.info(f"MONITOR: Persisted {len(alerts)} alerts")
        except Exception as exc:
            session.rollback()
            logger.error(f"MONITOR: Failed to persist alerts — {exc}")
        finally:
            session.close()
