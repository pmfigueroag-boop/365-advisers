"""
src/engines/backtesting/performance_service.py
──────────────────────────────────────────────────────────────────────────────
Signal Performance Service — scorecards, recalibration, and CASE integration.

Queries stored performance events to produce live SignalScorecards,
applies parameter recalibrations, and provides tier-based weight
multipliers for the Composite Alpha Score Engine.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime, timezone

from src.engines.alpha_signals.registry import registry as signal_registry
from src.engines.backtesting.models import (
    CalibrationRecord,
    CalibrationSuggestion,
    SignalScorecard,
    TIER_MULTIPLIERS,
)
from src.engines.backtesting.performance_repository import SignalPerformanceRepository
from src.engines.backtesting.repository import BacktestRepository

logger = logging.getLogger("365advisers.backtesting.performance_service")

# ── Reference window for tier classification ─────────────────────────────────
_REF_WINDOW = 20


class SignalPerformanceService:
    """
    High-level service for signal performance analysis.

    Provides scorecards, recalibration, and CASE weight multipliers.
    """

    def __init__(self) -> None:
        self._perf_repo = SignalPerformanceRepository
        self._bt_repo = BacktestRepository

    # ── Scorecards ────────────────────────────────────────────────────────

    def get_scorecard(self, signal_id: str) -> SignalScorecard | None:
        """
        Compute a live SignalScorecard from stored performance data.

        Uses the latest backtest results (aggregated) rather than
        re-computing from raw events, for speed.
        """
        record = self._bt_repo.get_signal_latest(signal_id)
        if not record or record.total_firings < 10:
            return None

        # Get signal definition for name/category
        sig_def = signal_registry.get(signal_id)
        name = sig_def.name if sig_def else record.signal_name
        category = sig_def.category.value if sig_def else record.category.value

        hit_rate = record.hit_rate.get(_REF_WINDOW, 0.0)
        avg_ret = record.avg_return.get(_REF_WINDOW, 0.0)
        sharpe = record.sharpe_ratio.get(_REF_WINDOW, 0.0)

        # Quality tier classification
        tier = self._classify_tier(sharpe, hit_rate, record.confidence_level)

        # Last calibration date
        last_cal = self._perf_repo.get_last_calibration_date(signal_id)

        return SignalScorecard(
            signal_id=signal_id,
            signal_name=name,
            category=category,
            total_events=record.total_firings,
            hit_rate_20d=round(hit_rate, 4),
            avg_return_20d=round(avg_ret, 6),
            sharpe_20d=round(sharpe, 4),
            confidence_level=record.confidence_level,
            empirical_half_life=record.empirical_half_life,
            last_calibrated=last_cal,
            quality_tier=tier,
        )

    def get_all_scorecards(self) -> list[SignalScorecard]:
        """Get scorecards for all signals with sufficient data."""
        scorecards: list[SignalScorecard] = []
        for sig in signal_registry.get_enabled():
            sc = self.get_scorecard(sig.id)
            if sc:
                scorecards.append(sc)
        return scorecards

    def get_category_alpha(self, category: str) -> dict:
        """Get aggregate performance for a signal category."""
        runs = self._bt_repo.list_runs(limit=1)
        if not runs:
            return {"category": category, "avg_sharpe": 0.0, "signal_count": 0}

        results = self._bt_repo.get_results(runs[0].run_id)
        cat_results = [r for r in results if r.category.value == category]

        if not cat_results:
            return {"category": category, "avg_sharpe": 0.0, "signal_count": 0}

        avg_sharpe = sum(
            r.sharpe_ratio.get(_REF_WINDOW, 0.0) for r in cat_results
        ) / len(cat_results)

        return {
            "category": category,
            "avg_sharpe": round(avg_sharpe, 4),
            "signal_count": len(cat_results),
        }

    # ── Recalibration ─────────────────────────────────────────────────────

    def apply_calibration(
        self,
        suggestion: CalibrationSuggestion,
        run_id: str = "",
        applied_by: str = "auto",
    ) -> CalibrationRecord | None:
        """
        Apply a calibration suggestion to the signal registry.

        Updates the in-memory registry and logs the change to the
        calibration history table.
        """
        sig = signal_registry.get(suggestion.signal_id)
        if not sig:
            logger.warning(f"CALIBRATION: Signal {suggestion.signal_id} not found")
            return None

        old_value = suggestion.current_value

        # Apply the change to the registry
        if suggestion.parameter == "weight":
            sig.weight = suggestion.suggested_value
        elif suggestion.parameter == "threshold":
            sig.threshold = suggestion.suggested_value
        elif suggestion.parameter == "half_life":
            # Half-life is managed by DecayConfig, not the signal itself.
            # Log the suggestion but don't modify here.
            pass
        else:
            logger.warning(f"CALIBRATION: Unknown parameter '{suggestion.parameter}'")
            return None

        # Create audit record
        record = CalibrationRecord(
            signal_id=suggestion.signal_id,
            parameter=suggestion.parameter,
            old_value=old_value,
            new_value=suggestion.suggested_value,
            evidence=suggestion.evidence,
            run_id=run_id,
            applied_by=applied_by,
        )

        # Persist the audit trail
        self._perf_repo.save_calibration(record)

        logger.info(
            f"CALIBRATION: Applied {suggestion.parameter} change for "
            f"{suggestion.signal_id}: {old_value} → {suggestion.suggested_value}"
        )

        return record

    # ── CASE Integration ──────────────────────────────────────────────────

    def get_tier_multipliers(self) -> dict[str, float]:
        """
        Return {signal_id: multiplier} for all signals with backtest data.

        Used by CompositeAlphaEngine to scale per-signal weights based
        on empirically validated performance.
        """
        multipliers: dict[str, float] = {}
        for sig in signal_registry.get_enabled():
            sc = self.get_scorecard(sig.id)
            if sc:
                multipliers[sig.id] = TIER_MULTIPLIERS.get(sc.quality_tier, 1.0)
            # Signals without backtest data keep multiplier 1.0 (no change)

        logger.info(
            f"CASE-TIERS: Generated multipliers for {len(multipliers)} signals"
        )
        return multipliers

    # ── Internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _classify_tier(sharpe: float, hit_rate: float, confidence: str) -> str:
        """
        Classify a signal into a quality tier.

        A — Sharpe ≥ 1.5, Hit Rate ≥ 60%, Confidence HIGH
        B — Sharpe ≥ 0.8, Hit Rate ≥ 55%, Confidence MEDIUM+
        C — Sharpe ≥ 0.3, Hit Rate ≥ 50%
        D — Below all thresholds
        """
        if sharpe >= 1.5 and hit_rate >= 0.60 and confidence == "HIGH":
            return "A"
        elif sharpe >= 0.8 and hit_rate >= 0.55 and confidence in ("HIGH", "MEDIUM"):
            return "B"
        elif sharpe >= 0.3 and hit_rate >= 0.50:
            return "C"
        return "D"
