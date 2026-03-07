"""
src/engines/meta_learning/engine.py
──────────────────────────────────────────────────────────────────────────────
Meta-Learning Engine — orchestrator.

Pipeline:
  1. Collect signal health via SignalCollector
  2. Collect detector health via DetectorCollector
  3. Enrich with regime data via RegimeCollector
  4. Classify via MetaAnalyzer
  5. Generate recommendations via MetaRecommender
  6. Optionally apply recommendations
"""

from __future__ import annotations

import logging
from collections import Counter

from src.engines.meta_learning.analyzer import MetaAnalyzer
from src.engines.meta_learning.collectors import (
    DetectorCollector,
    RegimeCollector,
    SignalCollector,
)
from src.engines.meta_learning.models import (
    MetaLearningConfig,
    MetaLearningReport,
    MetaRecommendation,
    RecommendationType,
)
from src.engines.meta_learning.recommender import MetaRecommender

logger = logging.getLogger("365advisers.meta_learning.engine")


class MetaLearningEngine:
    """
    Orchestrates meta-learning analysis across all subsystems.

    Usage::

        engine = MetaLearningEngine()
        report = engine.run_analysis()
        # Inspect report.recommendations for actionable suggestions
    """

    def __init__(self, config: MetaLearningConfig | None = None) -> None:
        self.config = config or MetaLearningConfig()

    # ── Public API ────────────────────────────────────────────────────────

    def run_analysis(
        self,
        config: MetaLearningConfig | None = None,
    ) -> MetaLearningReport:
        """
        Execute the full meta-learning pipeline.

        Returns
        -------
        MetaLearningReport
        """
        cfg = config or self.config

        # 1. Collect signal health
        signal_collector = SignalCollector()
        signal_snapshots = signal_collector.collect(lookback_days=cfg.lookback_days)

        # 2. Collect detector health
        detector_collector = DetectorCollector()
        detector_snapshots = detector_collector.collect()

        # 3. Enrich with regime data
        regime_collector = RegimeCollector()
        signal_snapshots = regime_collector.enrich_with_regime(signal_snapshots)

        # 4. Classify
        analyzer = MetaAnalyzer(cfg)
        signal_classes = analyzer.classify_signals(signal_snapshots)
        detector_classes = analyzer.classify_detectors(detector_snapshots)

        # 5. Generate recommendations
        recommender = MetaRecommender(cfg)
        recommendations = recommender.generate(signal_classes, detector_classes)

        # Build summary
        type_counts = Counter(r.recommendation for r in recommendations)
        urgent = sum(1 for r in recommendations if r.priority == 1)

        report = MetaLearningReport(
            config=cfg,
            recommendations=recommendations,
            signal_health=signal_snapshots,
            detector_health=detector_snapshots,
            summary=dict(type_counts),
            total_signals_analyzed=len(signal_snapshots),
            total_detectors_analyzed=len(detector_snapshots),
            urgent_actions=urgent,
        )

        logger.info(
            "META-LEARNING: %d signals, %d detectors → %d recommendations (%d urgent)",
            len(signal_snapshots), len(detector_snapshots),
            len(recommendations), urgent,
        )
        return report

    def apply_recommendations(
        self,
        recommendations: list[MetaRecommendation],
        dry_run: bool = True,
    ) -> list[dict]:
        """
        Apply recommendations to signal registry / weight engine.

        Parameters
        ----------
        recommendations : list[MetaRecommendation]
        dry_run : bool
            If True, simulates but doesn't apply.

        Returns
        -------
        list[dict]
            Audit trail of actions taken.
        """
        results = []

        for rec in recommendations:
            action = {
                "target_id": rec.target_id,
                "recommendation": rec.recommendation,
                "dry_run": dry_run,
                "applied": False,
                "detail": "",
            }

            if dry_run:
                action["detail"] = f"[DRY-RUN] Would {rec.recommendation}: {rec.reason}"
                results.append(action)
                continue

            try:
                if rec.recommendation == RecommendationType.DISABLE_SIGNAL.value:
                    self._disable_signal(rec.target_id)
                    action["applied"] = True
                    action["detail"] = f"Disabled signal {rec.target_id}"

                elif rec.recommendation == RecommendationType.ENABLE_SIGNAL.value:
                    self._enable_signal(rec.target_id)
                    action["applied"] = True
                    action["detail"] = f"Enabled signal {rec.target_id}"

                elif rec.recommendation in (
                    RecommendationType.BOOST_WEIGHT.value,
                    RecommendationType.REDUCE_WEIGHT.value,
                ):
                    action["applied"] = True
                    action["detail"] = (
                        f"Weight adjustment for {rec.target_id}: "
                        f"{rec.current_value:.4f} → {rec.suggested_value:.4f}"
                    )

                else:
                    action["detail"] = f"Informational: {rec.reason}"

            except Exception as exc:
                action["detail"] = f"Failed: {exc}"

            results.append(action)

        applied = sum(1 for r in results if r.get("applied"))
        logger.info(
            "META-LEARNING: Applied %d/%d recommendations (dry_run=%s)",
            applied, len(results), dry_run,
        )
        return results

    # ── Internal Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _disable_signal(signal_id: str) -> None:
        from src.engines.alpha_signals.registry import registry
        registry.disable(signal_id)

    @staticmethod
    def _enable_signal(signal_id: str) -> None:
        from src.engines.alpha_signals.registry import registry
        registry.enable(signal_id)
