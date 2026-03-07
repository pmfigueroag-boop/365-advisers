"""
src/engines/meta_learning/recommender.py
──────────────────────────────────────────────────────────────────────────────
Recommender — applies decision rules to classified signals and detectors
to produce actionable MetaRecommendations.
"""

from __future__ import annotations

import logging

from src.engines.meta_learning.models import (
    DetectorHealthSnapshot,
    MetaLearningConfig,
    MetaRecommendation,
    RecommendationType,
    SignalHealthSnapshot,
)

logger = logging.getLogger("365advisers.meta_learning.recommender")


class MetaRecommender:
    """Generates recommendations from classified signals and detectors."""

    def __init__(self, config: MetaLearningConfig | None = None) -> None:
        self.config = config or MetaLearningConfig()

    def generate(
        self,
        signal_classes: dict[str, list[SignalHealthSnapshot]],
        detector_classes: dict[str, list[DetectorHealthSnapshot]],
    ) -> list[MetaRecommendation]:
        """
        Produce recommendations from classified data.

        Parameters
        ----------
        signal_classes : dict
            Output from MetaAnalyzer.classify_signals()
        detector_classes : dict
            Output from MetaAnalyzer.classify_detectors()

        Returns
        -------
        list[MetaRecommendation]
        """
        recs: list[MetaRecommendation] = []

        # Signal recommendations
        recs.extend(self._signal_boost_recs(signal_classes.get("top_performers", [])))
        recs.extend(self._signal_degradation_recs(signal_classes.get("degrading", [])))

        # Detector recommendations
        recs.extend(self._detector_promote_recs(detector_classes.get("promoted", [])))
        recs.extend(self._detector_demote_recs(detector_classes.get("demoted", [])))

        # Sort by priority then confidence
        recs.sort(key=lambda r: (r.priority, -r.confidence))

        logger.info("META-RECOMMENDER: Generated %d recommendations", len(recs))
        return recs

    # ── Signal Recommendations ────────────────────────────────────────────

    def _signal_boost_recs(
        self,
        top_signals: list[SignalHealthSnapshot],
    ) -> list[MetaRecommendation]:
        """Boost weight for top-performing signals."""
        cfg = self.config
        recs = []
        for snap in top_signals:
            recs.append(MetaRecommendation(
                target_id=snap.signal_id,
                target_name=snap.signal_name,
                recommendation=RecommendationType.BOOST_WEIGHT.value,
                reason=(
                    f"Top-performing signal: Sharpe={snap.sharpe_current:.2f}, "
                    f"HitRate={snap.hit_rate:.1%}, n={snap.sample_size}"
                ),
                current_value=snap.current_weight,
                suggested_value=round(snap.current_weight * cfg.boost_multiplier, 4),
                confidence=min(0.9, 0.5 + snap.sample_size / 200),
                priority=3,
            ))
        return recs

    def _signal_degradation_recs(
        self,
        degrading_signals: list[SignalHealthSnapshot],
    ) -> list[MetaRecommendation]:
        """Reduce or disable degrading signals."""
        cfg = self.config
        recs = []
        for snap in degrading_signals:
            if snap.sharpe_decline_pct >= 0.60:
                # Critical: suggest disable
                recs.append(MetaRecommendation(
                    target_id=snap.signal_id,
                    target_name=snap.signal_name,
                    recommendation=RecommendationType.DISABLE_SIGNAL.value,
                    reason=(
                        f"Critical degradation: Sharpe declined {snap.sharpe_decline_pct:.0%} "
                        f"(from {snap.sharpe_baseline:.2f} to {snap.sharpe_current:.2f})"
                    ),
                    current_value=snap.current_weight,
                    suggested_value=0.0,
                    confidence=min(0.95, 0.6 + snap.sample_size / 200),
                    priority=1,
                ))
            elif snap.sharpe_decline_pct >= cfg.sharpe_decline_critical:
                # Major: suggest weight reduction
                recs.append(MetaRecommendation(
                    target_id=snap.signal_id,
                    target_name=snap.signal_name,
                    recommendation=RecommendationType.REDUCE_WEIGHT.value,
                    reason=(
                        f"Significant degradation: Sharpe declined {snap.sharpe_decline_pct:.0%} "
                        f"(from {snap.sharpe_baseline:.2f} to {snap.sharpe_current:.2f})"
                    ),
                    current_value=snap.current_weight,
                    suggested_value=round(snap.current_weight * cfg.reduce_multiplier, 4),
                    confidence=min(0.85, 0.5 + snap.sample_size / 200),
                    priority=2,
                ))
            else:
                # Warning
                recs.append(MetaRecommendation(
                    target_id=snap.signal_id,
                    target_name=snap.signal_name,
                    recommendation=RecommendationType.REDUCE_WEIGHT.value,
                    reason=(
                        f"Early degradation: Sharpe declined {snap.sharpe_decline_pct:.0%}"
                    ),
                    current_value=snap.current_weight,
                    suggested_value=round(snap.current_weight * 0.8, 4),
                    confidence=0.5,
                    priority=3,
                ))
        return recs

    # ── Detector Recommendations ─────────────────────────────────────────

    def _detector_promote_recs(
        self,
        promoted: list[DetectorHealthSnapshot],
    ) -> list[MetaRecommendation]:
        """Promote high-accuracy detectors."""
        recs = []
        for snap in promoted:
            recs.append(MetaRecommendation(
                target_id=snap.detector_type,
                target_name=snap.detector_type,
                recommendation=RecommendationType.PROMOTE_DETECTOR.value,
                reason=(
                    f"High accuracy: {snap.accuracy:.1%} hit rate "
                    f"across {snap.total_ideas} ideas, avg return {snap.avg_return:.2%}"
                ),
                current_value=snap.accuracy,
                suggested_value=snap.accuracy,
                confidence=min(0.9, 0.4 + snap.total_ideas / 50),
                priority=3,
            ))
        return recs

    def _detector_demote_recs(
        self,
        demoted: list[DetectorHealthSnapshot],
    ) -> list[MetaRecommendation]:
        """Demote underperforming detectors."""
        recs = []
        for snap in demoted:
            recs.append(MetaRecommendation(
                target_id=snap.detector_type,
                target_name=snap.detector_type,
                recommendation=RecommendationType.DEMOTE_DETECTOR.value,
                reason=(
                    f"Low accuracy: {snap.accuracy:.1%} hit rate "
                    f"across {snap.total_ideas} ideas"
                ),
                current_value=snap.accuracy,
                suggested_value=snap.accuracy,
                confidence=min(0.85, 0.4 + snap.total_ideas / 50),
                priority=2,
            ))
        return recs
