"""
src/engines/validation_dashboard/aggregator.py
──────────────────────────────────────────────────────────────────────────────
Data aggregation for the Validation Intelligence Dashboard.

Collects data from all QVF modules and assembles the unified response:
  - SignalPerformanceService → scorecards
  - RecalibrationEngine → degradation alerts + suggestions
  - OpportunityTracker → detector accuracy + idea performance
  - WalkForwardRepository → stability scores
  - CostModelRepository → cost resilience
  - BenchmarkFactorRepository → alpha source
"""

from __future__ import annotations

import logging
from collections import defaultdict

from src.engines.validation_dashboard.models import (
    DetectorPerformanceSection,
    OpportunityTrackingSection,
    SignalLeaderboard,
    SignalLeaderboardEntry,
    SystemHealthSection,
    ValidationIntelligence,
)

logger = logging.getLogger("365advisers.validation_dashboard.aggregator")


class DashboardAggregator:
    """
    Collects data from all QVF modules and assembles the dashboard.

    Usage::

        aggregator = DashboardAggregator()
        dashboard = aggregator.aggregate()
    """

    def aggregate(self) -> ValidationIntelligence:
        """
        Aggregate all QVF data into a single dashboard response.

        Gracefully handles missing data from any module.
        """
        leaderboard = self._build_leaderboard()
        detector_perf = self._build_detector_performance()
        opp_tracking = self._build_opportunity_tracking()
        system_health = self._build_system_health()

        result = ValidationIntelligence(
            leaderboard=leaderboard,
            detector_performance=detector_perf,
            opportunity_tracking=opp_tracking,
            system_health=system_health,
        )

        logger.info(
            "DASHBOARD: Aggregated — %d signals, %d detectors, %d ideas, %d alerts",
            leaderboard.total_signals,
            detector_perf.total_detectors,
            opp_tracking.total_ideas,
            system_health.active_degradation_alerts,
        )
        return result

    # ── Section Builders ─────────────────────────────────────────────────

    def _build_leaderboard(self) -> SignalLeaderboard:
        """Build signal leaderboard from scorecards + enrichment data."""
        try:
            from src.engines.backtesting.performance_service import SignalPerformanceService
            from src.engines.backtesting.recalibration_engine import RecalibrationEngine

            perf_service = SignalPerformanceService()
            recal_engine = RecalibrationEngine()

            scorecards = perf_service.get_all_scorecards()
            degraded = recal_engine.scan_for_degradation()

            # Get enrichment maps
            stability_map = self._get_stability_map()
            cost_map = self._get_cost_map()
            factor_map = self._get_factor_map()

            # Build entries
            entries: list[SignalLeaderboardEntry] = []
            for sc in scorecards:
                stab = stability_map.get(sc.signal_id, {})
                cost = cost_map.get(sc.signal_id, {})
                factor = factor_map.get(sc.signal_id, {})

                entries.append(SignalLeaderboardEntry(
                    signal_id=sc.signal_id,
                    signal_name=sc.signal_name,
                    category=sc.category,
                    sharpe_20d=sc.sharpe_20d,
                    hit_rate_20d=sc.hit_rate_20d,
                    avg_alpha_20d=sc.avg_return_20d,
                    quality_tier=sc.quality_tier,
                    total_events=sc.total_events,
                    stability_class=stab.get("stability_class"),
                    stability_score=stab.get("stability_score"),
                    cost_resilience=cost.get("cost_resilience"),
                    cost_drag_bps=cost.get("cost_drag_bps"),
                    alpha_source=factor.get("alpha_source"),
                    factor_alpha=factor.get("factor_alpha"),
                ))

            # Sort by Sharpe
            entries.sort(key=lambda e: e.sharpe_20d, reverse=True)

            # Compute aggregates
            sharpes = [e.sharpe_20d for e in entries if e.total_events > 0]
            hrs = [e.hit_rate_20d for e in entries if e.total_events > 0]
            pure_alpha = sum(
                1 for e in entries if e.alpha_source == "pure_alpha"
            )

            return SignalLeaderboard(
                total_signals=len(entries),
                avg_sharpe=round(sum(sharpes) / max(len(sharpes), 1), 4),
                avg_hit_rate=round(sum(hrs) / max(len(hrs), 1), 4),
                degrading_count=len(degraded),
                pure_alpha_count=pure_alpha,
                top_signals=entries[:10],
                bottom_signals=entries[-10:] if len(entries) > 10 else [],
                degrading_signals=degraded,
            )
        except Exception as exc:
            logger.warning("DASHBOARD: Leaderboard build failed — %s", exc)
            return SignalLeaderboard()

    def _build_detector_performance(self) -> DetectorPerformanceSection:
        """Build detector accuracy section."""
        try:
            from src.engines.opportunity_tracking.tracker import OpportunityTracker

            tracker = OpportunityTracker()
            accuracy_map = tracker.get_detector_accuracy()
            summary = tracker.get_performance_summary()

            detectors = list(accuracy_map.values()) if accuracy_map else []
            by_confidence = summary.by_confidence if summary else {}

            best = max(detectors, key=lambda d: d.hit_rate).label if detectors else ""
            worst = min(detectors, key=lambda d: d.hit_rate).label if detectors else ""

            return DetectorPerformanceSection(
                detectors=detectors,
                by_confidence=by_confidence,
                best_detector=best,
                worst_detector=worst,
                total_detectors=len(detectors),
            )
        except Exception as exc:
            logger.warning("DASHBOARD: Detector performance build failed — %s", exc)
            return DetectorPerformanceSection()

    def _build_opportunity_tracking(self) -> OpportunityTrackingSection:
        """Build opportunity tracking section."""
        try:
            from src.engines.opportunity_tracking.tracker import OpportunityTracker

            tracker = OpportunityTracker()
            summary = tracker.get_performance_summary()

            if summary:
                return OpportunityTrackingSection(
                    summary=summary,
                    total_ideas=summary.total_ideas,
                    hit_rate_20d=summary.hit_rate_20d,
                    avg_return_20d=summary.avg_return_20d,
                    avg_excess_20d=summary.avg_excess_return_20d,
                )
            return OpportunityTrackingSection()
        except Exception as exc:
            logger.warning("DASHBOARD: Opportunity tracking build failed — %s", exc)
            return OpportunityTrackingSection()

    def _build_system_health(self) -> SystemHealthSection:
        """Build system health section from all QVF modules."""
        try:
            from src.engines.backtesting.recalibration_engine import RecalibrationEngine

            recal = RecalibrationEngine()
            degraded = recal.scan_for_degradation()
            suggestions = recal.generate_recalibration_plan(degraded)

            # Stability distribution
            stability_dist, avg_stab = self._get_stability_distribution()

            # Cost distribution
            cost_dist, avg_drag = self._get_cost_distribution()

            # Alpha source distribution
            alpha_dist, avg_neutrality = self._get_alpha_distribution()

            # Half-life data
            avg_hl, fast_decay = self._get_decay_stats()

            return SystemHealthSection(
                stability_distribution=stability_dist,
                avg_stability_score=avg_stab,
                avg_half_life_days=avg_hl,
                signals_with_fast_decay=fast_decay,
                cost_distribution=cost_dist,
                avg_cost_drag_bps=avg_drag,
                alpha_source_distribution=alpha_dist,
                avg_factor_neutrality=avg_neutrality,
                pending_recalibrations=len(suggestions),
                active_degradation_alerts=len(degraded),
                recalibration_suggestions=suggestions[:10],
            )
        except Exception as exc:
            logger.warning("DASHBOARD: System health build failed — %s", exc)
            return SystemHealthSection()

    # ── Data Source Helpers ───────────────────────────────────────────────

    def _get_stability_map(self) -> dict[str, dict]:
        """Get walk-forward stability data for all signals."""
        try:
            from src.engines.walk_forward.repository import WalkForwardRepository
            repo = WalkForwardRepository()
            runs = repo.list_runs(limit=1)
            if not runs:
                return {}
            # The summary contains signal-level data
            run_id = runs[0].get("run_id", "")
            summary = repo.get_run_summary(run_id)
            if not summary:
                return {}
            result = {}
            for sig in summary.get("signal_summaries", []):
                result[sig.get("signal_id", "")] = {
                    "stability_class": sig.get("stability_class"),
                    "stability_score": sig.get("stability_score"),
                }
            return result
        except Exception:
            return {}

    def _get_cost_map(self) -> dict[str, dict]:
        """Get cost resilience data for all signals."""
        try:
            from src.engines.cost_model.repository import CostModelRepository
            repo = CostModelRepository()
            # Get profiles from a recent run (signal → profile)
            # Try to load from most recent data
            from src.data.database import CostModelProfileRecord, SessionLocal
            with SessionLocal() as db:
                rows = (
                    db.query(CostModelProfileRecord)
                    .order_by(CostModelProfileRecord.created_at.desc())
                    .limit(200)
                    .all()
                )
            result = {}
            for r in rows:
                if r.signal_id not in result:
                    resilience = "fragile"
                    if r.cost_resilience and r.cost_resilience >= 0.70:
                        resilience = "resilient"
                    elif r.cost_resilience and r.cost_resilience >= 0.40:
                        resilience = "moderate"
                    result[r.signal_id] = {
                        "cost_resilience": resilience,
                        "cost_drag_bps": r.cost_drag_bps,
                    }
            return result
        except Exception:
            return {}

    def _get_factor_map(self) -> dict[str, dict]:
        """Get factor alpha source data for all signals."""
        try:
            from src.data.database import BenchmarkFactorProfileRecord, SessionLocal
            with SessionLocal() as db:
                rows = (
                    db.query(BenchmarkFactorProfileRecord)
                    .order_by(BenchmarkFactorProfileRecord.created_at.desc())
                    .limit(200)
                    .all()
                )
            result = {}
            for r in rows:
                if r.signal_id not in result:
                    result[r.signal_id] = {
                        "alpha_source": r.alpha_source,
                        "factor_alpha": r.factor_alpha,
                    }
            return result
        except Exception:
            return {}

    def _get_stability_distribution(self) -> tuple[dict[str, int], float]:
        """Get distribution of stability classes."""
        stab_map = self._get_stability_map()
        dist: dict[str, int] = defaultdict(int)
        scores = []
        for data in stab_map.values():
            cls = data.get("stability_class", "overfit")
            if cls:
                dist[cls] = dist.get(cls, 0) + 1
            sc = data.get("stability_score")
            if sc is not None:
                scores.append(sc)
        avg = sum(scores) / max(len(scores), 1) if scores else 0.0
        return dict(dist), round(avg, 4)

    def _get_cost_distribution(self) -> tuple[dict[str, int], float]:
        """Get distribution of cost resilience classes."""
        cost_map = self._get_cost_map()
        dist: dict[str, int] = defaultdict(int)
        drags = []
        for data in cost_map.values():
            cls = data.get("cost_resilience", "fragile")
            dist[cls] = dist.get(cls, 0) + 1
            drag = data.get("cost_drag_bps")
            if drag is not None:
                drags.append(drag)
        avg = sum(drags) / max(len(drags), 1) if drags else 0.0
        return dict(dist), round(avg, 2)

    def _get_alpha_distribution(self) -> tuple[dict[str, int], float]:
        """Get distribution of alpha sources."""
        factor_map = self._get_factor_map()
        dist: dict[str, int] = defaultdict(int)
        neutralities = []
        for data in factor_map.values():
            src = data.get("alpha_source", "factor_beta")
            dist[src] = dist.get(src, 0) + 1
        # For neutrality we'd need r_squared, approximate from alpha_source
        return dict(dist), 0.0

    def _get_decay_stats(self) -> tuple[float | None, int]:
        """Get alpha decay statistics."""
        try:
            from src.engines.backtesting.performance_service import SignalPerformanceService
            service = SignalPerformanceService()
            scorecards = service.get_all_scorecards()
            half_lives = [
                sc.empirical_half_life
                for sc in scorecards
                if sc.empirical_half_life is not None and sc.empirical_half_life > 0
            ]
            if not half_lives:
                return None, 0
            avg_hl = sum(half_lives) / len(half_lives)
            fast = sum(1 for hl in half_lives if hl < 10)  # Fast decay: < 10 days
            return round(avg_hl, 1), fast
        except Exception:
            return None, 0
