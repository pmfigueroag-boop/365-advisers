"""
src/engines/meta_learning/analyzer.py
──────────────────────────────────────────────────────────────────────────────
Meta Analyzer — ranks signals and detects performance trends.
"""

from __future__ import annotations

import logging

from src.engines.meta_learning.models import (
    DetectorHealthSnapshot,
    MetaLearningConfig,
    SignalHealthSnapshot,
    TrendDirection,
)

logger = logging.getLogger("365advisers.meta_learning.analyzer")


class MetaAnalyzer:
    """Ranks signals and detectors, identifies trends."""

    def __init__(self, config: MetaLearningConfig | None = None) -> None:
        self.config = config or MetaLearningConfig()

    def classify_signals(
        self,
        snapshots: list[SignalHealthSnapshot],
    ) -> dict[str, list[SignalHealthSnapshot]]:
        """
        Classify signals into tiers.

        Returns
        -------
        dict with keys: "top_performers", "degrading", "stable", "insufficient"
        """
        cfg = self.config
        top: list[SignalHealthSnapshot] = []
        degrading: list[SignalHealthSnapshot] = []
        stable: list[SignalHealthSnapshot] = []
        insufficient: list[SignalHealthSnapshot] = []

        # Filter by sample size
        valid = [s for s in snapshots if s.sample_size >= cfg.min_sample_size]
        invalid = [s for s in snapshots if s.sample_size < cfg.min_sample_size]

        if not valid:
            return {
                "top_performers": [],
                "degrading": [],
                "stable": [],
                "insufficient": snapshots,
            }

        # Sort by current Sharpe descending
        sorted_by_sharpe = sorted(valid, key=lambda s: s.sharpe_current, reverse=True)

        # Top N% are top performers
        top_n = max(1, int(len(sorted_by_sharpe) * cfg.sharpe_boost_percentile))

        for i, snap in enumerate(sorted_by_sharpe):
            if snap.sharpe_decline_pct >= cfg.sharpe_decline_critical:
                degrading.append(snap)
            elif snap.sharpe_decline_pct >= cfg.sharpe_decline_warn:
                degrading.append(snap)
            elif i < top_n and snap.sharpe_current > 0:
                top.append(snap)
            else:
                stable.append(snap)

        logger.info(
            "META-ANALYZER: %d top, %d degrading, %d stable, %d insufficient",
            len(top), len(degrading), len(stable), len(invalid),
        )

        return {
            "top_performers": top,
            "degrading": degrading,
            "stable": stable,
            "insufficient": invalid,
        }

    def classify_detectors(
        self,
        snapshots: list[DetectorHealthSnapshot],
    ) -> dict[str, list[DetectorHealthSnapshot]]:
        """
        Classify detectors into tiers.

        Returns
        -------
        dict with keys: "promoted", "demoted", "stable"
        """
        cfg = self.config
        promoted: list[DetectorHealthSnapshot] = []
        demoted: list[DetectorHealthSnapshot] = []
        stable: list[DetectorHealthSnapshot] = []

        for snap in snapshots:
            if snap.total_ideas < 5:
                stable.append(snap)
            elif snap.accuracy >= cfg.detector_accuracy_promote:
                promoted.append(snap)
            elif snap.accuracy < cfg.detector_accuracy_demote:
                demoted.append(snap)
            else:
                stable.append(snap)

        logger.info(
            "META-ANALYZER: %d promoted, %d demoted, %d stable detectors",
            len(promoted), len(demoted), len(stable),
        )

        return {
            "promoted": promoted,
            "demoted": demoted,
            "stable": stable,
        }
