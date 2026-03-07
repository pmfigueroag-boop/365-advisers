"""
src/engines/concept_drift/engine.py
──────────────────────────────────────────────────────────────────────────────
Concept Drift Engine — orchestrator.

Pipeline:
  1. For each signal, split returns into baseline vs recent
  2. Run 3 detectors (KS, correlation, CUSUM)
  3. Aggregate into severity-rated DriftAlerts
"""

from __future__ import annotations

import logging

from src.engines.backtesting.models import SignalEvent
from src.engines.concept_drift.aggregator import DriftAggregator
from src.engines.concept_drift.detectors import (
    CorrelationBreakdownDetector,
    DistributionShiftDetector,
    RegimeShiftDetector,
)
from src.engines.concept_drift.models import (
    ConceptDriftReport,
    DriftConfig,
    DriftSeverity,
)

logger = logging.getLogger("365advisers.concept_drift.engine")


class ConceptDriftEngine:
    """
    Detects structural changes that invalidate historical signal patterns.

    Usage::

        engine = ConceptDriftEngine()
        report = engine.analyze(events_by_signal)
    """

    def __init__(self, config: DriftConfig | None = None) -> None:
        self.config = config or DriftConfig()

    def analyze(
        self,
        events_by_signal: dict[str, list[SignalEvent]],
        config: DriftConfig | None = None,
        forward_window: int = 20,
    ) -> ConceptDriftReport:
        """
        Run full drift detection pipeline.

        Parameters
        ----------
        events_by_signal : dict
            {signal_id: [SignalEvent, ...]}
        config : DriftConfig | None
        forward_window : int

        Returns
        -------
        ConceptDriftReport
        """
        cfg = config or self.config

        ks_detector = DistributionShiftDetector()
        corr_detector = CorrelationBreakdownDetector()
        cusum_detector = RegimeShiftDetector()
        aggregator = DriftAggregator()

        alerts = []

        for signal_id, events in events_by_signal.items():
            # Sort events by date
            sorted_events = sorted(events, key=lambda e: e.fired_date)

            # Extract returns
            all_returns = [
                e.forward_returns.get(forward_window, 0.0)
                for e in sorted_events
                if e.forward_returns.get(forward_window) is not None
            ]
            all_values = [e.value for e in sorted_events]

            if len(all_returns) < cfg.min_samples * 2:
                continue

            # Split into baseline and recent
            split_idx = len(all_returns) - cfg.rolling_window_days
            if split_idx < cfg.min_samples:
                split_idx = len(all_returns) // 2

            baseline_returns = all_returns[:split_idx]
            recent_returns = all_returns[split_idx:]
            baseline_values = all_values[:split_idx]
            recent_values = all_values[split_idx:]

            # Run 3 detectors
            detections = []

            detection_ks = ks_detector.detect(baseline_returns, recent_returns, cfg)
            detections.append(detection_ks)

            detection_corr = corr_detector.detect(
                baseline_values, baseline_returns,
                recent_values, recent_returns,
                cfg,
            )
            detections.append(detection_corr)

            detection_cusum = cusum_detector.detect(all_returns, cfg)
            detections.append(detection_cusum)

            # Aggregate
            alert = aggregator.aggregate(
                signal_id=signal_id,
                detections=detections,
                config=cfg,
            )
            alerts.append(alert)

        # Count severities
        drifting = sum(1 for a in alerts if a.active_detectors > 0)
        critical_c = sum(1 for a in alerts if a.severity == DriftSeverity.CRITICAL.value)
        warning_c = sum(1 for a in alerts if a.severity == DriftSeverity.WARNING.value)

        report = ConceptDriftReport(
            config=cfg,
            alerts=alerts,
            total_signals_scanned=len(events_by_signal),
            drifting_signals=drifting,
            critical_count=critical_c,
            warning_count=warning_c,
        )

        logger.info(
            "CONCEPT-DRIFT: %d signals scanned → %d drifting (%d critical, %d warning)",
            len(events_by_signal), drifting, critical_c, warning_c,
        )
        return report
