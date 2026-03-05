"""
src/engines/backtesting/report_builder.py
──────────────────────────────────────────────────────────────────────────────
Assembles the final BacktestReport from per-signal metrics.

Generates category summaries, identifies top/underperforming signals,
and produces calibration suggestions by comparing empirical half-lives
against the configured DecayConfig values.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from src.engines.alpha_decay.models import DEFAULT_HALF_LIFE_DAYS
from src.engines.alpha_signals.models import SignalCategory
from src.engines.backtesting.models import (
    CalibrationSuggestion,
    CategoryPerformanceReport,
    SignalPerformanceRecord,
)

logger = logging.getLogger("365advisers.backtesting.report_builder")


# ─── Category Report Builder ────────────────────────────────────────────────

def build_category_summaries(
    results: list[SignalPerformanceRecord],
) -> list[CategoryPerformanceReport]:
    """Group signal results by category and compute category-level stats."""
    by_category: dict[SignalCategory, list[SignalPerformanceRecord]] = defaultdict(list)
    for r in results:
        by_category[r.category].append(r)

    summaries: list[CategoryPerformanceReport] = []
    for category, records in sorted(by_category.items(), key=lambda x: x[0].value):
        # Best Sharpe window (use 20-day as the reference)
        ref_window = 20

        sharpes = [r.sharpe_ratio.get(ref_window, 0.0) for r in records]
        hit_rates = [r.hit_rate.get(ref_window, 0.0) for r in records]
        half_lives = [r.empirical_half_life for r in records if r.empirical_half_life is not None]
        excess_returns = [r.avg_excess_return.get(ref_window, 0.0) for r in records]

        avg_sharpe = sum(sharpes) / len(sharpes) if sharpes else 0.0
        avg_hit_rate = sum(hit_rates) / len(hit_rates) if hit_rates else 0.0
        avg_half_life = sum(half_lives) / len(half_lives) if half_lives else None
        category_alpha = sum(excess_returns) / len(excess_returns) if excess_returns else 0.0

        # Best / worst signal
        best = max(records, key=lambda r: r.sharpe_ratio.get(ref_window, 0.0))
        worst = min(records, key=lambda r: r.sharpe_ratio.get(ref_window, 0.0))

        summaries.append(CategoryPerformanceReport(
            category=category,
            signal_count=len(records),
            avg_hit_rate=round(avg_hit_rate, 4),
            avg_sharpe=round(avg_sharpe, 4),
            best_signal=best.signal_id,
            worst_signal=worst.signal_id,
            category_alpha=round(category_alpha, 6),
            empirical_half_life=round(avg_half_life, 1) if avg_half_life else None,
        ))

    return summaries


# ─── Top / Underperforming Signal Identification ────────────────────────────

def identify_top_signals(
    results: list[SignalPerformanceRecord],
    n: int = 10,
) -> list[str]:
    """Return the top N signal IDs by 20-day Sharpe ratio."""
    ranked = sorted(
        results,
        key=lambda r: r.sharpe_ratio.get(20, 0.0),
        reverse=True,
    )
    return [r.signal_id for r in ranked[:n] if r.sharpe_ratio.get(20, 0.0) > 0]


def identify_underperformers(
    results: list[SignalPerformanceRecord],
) -> list[str]:
    """Return signal IDs with negative average excess return at T+20."""
    return [
        r.signal_id
        for r in results
        if r.avg_excess_return.get(20, 0.0) < 0 and r.total_firings >= 10
    ]


# ─── Calibration Suggestions ────────────────────────────────────────────────

def generate_calibration_suggestions(
    results: list[SignalPerformanceRecord],
    gap_threshold: float = 0.30,
) -> list[CalibrationSuggestion]:
    """
    Compare empirical half-lives vs configured DecayConfig values.

    Generates suggestions when the gap exceeds `gap_threshold` (default 30%).
    """
    suggestions: list[CalibrationSuggestion] = []

    for r in results:
        if r.empirical_half_life is None:
            continue
        if r.total_firings < 30:
            continue

        # Get configured half-life for this category
        configured_hl = DEFAULT_HALF_LIFE_DAYS.get(r.category.value, 30.0)
        empirical_hl = r.empirical_half_life

        if configured_hl <= 0:
            continue

        gap = abs(empirical_hl - configured_hl) / configured_hl

        if gap >= gap_threshold:
            suggestions.append(CalibrationSuggestion(
                signal_id=r.signal_id,
                parameter="half_life",
                current_value=configured_hl,
                suggested_value=round(empirical_hl, 1),
                evidence=(
                    f"Empirical half-life is {empirical_hl:.1f}d vs configured "
                    f"{configured_hl:.1f}d ({gap:.0%} gap, n={r.total_firings})"
                ),
                impact_estimate=(
                    f"Aligning decay would improve alpha utilisation for "
                    f"signal '{r.signal_name}'"
                ),
            ))

        # Weight suggestion: underperforming signals with low Sharpe
        best_sharpe = r.sharpe_ratio.get(r.optimal_hold_period or 20, 0.0)
        if best_sharpe < 0 and r.total_firings >= 50:
            suggestions.append(CalibrationSuggestion(
                signal_id=r.signal_id,
                parameter="weight",
                current_value=1.0,  # Default weight
                suggested_value=0.5,
                evidence=(
                    f"Negative Sharpe ({best_sharpe:.2f}) with {r.total_firings} "
                    f"observations suggests this signal adds noise"
                ),
                impact_estimate="Halving weight would reduce noise in composite alpha",
            ))

    logger.info(f"CALIBRATION: Generated {len(suggestions)} suggestions")
    return suggestions
