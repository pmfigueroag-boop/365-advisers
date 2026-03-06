"""
src/engines/backtesting/recalibration_engine.py
──────────────────────────────────────────────────────────────────────────────
Automated Signal Recalibration Engine.

Scans all signals for performance degradation, generates recalibration
suggestions, and optionally applies them to the live signal registry.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.alpha_signals.registry import registry as signal_registry
from src.engines.backtesting.models import (
    CalibrationRecord,
    CalibrationSuggestion,
    SignalPerformanceEvent,
    SignalScorecard,
)
from src.engines.backtesting.performance_repository import SignalPerformanceRepository
from src.engines.backtesting.performance_service import SignalPerformanceService
from src.engines.backtesting.rolling_analyzer import (
    DegradationReport,
    DegradationSeverity,
    RollingAnalyzer,
    RollingPerformanceSnapshot,
)
from src.data.database import (
    DegradationAlertRecord,
    RollingPerformanceRecord,
    SessionLocal,
)

logger = logging.getLogger("365advisers.backtesting.recalibration_engine")


class RecalibrationEngine:
    """
    Automated signal recalibration based on rolling performance.

    Usage::

        engine = RecalibrationEngine()
        degraded = engine.scan_for_degradation()
        suggestions = engine.generate_recalibration_plan(degraded)
        results = engine.auto_apply(suggestions, dry_run=True)
    """

    def __init__(
        self,
        degradation_threshold: float = 0.20,
        critical_threshold: float = 0.40,
    ) -> None:
        self._perf_repo = SignalPerformanceRepository
        self._perf_service = SignalPerformanceService()
        self._analyzer = RollingAnalyzer(
            degradation_threshold=degradation_threshold,
            critical_threshold=critical_threshold,
        )

    # ── Degradation Scanning ──────────────────────────────────────────────

    def scan_for_degradation(self) -> list[DegradationReport]:
        """
        Check all signals for performance degradation.

        Compares 30D rolling Sharpe to full-history Sharpe.
        If decline > threshold, flag for recalibration.

        Returns
        -------
        list[DegradationReport]
        """
        all_reports: list[DegradationReport] = []
        enabled_signals = signal_registry.get_enabled()

        for sig_def in enabled_signals:
            try:
                events = self._perf_repo.get_events_for_signal(sig_def.id)
                if len(events) < 30:
                    continue

                reports = self._analyzer.detect_degradation(
                    signal_id=sig_def.id,
                    events=events,
                    signal_name=sig_def.name,
                )

                if reports:
                    # Persist alerts to DB
                    self._save_degradation_alerts(reports)
                    all_reports.extend(reports)

            except Exception as exc:
                logger.error(
                    "RECALIBRATION: Error scanning %s — %s", sig_def.id, exc,
                )

        logger.info(
            "RECALIBRATION: Scanned %d signals, found %d degradation alerts",
            len(enabled_signals), len(all_reports),
        )
        return all_reports

    def compute_rolling_snapshots(self) -> list[RollingPerformanceSnapshot]:
        """
        Compute and persist rolling performance snapshots for all signals.

        Returns
        -------
        list[RollingPerformanceSnapshot]
        """
        all_snapshots: list[RollingPerformanceSnapshot] = []
        enabled_signals = signal_registry.get_enabled()

        for sig_def in enabled_signals:
            try:
                events = self._perf_repo.get_events_for_signal(sig_def.id)
                if len(events) < 5:
                    continue

                snapshots = self._analyzer.compute_rolling_metrics(
                    signal_id=sig_def.id,
                    events=events,
                )

                # Persist to DB
                self._save_rolling_snapshots(snapshots)
                all_snapshots.extend(snapshots)

            except Exception as exc:
                logger.error(
                    "RECALIBRATION: Error computing rolling for %s — %s",
                    sig_def.id, exc,
                )

        logger.info(
            "RECALIBRATION: Computed %d rolling snapshots for %d signals",
            len(all_snapshots), len(enabled_signals),
        )
        return all_snapshots

    # ── Recalibration Plan ────────────────────────────────────────────────

    def generate_recalibration_plan(
        self,
        degraded: list[DegradationReport],
    ) -> list[CalibrationSuggestion]:
        """
        Produce specific calibration suggestions based on degradation reports.

        Rules:
        - Sharpe declined >40%: suggest weight reduction (0.5x)
        - Sharpe declined >60%: suggest disabling signal
        - Hit rate <45%: suggest threshold tightening (+10%)
        - Half-life shrunk >50%: suggest half_life update

        Parameters
        ----------
        degraded : list[DegradationReport]
            Output from scan_for_degradation().

        Returns
        -------
        list[CalibrationSuggestion]
        """
        suggestions: list[CalibrationSuggestion] = []

        for report in degraded:
            sig_def = signal_registry.get(report.signal_id)
            if not sig_def:
                continue

            if report.metric == "sharpe":
                if report.severity == DegradationSeverity.CRITICAL:
                    # Suggest weight reduction
                    current_weight = sig_def.weight
                    new_weight = round(current_weight * 0.5, 4)
                    suggestions.append(CalibrationSuggestion(
                        signal_id=report.signal_id,
                        parameter="weight",
                        current_value=current_weight,
                        suggested_value=new_weight,
                        evidence=(
                            f"Sharpe degraded {abs(report.decline_pct)*100:.0f}% "
                            f"from {report.peak_value:.3f} to {report.current_value:.3f}"
                        ),
                        impact_estimate="Reduces signal influence by 50%",
                    ))

                    # If very severe, suggest disable
                    if abs(report.decline_pct) >= 0.60:
                        suggestions.append(CalibrationSuggestion(
                            signal_id=report.signal_id,
                            parameter="enabled",
                            current_value=1.0,
                            suggested_value=0.0,
                            evidence=(
                                f"Sharpe collapsed {abs(report.decline_pct)*100:.0f}% — "
                                f"signal may have lost predictive power"
                            ),
                            impact_estimate="Removes signal from evaluation",
                        ))

            elif report.metric == "hit_rate":
                if report.current_value < 0.45:
                    # Suggest threshold tightening
                    current_thresh = sig_def.threshold
                    # Tighten by 10% (raise threshold to require stronger signal)
                    new_thresh = round(current_thresh * 1.10, 6)
                    suggestions.append(CalibrationSuggestion(
                        signal_id=report.signal_id,
                        parameter="threshold",
                        current_value=current_thresh,
                        suggested_value=new_thresh,
                        evidence=(
                            f"Hit rate degraded to {report.current_value:.1%} "
                            f"(from {report.peak_value:.1%}). "
                            f"Tightening threshold to filter weaker firings."
                        ),
                        impact_estimate="Fewer firings, higher precision",
                    ))

        logger.info(
            "RECALIBRATION: Generated %d suggestions from %d degradation reports",
            len(suggestions), len(degraded),
        )
        return suggestions

    # ── Auto-Apply ────────────────────────────────────────────────────────

    def auto_apply(
        self,
        suggestions: list[CalibrationSuggestion],
        dry_run: bool = True,
    ) -> list[CalibrationRecord]:
        """
        Apply suggestions to the live registry.

        Parameters
        ----------
        suggestions : list[CalibrationSuggestion]
            From generate_recalibration_plan().
        dry_run : bool
            If True, only simulate — do not modify registry.

        Returns
        -------
        list[CalibrationRecord]
            Audit trail of applied changes.
        """
        records: list[CalibrationRecord] = []

        for suggestion in suggestions:
            record = CalibrationRecord(
                signal_id=suggestion.signal_id,
                parameter=suggestion.parameter,
                old_value=suggestion.current_value,
                new_value=suggestion.suggested_value,
                evidence=suggestion.evidence,
                applied_by="auto_dry" if dry_run else "auto",
            )

            if not dry_run:
                try:
                    sig_def = signal_registry.get(suggestion.signal_id)
                    if sig_def is None:
                        continue

                    if suggestion.parameter == "weight":
                        sig_def.weight = suggestion.suggested_value
                    elif suggestion.parameter == "threshold":
                        sig_def.threshold = suggestion.suggested_value
                    elif suggestion.parameter == "enabled":
                        if suggestion.suggested_value == 0.0:
                            signal_registry.disable(suggestion.signal_id)

                    # Log to performance repository
                    self._perf_repo.log_calibration(record)

                    logger.info(
                        "RECALIBRATION: Applied %s=%s for %s (was %s)",
                        suggestion.parameter,
                        suggestion.suggested_value,
                        suggestion.signal_id,
                        suggestion.current_value,
                    )
                except Exception as exc:
                    logger.error(
                        "RECALIBRATION: Failed to apply %s for %s — %s",
                        suggestion.parameter, suggestion.signal_id, exc,
                    )
                    continue

            records.append(record)

        mode = "DRY RUN" if dry_run else "LIVE"
        logger.info(
            "RECALIBRATION [%s]: %d suggestions processed",
            mode, len(records),
        )
        return records

    # ── Top Performers ────────────────────────────────────────────────────

    def identify_top_performers(self, top_n: int = 10) -> list[str]:
        """
        Signals with highest rolling Sharpe — candidates for weight boost.

        Returns list of signal IDs sorted by recent Sharpe.
        """
        scorecards = self._perf_service.get_all_scorecards()
        if not scorecards:
            return []

        # Sort by Sharpe descending
        sorted_cards = sorted(
            scorecards,
            key=lambda s: s.sharpe_20d,
            reverse=True,
        )

        top = [s.signal_id for s in sorted_cards[:top_n] if s.sharpe_20d > 0]
        logger.info(
            "RECALIBRATION: Top %d performers: %s",
            len(top), top,
        )
        return top

    # ── Persistence Helpers ───────────────────────────────────────────────

    @staticmethod
    def _save_degradation_alerts(reports: list[DegradationReport]) -> None:
        """Persist degradation alerts to DB."""
        try:
            with SessionLocal() as db:
                for report in reports:
                    record = DegradationAlertRecord(
                        signal_id=report.signal_id,
                        signal_name=report.signal_name,
                        metric=report.metric,
                        peak_value=report.peak_value,
                        current_value=report.current_value,
                        decline_pct=report.decline_pct,
                        recommendation=report.recommendation,
                    )
                    db.add(record)
                db.commit()
        except Exception as exc:
            logger.error("RECALIBRATION: Failed to save alerts — %s", exc)

    @staticmethod
    def _save_rolling_snapshots(snapshots: list[RollingPerformanceSnapshot]) -> None:
        """Persist rolling performance snapshots to DB."""
        try:
            with SessionLocal() as db:
                for snap in snapshots:
                    record = RollingPerformanceRecord(
                        signal_id=snap.signal_id,
                        window_days=snap.window_days,
                        as_of_date=snap.as_of_date.isoformat(),
                        hit_rate=snap.hit_rate,
                        sharpe=snap.sharpe,
                        avg_return=snap.avg_return,
                        avg_excess=snap.avg_excess_return,
                        sample_size=snap.sample_size,
                        regime=snap.regime.value if snap.regime else None,
                    )
                    db.add(record)
                db.commit()
        except Exception as exc:
            logger.error("RECALIBRATION: Failed to save snapshots — %s", exc)
