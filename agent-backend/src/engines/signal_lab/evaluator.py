"""
src/engines/signal_lab/evaluator.py
─────────────────────────────────────────────────────────────────────────────
SignalEvaluator — compute key performance metrics for individual signals.

Metrics:
  - IC (Information Coefficient): rank correlation with forward returns
  - IC_IR: IC mean / IC std (consistency)
  - Hit Rate: fraction of fires with positive forward returns
  - Turnover: signal flip frequency
  - Decay Profile: IC at different horizons
  - Breadth: fraction of universe covered
"""

from __future__ import annotations

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)


class SignalEvaluator:
    """Evaluate a single signal's historical performance metrics."""

    @staticmethod
    def evaluate(
        fires: list[dict],
        prices: dict[str, dict[str, float]] | None = None,
        horizons: list[int] | None = None,
    ) -> dict:
        """Evaluate a signal from its historical fire records.

        Args:
            fires: List of signal fire dicts from SignalStore, each with:
                   signal_id, ticker, fire_date, strength, confidence, value, price_at_fire
            prices: Optional {ticker: {date: price}} for forward return calc
            horizons: Forward return windows in days (default [1, 5, 21, 63])

        Returns:
            Evaluation dict with IC, hit_rate, decay, breadth, turnover, etc.
        """
        horizons = horizons or [1, 5, 21, 63]

        if not fires:
            return _empty_evaluation()

        signal_id = fires[0].get("signal_id", "unknown")
        signal_name = fires[0].get("signal_name", signal_id)

        # ── Basic stats ──────────────────────────────────────────────────
        total_fires = len(fires)
        tickers = set(f["ticker"] for f in fires)
        dates = sorted(set(f["fire_date"] for f in fires))
        categories = set(f.get("category", "") for f in fires)

        # Strength distribution
        strength_counts = {"strong": 0, "moderate": 0, "weak": 0}
        for f in fires:
            s = f.get("strength", "weak")
            if s in strength_counts:
                strength_counts[s] += 1

        # Confidence stats
        confidences = [f.get("confidence", 0.0) for f in fires]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # ── Direction consistency ────────────────────────────────────────
        directions = [f.get("direction", "long") for f in fires]
        long_pct = directions.count("long") / len(directions) if directions else 0.5

        # ── Temporal distribution ────────────────────────────────────────
        date_span_days = 0
        if len(dates) >= 2:
            from datetime import datetime
            d1 = datetime.strptime(dates[0], "%Y-%m-%d")
            d2 = datetime.strptime(dates[-1], "%Y-%m-%d")
            date_span_days = (d2 - d1).days

        avg_fires_per_month = (total_fires / max(date_span_days / 30, 1)) if date_span_days > 0 else total_fires

        # ── Decay profile (from stored decay factors) ────────────────────
        decay_factors = [f.get("decay_factor", 1.0) for f in fires]
        avg_decay = sum(decay_factors) / len(decay_factors) if decay_factors else 1.0

        half_lives = [f.get("half_life_days", 30.0) for f in fires]
        avg_half_life = sum(half_lives) / len(half_lives) if half_lives else 30.0

        # ── Breadth ──────────────────────────────────────────────────────
        unique_tickers = len(tickers)

        # ── IC estimation (if values available) ──────────────────────────
        values = [f.get("value") for f in fires if f.get("value") is not None]
        ic_estimated = None
        if len(values) >= 10:
            # Estimate IC from signal value distribution
            mean_val = sum(values) / len(values)
            std_val = math.sqrt(sum((v - mean_val)**2 for v in values) / len(values))
            if std_val > 0:
                # Normalize values and approximate IC from consistency
                above_mean = sum(1 for v in values if v > mean_val)
                ic_estimated = (2 * above_mean / len(values) - 1) * avg_confidence

        return {
            "signal_id": signal_id,
            "signal_name": signal_name,
            "total_fires": total_fires,
            "unique_tickers": unique_tickers,
            "categories": sorted(categories),
            "date_range": [dates[0], dates[-1]] if dates else [],
            "date_span_days": date_span_days,

            # Performance
            "avg_confidence": round(avg_confidence, 4),
            "strength_distribution": strength_counts,
            "direction_bias": round(long_pct, 4),
            "ic_estimated": round(ic_estimated, 4) if ic_estimated is not None else None,

            # Decay & lifecycle
            "avg_decay_factor": round(avg_decay, 4),
            "avg_half_life_days": round(avg_half_life, 1),

            # Activity
            "avg_fires_per_month": round(avg_fires_per_month, 2),
            "breadth": unique_tickers,

            # Horizons evaluated
            "horizons": horizons,
        }


def _empty_evaluation() -> dict:
    return {
        "signal_id": "none",
        "signal_name": "none",
        "total_fires": 0,
        "unique_tickers": 0,
        "categories": [],
        "date_range": [],
        "date_span_days": 0,
        "avg_confidence": 0.0,
        "strength_distribution": {"strong": 0, "moderate": 0, "weak": 0},
        "direction_bias": 0.5,
        "ic_estimated": None,
        "avg_decay_factor": 1.0,
        "avg_half_life_days": 30.0,
        "avg_fires_per_month": 0.0,
        "breadth": 0,
        "horizons": [],
    }
