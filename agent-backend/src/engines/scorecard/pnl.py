"""
src/engines/scorecard/pnl.py
─────────────────────────────────────────────────────────────────────────────
PnLCalculator — Computes P&L metrics from tracked signal fires:
  • Hit rate (live, per horizon)
  • Information ratio
  • Alpha vs benchmark
  • Signal stability (rolling consistency)
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from src.data.database import SessionLocal

logger = logging.getLogger("365advisers.scorecard.pnl")


class PnLCalculator:
    """Calculates live P&L metrics from tracked signal performance."""

    def compute_signal_metrics(
        self, signal_id: str, horizon: str = "20d"
    ) -> dict:
        """Compute performance metrics for a single signal.

        Args:
            signal_id: The signal identifier.
            horizon: Return horizon to evaluate ("1d", "5d", "20d", "60d").

        Returns:
            Dict with hit_rate, avg_return, avg_excess, information_ratio,
            stability, and pnl_contribution.
        """
        from src.data.database import LiveSignalTrackingRecord

        horizon_col = self._horizon_column(horizon)
        if not horizon_col:
            return {"error": f"Unknown horizon: {horizon}"}

        with SessionLocal() as db:
            records = (
                db.query(LiveSignalTrackingRecord)
                .filter(
                    LiveSignalTrackingRecord.signal_id == signal_id,
                    getattr(LiveSignalTrackingRecord, horizon_col).isnot(None),
                )
                .all()
            )

        if not records:
            return self._empty_metrics(signal_id)

        returns = [getattr(r, horizon_col) for r in records]
        benchmark_returns = [
            getattr(r, f"benchmark_{horizon_col}", 0.0) or 0.0
            for r in records
        ]
        excess = [r - b for r, b in zip(returns, benchmark_returns)]

        n = len(returns)
        hit_rate = sum(1 for r in returns if r > 0) / n if n > 0 else 0.0
        avg_return = sum(returns) / n if n > 0 else 0.0
        avg_excess = sum(excess) / n if n > 0 else 0.0

        # Information Ratio = mean(excess) / std(excess)
        if n > 1:
            variance = sum((e - avg_excess) ** 2 for e in excess) / (n - 1)
            tracking_error = math.sqrt(variance) if variance > 0 else 1e-6
            information_ratio = avg_excess / tracking_error
        else:
            information_ratio = 0.0

        # Signal stability: rolling hit-rate consistency
        stability = self._compute_stability(returns)

        return {
            "signal_id": signal_id,
            "horizon": horizon,
            "total_firings": n,
            "hit_rate": round(hit_rate, 4),
            "avg_return": round(avg_return, 6),
            "avg_excess_return": round(avg_excess, 6),
            "information_ratio": round(information_ratio, 4),
            "signal_stability": round(stability, 4),
            "pnl_contribution_bps": round(avg_excess * 10000, 2),
        }

    def compute_all_signals(self, horizon: str = "20d") -> list[dict]:
        """Compute metrics for all tracked signals."""
        from src.data.database import LiveSignalTrackingRecord

        with SessionLocal() as db:
            signal_ids = (
                db.query(LiveSignalTrackingRecord.signal_id)
                .distinct()
                .all()
            )

        return [
            self.compute_signal_metrics(sid[0], horizon)
            for sid in signal_ids
        ]

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _horizon_column(horizon: str) -> str | None:
        mapping = {
            "1d": "return_1d",
            "5d": "return_5d",
            "20d": "return_20d",
            "60d": "return_60d",
        }
        return mapping.get(horizon)

    @staticmethod
    def _compute_stability(returns: list[float], window: int = 10) -> float:
        """Compute rolling hit-rate consistency.

        Uses a sliding window to measure how stable the hit rate is
        across sequential firings.  Returns a value in [0, 1].
        """
        if len(returns) < window:
            return 0.5  # insufficient data → neutral

        rolling_hit_rates = []
        for i in range(len(returns) - window + 1):
            chunk = returns[i : i + window]
            hr = sum(1 for r in chunk if r > 0) / window
            rolling_hit_rates.append(hr)

        if not rolling_hit_rates:
            return 0.5

        mean_hr = sum(rolling_hit_rates) / len(rolling_hit_rates)
        variance = sum((h - mean_hr) ** 2 for h in rolling_hit_rates) / len(
            rolling_hit_rates
        )
        # Low variance → high stability
        stability = max(0.0, 1.0 - math.sqrt(variance) * 4)
        return min(stability, 1.0)

    @staticmethod
    def _empty_metrics(signal_id: str) -> dict:
        return {
            "signal_id": signal_id,
            "horizon": "20d",
            "total_firings": 0,
            "hit_rate": 0.0,
            "avg_return": 0.0,
            "avg_excess_return": 0.0,
            "information_ratio": 0.0,
            "signal_stability": 0.5,
            "pnl_contribution_bps": 0.0,
        }
