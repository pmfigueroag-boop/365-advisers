"""
src/engines/backtesting/walk_forward_validator.py
--------------------------------------------------------------------------
Walk-Forward Stability Test (WFST) — Out-of-Sample Validation.

Splits historical signal events into K rolling windows, then measures
each signal's performance on the test portion of each window.
The result is a per-signal OOS degradation ratio that quantifies
how much performance drops when going from in-sample to out-of-sample.

Method
~~~~~~
1. Sort all events by fired_date
2. Split into K windows (e.g., 4 quarterly blocks)
3. For each window:
   - Train = first train_pct% of events
   - Test  = remaining events
   - Compute Sharpe@20d on train and test separately
4. Per signal:
   - OOS degradation = 1 - mean(Sharpe_test) / mean(Sharpe_train)
   - Window stability = std(Sharpe_test) across windows
5. Signals with high degradation (> 0.5) are likely overfitted.

Integration
~~~~~~~~~~~
Produces ``oos_degradation`` and ``wf_stability`` fields that can be
attached to ``ParameterChange`` for governor gating.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date, datetime, timezone

from pydantic import BaseModel, Field

from src.engines.backtesting.models import SignalEvent

logger = logging.getLogger("365advisers.backtesting.walk_forward")


# ── Contracts ────────────────────────────────────────────────────────────────

class WindowResult(BaseModel):
    """Performance for a single signal in a single walk-forward window."""
    window_index: int
    train_sharpe: float = 0.0
    test_sharpe: float = 0.0
    train_events: int = 0
    test_events: int = 0
    degradation: float = Field(
        0.0,
        description="1 - (test_sharpe / train_sharpe). "
        "0.0 = no degradation, 1.0 = complete degradation, <0 = OOS improvement.",
    )


class SignalWFResult(BaseModel):
    """Walk-forward stability result for a single signal."""
    signal_id: str
    signal_name: str = ""
    total_events: int = 0
    windows: list[WindowResult] = Field(default_factory=list)

    # Aggregate metrics
    avg_train_sharpe: float = 0.0
    avg_test_sharpe: float = 0.0
    oos_degradation: float = Field(
        0.0,
        description="1 - (avg_test_sharpe / avg_train_sharpe). "
        "High (>0.5) = likely overfitted.",
    )
    wf_stability: float = Field(
        0.0,
        description="StdDev of test Sharpe across windows. "
        "Lower = more stable OOS performance.",
    )
    is_overfit: bool = Field(
        False,
        description="True if oos_degradation > overfit_threshold",
    )


class WalkForwardReport(BaseModel):
    """Full walk-forward validation output."""
    signal_results: list[SignalWFResult] = Field(default_factory=list)
    n_windows: int = 0
    train_pct: float = 0.0
    total_signals: int = 0
    overfit_count: int = Field(
        0, ge=0, description="Signals with oos_degradation > threshold",
    )
    stable_count: int = Field(
        0, ge=0, description="Signals with acceptable OOS performance",
    )
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Engine ───────────────────────────────────────────────────────────────────

_REF_WINDOW = 20
_OVERFIT_THRESHOLD = 0.50  # > 50% degradation = likely overfitted
_MIN_EVENTS_PER_SPLIT = 5  # Min events in train/test to compute Sharpe


class WalkForwardValidator:
    """
    Walk-Forward Stability Test engine.

    Usage::

        validator = WalkForwardValidator(n_windows=4, train_pct=0.7)
        report = validator.validate(events, signal_meta)
    """

    def __init__(
        self,
        n_windows: int = 4,
        train_pct: float = 0.70,
        overfit_threshold: float = _OVERFIT_THRESHOLD,
    ) -> None:
        """
        Parameters
        ----------
        n_windows : int
            Number of rolling windows to split history into.
        train_pct : float
            Fraction of each window used for training (0.0-1.0).
        overfit_threshold : float
            OOS degradation above this → signal flagged as overfitted.
        """
        if n_windows < 2:
            raise ValueError("n_windows must be >= 2")
        if not (0.3 <= train_pct <= 0.9):
            raise ValueError("train_pct must be between 0.3 and 0.9")

        self.n_windows = n_windows
        self.train_pct = train_pct
        self.overfit_threshold = overfit_threshold

    def validate(
        self,
        events: list[SignalEvent],
        signal_meta: dict[str, str] | None = None,
    ) -> WalkForwardReport:
        """
        Run walk-forward validation on backtest events.

        Parameters
        ----------
        events : list[SignalEvent]
            All signal events from a completed backtest.
        signal_meta : dict[str, str] | None
            Optional signal_id → signal_name mapping.

        Returns
        -------
        WalkForwardReport
        """
        if not events:
            return WalkForwardReport(
                n_windows=self.n_windows,
                train_pct=self.train_pct,
            )

        signal_meta = signal_meta or {}

        # Sort by date
        sorted_events = sorted(events, key=lambda e: e.fired_date)

        # Split into K windows
        windows = self._split_windows(sorted_events)

        # Group events by signal
        by_signal: dict[str, list[SignalEvent]] = defaultdict(list)
        for e in sorted_events:
            by_signal[e.signal_id].append(e)

        signal_ids = sorted(by_signal.keys())
        results: list[SignalWFResult] = []

        for sig_id in signal_ids:
            sig_events = by_signal[sig_id]
            window_results: list[WindowResult] = []

            for w_idx, (win_start, win_end) in enumerate(windows):
                # Filter events in this window
                win_events = [
                    e for e in sig_events
                    if win_start <= e.fired_date <= win_end
                ]
                if len(win_events) < _MIN_EVENTS_PER_SPLIT * 2:
                    continue

                # Split into train/test
                split_idx = int(len(win_events) * self.train_pct)
                train = win_events[:split_idx]
                test = win_events[split_idx:]

                if len(train) < _MIN_EVENTS_PER_SPLIT or len(test) < _MIN_EVENTS_PER_SPLIT:
                    continue

                train_sharpe = self._sharpe(train)
                test_sharpe = self._sharpe(test)

                # Degradation: 1 - (test/train)
                if abs(train_sharpe) > 1e-6:
                    degradation = 1.0 - (test_sharpe / train_sharpe)
                else:
                    degradation = 0.0  # Can't measure degradation from zero

                window_results.append(WindowResult(
                    window_index=w_idx,
                    train_sharpe=round(train_sharpe, 4),
                    test_sharpe=round(test_sharpe, 4),
                    train_events=len(train),
                    test_events=len(test),
                    degradation=round(degradation, 4),
                ))

            # Aggregate across windows
            if window_results:
                avg_train = sum(w.train_sharpe for w in window_results) / len(window_results)
                avg_test = sum(w.test_sharpe for w in window_results) / len(window_results)

                if abs(avg_train) > 1e-6:
                    oos_deg = 1.0 - (avg_test / avg_train)
                else:
                    oos_deg = 0.0

                test_sharpes = [w.test_sharpe for w in window_results]
                wf_stab = self._std(test_sharpes)
            else:
                avg_train = 0.0
                avg_test = 0.0
                oos_deg = 0.0
                wf_stab = 0.0

            results.append(SignalWFResult(
                signal_id=sig_id,
                signal_name=signal_meta.get(sig_id, sig_id),
                total_events=len(sig_events),
                windows=window_results,
                avg_train_sharpe=round(avg_train, 4),
                avg_test_sharpe=round(avg_test, 4),
                oos_degradation=round(oos_deg, 4),
                wf_stability=round(wf_stab, 4),
                is_overfit=oos_deg > self.overfit_threshold,
            ))

        overfit_count = sum(1 for r in results if r.is_overfit)

        report = WalkForwardReport(
            signal_results=results,
            n_windows=self.n_windows,
            train_pct=self.train_pct,
            total_signals=len(results),
            overfit_count=overfit_count,
            stable_count=len(results) - overfit_count,
        )

        logger.info(
            "WALK-FORWARD: %d signals validated — %d stable, %d overfit "
            "(%d windows, %.0f%% train)",
            report.total_signals, report.stable_count, report.overfit_count,
            self.n_windows, self.train_pct * 100,
        )

        return report

    # ── Internal ─────────────────────────────────────────────────────────

    def _split_windows(
        self,
        sorted_events: list[SignalEvent],
    ) -> list[tuple[date, date]]:
        """Split event date range into K non-overlapping windows."""
        if not sorted_events:
            return []

        min_date = sorted_events[0].fired_date
        max_date = sorted_events[-1].fired_date
        total_days = (max_date - min_date).days

        if total_days < self.n_windows * 30:
            # Not enough history — use 2 windows minimum
            mid = min_date.toordinal() + total_days // 2
            return [
                (min_date, date.fromordinal(mid)),
                (date.fromordinal(mid + 1), max_date),
            ]

        window_days = total_days // self.n_windows
        windows: list[tuple[date, date]] = []

        for i in range(self.n_windows):
            start = date.fromordinal(min_date.toordinal() + i * window_days)
            if i == self.n_windows - 1:
                end = max_date  # Last window captures remainder
            else:
                end = date.fromordinal(min_date.toordinal() + (i + 1) * window_days - 1)
            windows.append((start, end))

        return windows

    @staticmethod
    def _sharpe(events: list[SignalEvent]) -> float:
        """Compute Sharpe@REF_WINDOW from excess returns."""
        returns = [
            e.excess_returns.get(_REF_WINDOW, 0.0)
            for e in events
            if _REF_WINDOW in e.excess_returns
        ]
        if len(returns) < _MIN_EVENTS_PER_SPLIT:
            return 0.0
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / len(returns)
        std = math.sqrt(var) if var > 0 else 1e-9
        return mean / std

    @staticmethod
    def _std(values: list[float]) -> float:
        """Standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / len(values)
        return math.sqrt(var) if var > 0 else 0.0
