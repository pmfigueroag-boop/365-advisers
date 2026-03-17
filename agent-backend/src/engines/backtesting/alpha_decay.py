"""
src/engines/backtesting/alpha_decay.py
--------------------------------------------------------------------------
Alpha Decay Modeling — measures how quickly signal alpha dissipates over time.

For each signal, computes excess returns at multiple forward windows
[5, 10, 20, 40, 60] days and fits an exponential decay curve:

    α(t) = α₀ × e^(-λt)

Where:
    α₀ = initial alpha at shortest window
    λ  = decay rate
    t  = time in trading days

Outputs:
    - Decay half-life: t½ = ln(2) / λ
    - Optimal holding period (where marginal alpha ≈ 0)
    - Per-window excess return averages

Usage::

    engine = AlphaDecayEngine()
    report = engine.analyze(events)
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from src.engines.backtesting.models import SignalEvent

logger = logging.getLogger("365advisers.backtesting.alpha_decay")


# ── Contracts ────────────────────────────────────────────────────────────────

class AlphaDecayResult(BaseModel):
    """Decay analysis for a single signal."""
    signal_id: str
    signal_name: str = ""
    n_events: int = 0

    # Per-window average excess returns
    window_returns: dict[int, float] = Field(
        default_factory=dict,
        description="{window_days: avg_excess_return}",
    )

    # Fitted decay parameters
    alpha_0: float = Field(
        0.0, description="Initial alpha (shortest-window excess return)",
    )
    decay_rate: float = Field(
        0.0, description="Decay rate λ (higher = faster decay)",
    )
    half_life_days: float = Field(
        0.0, description="Half-life in trading days: ln(2)/λ",
    )
    optimal_holding_days: int = Field(
        0, description="Recommended holding period (window with peak Sharpe-like ratio)",
    )

    # Quality
    r_squared: float = Field(
        0.0, description="Fit quality of exp decay (0-1)",
    )
    is_decaying: bool = Field(
        False, description="True if alpha clearly decays over time",
    )


class AlphaDecayReport(BaseModel):
    """Full decay analysis across all signals."""
    signal_results: list[AlphaDecayResult] = Field(default_factory=list)
    total_signals: int = 0
    avg_half_life: float = 0.0
    fast_decay_count: int = 0
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Engine ───────────────────────────────────────────────────────────────────

DEFAULT_WINDOWS = [5, 10, 20, 40, 60]


class AlphaDecayEngine:
    """
    Analyzes signal alpha decay across multiple forward windows.

    Usage::

        engine = AlphaDecayEngine()
        report = engine.analyze(backtest_events)
        for r in report.signal_results:
            print(f"{r.signal_id}: half-life = {r.half_life_days:.0f} days")
    """

    def __init__(
        self,
        windows: list[int] | None = None,
        min_events: int = 20,
    ) -> None:
        self.windows = sorted(windows or DEFAULT_WINDOWS)
        self.min_events = min_events

    def analyze(
        self,
        events: list[SignalEvent],
        signal_meta: dict[str, str] | None = None,
    ) -> AlphaDecayReport:
        """Analyze alpha decay for all signals in the event set."""
        meta = signal_meta or {}

        # Group by signal_id
        by_signal: dict[str, list[SignalEvent]] = defaultdict(list)
        for e in events:
            by_signal[e.signal_id].append(e)

        results: list[AlphaDecayResult] = []

        for signal_id in sorted(by_signal.keys()):
            sig_events = by_signal[signal_id]
            result = self._analyze_signal(signal_id, sig_events, meta)
            if result:
                results.append(result)

        # Aggregate
        half_lives = [r.half_life_days for r in results if r.half_life_days > 0]
        avg_hl = sum(half_lives) / len(half_lives) if half_lives else 0.0
        fast_count = sum(1 for r in results if r.half_life_days > 0 and r.half_life_days < 10)

        return AlphaDecayReport(
            signal_results=results,
            total_signals=len(results),
            avg_half_life=round(avg_hl, 1),
            fast_decay_count=fast_count,
        )

    def _analyze_signal(
        self,
        signal_id: str,
        events: list[SignalEvent],
        meta: dict[str, str],
    ) -> AlphaDecayResult | None:
        """Analyze decay for a single signal."""
        if len(events) < self.min_events:
            return None

        # Compute avg excess return per window
        window_returns: dict[int, float] = {}
        window_counts: dict[int, int] = {}

        for w in self.windows:
            returns = [
                e.excess_returns.get(w, 0.0)
                for e in events
                if w in e.excess_returns
            ]
            if returns:
                window_returns[w] = sum(returns) / len(returns)
                window_counts[w] = len(returns)

        if not window_returns:
            return None

        # Find window with data
        valid_windows = [(w, window_returns[w]) for w in self.windows if w in window_returns]
        if len(valid_windows) < 2:
            # Can't fit decay with < 2 points
            first_w, first_r = valid_windows[0] if valid_windows else (0, 0.0)
            return AlphaDecayResult(
                signal_id=signal_id,
                signal_name=meta.get(signal_id, ""),
                n_events=len(events),
                window_returns={w: round(r, 6) for w, r in window_returns.items()},
                alpha_0=round(first_r, 6),
                optimal_holding_days=first_w,
            )

        # Fit exponential decay: α(t) = α₀ × e^(-λt)
        alpha_0, decay_rate, r_squared = self._fit_decay(valid_windows)

        # Half-life
        half_life = math.log(2) / decay_rate if decay_rate > 0 else 0.0

        # Optimal holding: window with highest return/sqrt(window) ratio
        # (risk-adjusted per unit time)
        optimal = self._find_optimal_holding(valid_windows)

        is_decaying = decay_rate > 0 and r_squared > 0.3

        return AlphaDecayResult(
            signal_id=signal_id,
            signal_name=meta.get(signal_id, ""),
            n_events=len(events),
            window_returns={w: round(r, 6) for w, r in window_returns.items()},
            alpha_0=round(alpha_0, 6),
            decay_rate=round(decay_rate, 6),
            half_life_days=round(half_life, 1),
            optimal_holding_days=optimal,
            r_squared=round(r_squared, 4),
            is_decaying=is_decaying,
        )

    @staticmethod
    def _fit_decay(
        window_returns: list[tuple[int, float]],
    ) -> tuple[float, float, float]:
        """
        Fit α(t) = α₀ × e^(-λt) using log-linear regression.

        ln(α) = ln(α₀) - λ × t

        Returns (alpha_0, lambda, r_squared).
        """
        # Filter to positive returns (can't log negative)
        positive = [(t, r) for t, r in window_returns if r > 0]

        if len(positive) < 2:
            # Can't fit — return first point as α₀
            alpha_0 = window_returns[0][1] if window_returns else 0.0
            return (alpha_0, 0.0, 0.0)

        # Log-linear regression: y = a + b*x
        # where y = ln(return), x = window_days
        xs = [float(t) for t, _ in positive]
        ys = [math.log(r) for _, r in positive]

        n = len(xs)
        sum_x = sum(xs)
        sum_y = sum(ys)
        sum_xy = sum(x * y for x, y in zip(xs, ys))
        sum_x2 = sum(x * x for x in xs)

        denom = n * sum_x2 - sum_x ** 2
        if abs(denom) < 1e-12:
            return (positive[0][1], 0.0, 0.0)

        b = (n * sum_xy - sum_x * sum_y) / denom  # slope = -λ
        a = (sum_y - b * sum_x) / n  # intercept = ln(α₀)

        alpha_0 = math.exp(a)
        decay_rate = -b  # λ = -slope

        # R² (coefficient of determination)
        mean_y = sum_y / n
        ss_tot = sum((y - mean_y) ** 2 for y in ys)
        ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        return (alpha_0, max(decay_rate, 0.0), max(r_squared, 0.0))

    @staticmethod
    def _find_optimal_holding(
        window_returns: list[tuple[int, float]],
    ) -> int:
        """
        Find optimal holding period.

        Uses return / sqrt(time) as a Sharpe-like efficiency metric.
        """
        if not window_returns:
            return 0

        best_window = 0
        best_efficiency = -math.inf

        for w, r in window_returns:
            efficiency = r / math.sqrt(w) if w > 0 else 0.0
            if efficiency > best_efficiency:
                best_efficiency = efficiency
                best_window = w

        return best_window
