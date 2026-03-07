"""
src/engines/concept_drift/aggregator.py
──────────────────────────────────────────────────────────────────────────────
Drift Aggregator — combines individual detector results into a
severity-rated DriftAlert.
"""

from __future__ import annotations

import logging

from src.engines.concept_drift.models import (
    DriftAlert,
    DriftConfig,
    DriftDetection,
    DriftSeverity,
)

logger = logging.getLogger("365advisers.concept_drift.aggregator")


class DriftAggregator:
    """Combines multiple DriftDetection results into a single DriftAlert."""

    def aggregate(
        self,
        signal_id: str,
        detections: list[DriftDetection],
        config: DriftConfig,
        signal_name: str = "",
    ) -> DriftAlert:
        """
        Combine detector results into a severity-rated alert.

        Severity rules:
          - 3 detectors active OR KS p < critical → CRITICAL
          - 2 detectors active → WARNING
          - 1 detector active → INFO
          - 0 → INFO (no drift)
        """
        active = sum(1 for d in detections if d.detected)

        # Check for critical KS p-value
        ks_critical = False
        for d in detections:
            if d.detector == "distribution_shift" and d.p_value is not None:
                if d.p_value < config.ks_critical_alpha:
                    ks_critical = True

        # Determine severity
        if active >= 3 or ks_critical:
            severity = DriftSeverity.CRITICAL.value
            action = "disable_signal"
        elif active >= 2:
            severity = DriftSeverity.WARNING.value
            action = "reduce_weight"
        elif active >= 1:
            severity = DriftSeverity.INFO.value
            action = "monitor"
        else:
            severity = DriftSeverity.INFO.value
            action = "none"

        # Composite drift score [0, 1]
        drift_score = min(1.0, active / 3.0)
        # Boost score for critical KS
        if ks_critical:
            drift_score = max(drift_score, 0.9)

        return DriftAlert(
            signal_id=signal_id,
            signal_name=signal_name,
            severity=severity,
            detections=detections,
            active_detectors=active,
            recommended_action=action,
            drift_score=round(drift_score, 4),
        )
