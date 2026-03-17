"""
src/engines/backtesting/top_bottom_validator.py
--------------------------------------------------------------------------
Top–Bottom Portfolio Test (TBPT) — Long-Short Spread Analysis.

For each signal, groups events by fired_date, ranks by confidence,
splits into Top (highest 20%) and Bottom (lowest 20%) quintiles, then
computes the Long-Short Spread (top excess return - bottom excess return).

Method
~~~~~~
1. Group signal events by fired_date (cross-sectional slices)
2. For each date with enough events:
   - Sort by confidence (descending)
   - Top quintile = top 20% by confidence
   - Bottom quintile = bottom 20% by confidence
   - Slice spread = avg(top excess returns) - avg(bottom excess returns)
3. Aggregate across dates:
   - spread = mean(slice spreads)
   - t-stat = spread / (std(slice spreads) / √N)
   - Significant if |t_stat| > 2.0

Integration
~~~~~~~~~~~
Produces ``spread`` and ``spread_t_stat`` that can be attached to
``ParameterChange`` for governor gating (Rule 5e).

Also computes the full 5-quintile return curve and a monotonicity score
(normalized Kendall tau) to verify that returns increase monotonically
with signal confidence.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date, datetime, timezone

from pydantic import BaseModel, Field

from src.engines.backtesting.models import SignalEvent

logger = logging.getLogger("365advisers.backtesting.top_bottom")


# ── Contracts ────────────────────────────────────────────────────────────────

class SignalTopBottomResult(BaseModel):
    """Top-Bottom test result for a single signal."""
    signal_id: str
    signal_name: str = ""
    total_events: int = 0
    n_periods: int = Field(
        0, ge=0, description="Number of cross-sectional date slices used",
    )

    # Per-quintile returns
    top_avg_return: float = Field(
        0.0, description="Avg excess return@20d of top confidence quintile",
    )
    bottom_avg_return: float = Field(
        0.0, description="Avg excess return@20d of bottom confidence quintile",
    )

    # Spread metrics
    spread: float = Field(
        0.0,
        description="top_avg_return - bottom_avg_return. "
        "Positive = signal discriminates correctly.",
    )
    spread_t_stat: float = Field(
        0.0,
        description="t-statistic of spread: spread / (std / √N). "
        "|t| > 2.0 = statistically significant.",
    )
    is_significant: bool = Field(
        False,
        description="True if |spread_t_stat| > 2.0",
    )
    has_negative_spread: bool = Field(
        False,
        description="True if spread < 0 (signal ranks backwards)",
    )

    # Monotonic Return Curve
    quintile_returns: list[float] = Field(
        default_factory=list,
        description="Avg excess return per quintile [Q1(low conf)..Q5(high conf)]. "
        "Monotonically increasing = ideal.",
    )
    monotonicity_score: float = Field(
        0.0,
        description="Normalized Kendall tau of quintile returns curve. "
        "1.0 = perfectly monotonic increasing, 0.0 = random, <0 = inverted.",
    )


class TopBottomReport(BaseModel):
    """Full top-bottom portfolio test output."""
    signal_results: list[SignalTopBottomResult] = Field(default_factory=list)
    quintile_pct: float = 0.20
    total_signals: int = 0
    significant_count: int = Field(
        0, ge=0, description="Signals with |t-stat| > 2.0",
    )
    negative_spread_count: int = Field(
        0, ge=0, description="Signals with negative spread (backwards)",
    )
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Engine ───────────────────────────────────────────────────────────────────

_REF_WINDOW = 20
_MIN_EVENTS_PER_SLICE = 5  # min events in a date slice for quintile sort


class TopBottomValidator:
    """
    Top-Bottom Portfolio Test engine.

    Usage::

        validator = TopBottomValidator(quintile_pct=0.20)
        report = validator.validate(events, signal_meta)
    """

    def __init__(
        self,
        quintile_pct: float = 0.20,
        min_periods: int = 5,
    ) -> None:
        """
        Parameters
        ----------
        quintile_pct : float
            Fraction of events in top/bottom quintile (0.10-0.50).
        min_periods : int
            Minimum cross-sectional date slices needed for t-stat.
        """
        if not (0.10 <= quintile_pct <= 0.50):
            raise ValueError("quintile_pct must be between 0.10 and 0.50")
        if min_periods < 3:
            raise ValueError("min_periods must be >= 3")

        self.quintile_pct = quintile_pct
        self.min_periods = min_periods

    def validate(
        self,
        events: list[SignalEvent],
        signal_meta: dict[str, str] | None = None,
    ) -> TopBottomReport:
        """
        Run top-bottom portfolio test on backtest events.

        Parameters
        ----------
        events : list[SignalEvent]
            All signal events from a completed backtest.
        signal_meta : dict[str, str] | None
            Optional signal_id → signal_name mapping.
        """
        if not events:
            return TopBottomReport(quintile_pct=self.quintile_pct)

        signal_meta = signal_meta or {}

        # Group by signal
        by_signal: dict[str, list[SignalEvent]] = defaultdict(list)
        for e in events:
            by_signal[e.signal_id].append(e)

        results: list[SignalTopBottomResult] = []

        for sig_id in sorted(by_signal.keys()):
            sig_events = by_signal[sig_id]
            result = self._evaluate_signal(sig_id, sig_events)
            result.signal_name = signal_meta.get(sig_id, sig_id)
            results.append(result)

        significant = sum(1 for r in results if r.is_significant)
        neg_spread = sum(1 for r in results if r.has_negative_spread)

        report = TopBottomReport(
            signal_results=results,
            quintile_pct=self.quintile_pct,
            total_signals=len(results),
            significant_count=significant,
            negative_spread_count=neg_spread,
        )

        logger.info(
            "TOP-BOTTOM: %d signals tested — %d significant, %d negative spread "
            "(%.0f%% quintile)",
            report.total_signals, report.significant_count,
            report.negative_spread_count, self.quintile_pct * 100,
        )

        return report

    # ── Internal ─────────────────────────────────────────────────────────

    def _evaluate_signal(
        self,
        signal_id: str,
        events: list[SignalEvent],
    ) -> SignalTopBottomResult:
        """Evaluate a single signal's top-bottom spread."""
        # Group by fired_date (cross-sectional slices)
        by_date: dict[date, list[SignalEvent]] = defaultdict(list)
        for e in events:
            if _REF_WINDOW in e.excess_returns:
                by_date[e.fired_date].append(e)

        # Compute per-date spread and quintile accumulators
        slice_spreads: list[float] = []
        all_top_returns: list[float] = []
        all_bottom_returns: list[float] = []
        quintile_sums: dict[int, float] = {i: 0.0 for i in range(5)}
        quintile_counts: dict[int, int] = {i: 0 for i in range(5)}

        for d in sorted(by_date.keys()):
            slice_events = by_date[d]
            if len(slice_events) < _MIN_EVENTS_PER_SLICE:
                continue

            # Sort by confidence descending
            sorted_events = sorted(
                slice_events, key=lambda e: e.confidence, reverse=True,
            )

            n = len(sorted_events)
            top_n = max(1, int(n * self.quintile_pct))
            bottom_n = max(1, int(n * self.quintile_pct))

            top_events = sorted_events[:top_n]
            bottom_events = sorted_events[-bottom_n:]

            top_returns = [
                e.excess_returns.get(_REF_WINDOW, 0.0) for e in top_events
            ]
            bottom_returns = [
                e.excess_returns.get(_REF_WINDOW, 0.0) for e in bottom_events
            ]

            top_avg = sum(top_returns) / len(top_returns)
            bottom_avg = sum(bottom_returns) / len(bottom_returns)

            slice_spreads.append(top_avg - bottom_avg)
            all_top_returns.extend(top_returns)
            all_bottom_returns.extend(bottom_returns)

            # ── Quintile curve: split into 5 buckets ────────────
            n_q = max(1, n // 5)
            for q_idx in range(5):
                start = q_idx * n_q
                end = start + n_q if q_idx < 4 else n
                q_events = sorted_events[start:end]
                q_returns = [
                    e.excess_returns.get(_REF_WINDOW, 0.0) for e in q_events
                ]
                if q_returns:
                    # Note: sorted descending by conf, so q_idx=0 is TOP (Q5)
                    quintile_sums[q_idx] += sum(q_returns)
                    quintile_counts[q_idx] += len(q_returns)

        if len(slice_spreads) < self.min_periods:
            return SignalTopBottomResult(
                signal_id=signal_id,
                total_events=len(events),
                n_periods=len(slice_spreads),
            )

        # Quintile returns: reverse so Q1=low conf, Q5=high conf
        quintile_returns_raw = []
        for q_idx in range(5):
            if quintile_counts[q_idx] > 0:
                quintile_returns_raw.append(
                    quintile_sums[q_idx] / quintile_counts[q_idx]
                )
            else:
                quintile_returns_raw.append(0.0)
        # Reverse: index 0 was top (Q5), we want Q1..Q5 ascending by conf
        quintile_returns = list(reversed(quintile_returns_raw))
        monotonicity = self._kendall_tau_normalized(quintile_returns)

        # Aggregate
        spread = sum(slice_spreads) / len(slice_spreads)
        spread_std = self._std(slice_spreads)
        n_periods = len(slice_spreads)

        if spread_std > 1e-9:
            t_stat = spread / (spread_std / math.sqrt(n_periods))
        else:
            t_stat = 0.0

        top_avg = (
            sum(all_top_returns) / len(all_top_returns)
            if all_top_returns else 0.0
        )
        bottom_avg = (
            sum(all_bottom_returns) / len(all_bottom_returns)
            if all_bottom_returns else 0.0
        )

        return SignalTopBottomResult(
            signal_id=signal_id,
            total_events=len(events),
            n_periods=n_periods,
            top_avg_return=round(top_avg, 6),
            bottom_avg_return=round(bottom_avg, 6),
            spread=round(spread, 6),
            spread_t_stat=round(t_stat, 4),
            is_significant=abs(t_stat) > 2.0,
            has_negative_spread=spread < 0,
            quintile_returns=[round(r, 6) for r in quintile_returns],
            monotonicity_score=round(monotonicity, 4),
        )

    @staticmethod
    def _std(values: list[float]) -> float:
        """Standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / len(values)
        return math.sqrt(var) if var > 0 else 0.0

    @staticmethod
    def _kendall_tau_normalized(values: list[float]) -> float:
        """
        Normalized Kendall tau for a list of values.

        Counts concordant vs discordant pairs and normalizes to [-1, 1].
        1.0 = perfectly increasing, -1.0 = perfectly decreasing.
        """
        n = len(values)
        if n < 2:
            return 0.0

        concordant = 0
        discordant = 0
        for i in range(n):
            for j in range(i + 1, n):
                if values[j] > values[i]:
                    concordant += 1
                elif values[j] < values[i]:
                    discordant += 1
                # ties don't count

        total_pairs = n * (n - 1) / 2
        if total_pairs == 0:
            return 0.0

        return (concordant - discordant) / total_pairs
