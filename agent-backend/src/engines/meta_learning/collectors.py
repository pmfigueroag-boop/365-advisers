"""
src/engines/meta_learning/collectors.py
──────────────────────────────────────────────────────────────────────────────
Data collectors that aggregate performance metrics from various subsystems.

Collectors:
  - SignalCollector: from BacktestRepository (Sharpe, hit rate, sample size)
  - DetectorCollector: from OpportunityTracker (detector accuracy)
  - RegimeCollector: from RegimeWeightRepository (best/worst regime per signal)
"""

from __future__ import annotations

import logging

from src.engines.meta_learning.models import (
    DetectorHealthSnapshot,
    SignalHealthSnapshot,
    TrendDirection,
)

logger = logging.getLogger("365advisers.meta_learning.collectors")


class SignalCollector:
    """Collects per-signal performance data from the backtest database."""

    def collect(self, lookback_days: int = 90) -> list[SignalHealthSnapshot]:
        """
        Gather signal health snapshots from BacktestRepository.

        Returns
        -------
        list[SignalHealthSnapshot]
        """
        snapshots = []
        try:
            from src.engines.backtesting.repository import BacktestRepository
            repo = BacktestRepository

            all_records = repo.get_all_latest()
            if not all_records:
                logger.info("SIGNAL-COLLECTOR: No backtest records found")
                return snapshots

            for record in all_records:
                ref_window = 20
                sharpe_full = record.sharpe_ratio.get(ref_window, 0.0)
                hit_rate = record.hit_rate.get(ref_window, 0.0)
                sample = record.sample_size

                # Try to get rolling (recent) Sharpe
                sharpe_rolling = sharpe_full
                try:
                    from src.engines.backtesting.rolling_analyzer import RollingAnalyzer
                    analyzer = RollingAnalyzer()
                    rolling = analyzer.compute_rolling(
                        record.signal_id, window_days=30,
                    )
                    if rolling and rolling[-1].sharpe_ratio:
                        sharpe_rolling = rolling[-1].sharpe_ratio.get(ref_window, sharpe_full)
                except Exception:
                    pass

                decline = 0.0
                if sharpe_full > 0:
                    decline = max(0, (sharpe_full - sharpe_rolling) / sharpe_full)

                # Determine trend
                if decline > 0.20:
                    trend = TrendDirection.DEGRADING.value
                elif sharpe_rolling > sharpe_full * 1.1:
                    trend = TrendDirection.IMPROVING.value
                else:
                    trend = TrendDirection.STABLE.value

                snapshots.append(SignalHealthSnapshot(
                    signal_id=record.signal_id,
                    signal_name=getattr(record, "signal_name", ""),
                    sharpe_current=round(sharpe_rolling, 4),
                    sharpe_baseline=round(sharpe_full, 4),
                    sharpe_decline_pct=round(decline, 4),
                    hit_rate=round(hit_rate, 4),
                    sample_size=sample,
                    trend=trend,
                ))

        except Exception as exc:
            logger.warning("SIGNAL-COLLECTOR: Failed — %s", exc)

        logger.info("SIGNAL-COLLECTOR: Collected %d signal snapshots", len(snapshots))
        return snapshots


class DetectorCollector:
    """Collects per-detector accuracy from OpportunityTracker."""

    def collect(self) -> list[DetectorHealthSnapshot]:
        """
        Gather detector health snapshots.

        Returns
        -------
        list[DetectorHealthSnapshot]
        """
        snapshots = []
        try:
            from src.engines.opportunity_tracking.tracker import OpportunityTracker
            tracker = OpportunityTracker()

            accuracy_data = tracker.get_detector_accuracy()
            if not accuracy_data:
                logger.info("DETECTOR-COLLECTOR: No detector data found")
                return snapshots

            for det_type, stats in accuracy_data.items():
                total = stats.get("total", 0)
                positive = stats.get("positive", 0)
                accuracy = stats.get("accuracy", 0.0)
                avg_ret = stats.get("avg_return", 0.0)

                # Trend based on accuracy
                if accuracy >= 0.60:
                    trend = TrendDirection.IMPROVING.value
                elif accuracy < 0.40:
                    trend = TrendDirection.DEGRADING.value
                else:
                    trend = TrendDirection.STABLE.value

                snapshots.append(DetectorHealthSnapshot(
                    detector_type=det_type,
                    total_ideas=total,
                    positive_ideas=positive,
                    accuracy=round(accuracy, 4),
                    avg_return=round(avg_ret, 6),
                    trend=trend,
                ))

        except Exception as exc:
            logger.warning("DETECTOR-COLLECTOR: Failed — %s", exc)

        logger.info("DETECTOR-COLLECTOR: Collected %d detector snapshots", len(snapshots))
        return snapshots


class RegimeCollector:
    """Collects regime-specific insights from regime weight profiles."""

    def enrich_with_regime(
        self,
        snapshots: list[SignalHealthSnapshot],
    ) -> list[SignalHealthSnapshot]:
        """
        Add best/worst regime info to each signal snapshot.

        Modifies snapshots in-place and returns them.
        """
        try:
            from src.engines.regime_weights.repository import RegimeWeightRepository
            repo = RegimeWeightRepository()

            for snap in snapshots:
                profile = repo.get_signal_profile(snap.signal_id)
                if profile:
                    snap.best_regime = profile.get("best_regime", "")
                    snap.worst_regime = profile.get("worst_regime", "")

        except Exception as exc:
            logger.warning("REGIME-COLLECTOR: Failed — %s", exc)

        return snapshots
