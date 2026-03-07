"""
src/engines/signal_selection/incremental.py
──────────────────────────────────────────────────────────────────────────────
Leave-one-out incremental alpha measurement.

For each signal s:
  Incremental_α(s) = Sharpe(all) − Sharpe(all \ {s})

Positive = signal adds value; ≤ 0 = signal is dispensable.
"""

from __future__ import annotations

import logging
import math

import numpy as np

from src.engines.backtesting.models import SignalEvent

logger = logging.getLogger("365advisers.signal_selection.incremental")


class IncrementalAlphaAnalyzer:
    """Measures leave-one-out incremental alpha for each signal."""

    def compute(
        self,
        events_by_signal: dict[str, list[SignalEvent]],
        forward_window: int = 20,
    ) -> dict[str, float]:
        """
        Compute incremental alpha (Sharpe contribution) per signal.

        Parameters
        ----------
        events_by_signal : dict
            {signal_id: [SignalEvent, ...]}
        forward_window : int
            Forward return window to use.

        Returns
        -------
        dict[str, float]
            {signal_id: incremental_sharpe}
        """
        # Collect all returns and per-signal returns
        all_returns: list[float] = []
        signal_returns: dict[str, list[float]] = {}

        for sig_id, events in events_by_signal.items():
            rets = []
            for e in events:
                r = e.forward_returns.get(forward_window)
                if r is not None:
                    rets.append(r)
                    all_returns.append(r)
            signal_returns[sig_id] = rets

        if not all_returns:
            return {s: 0.0 for s in events_by_signal}

        full_sharpe = self._sharpe(all_returns)

        result: dict[str, float] = {}
        for sig_id, rets in signal_returns.items():
            if not rets:
                result[sig_id] = 0.0
                continue

            # Remove this signal's returns
            rets_set = set(id(r) for r in rets)
            # Rebuild without via index exclusion
            remaining = [
                r for i, r in enumerate(all_returns)
                if i not in self._signal_indices(events_by_signal, sig_id, all_returns, forward_window)
            ]

            if not remaining:
                result[sig_id] = full_sharpe
                continue

            leave_out_sharpe = self._sharpe(remaining)
            result[sig_id] = round(full_sharpe - leave_out_sharpe, 6)

        return result

    def _signal_indices(
        self,
        events_by_signal: dict[str, list[SignalEvent]],
        target_id: str,
        all_returns: list[float],
        forward_window: int,
    ) -> set[int]:
        """Find indices of target signal's returns in the flat list."""
        idx = 0
        target_indices = set()
        for sig_id in events_by_signal:
            for e in events_by_signal[sig_id]:
                r = e.forward_returns.get(forward_window)
                if r is not None:
                    if sig_id == target_id:
                        target_indices.add(idx)
                    idx += 1
        return target_indices

    @staticmethod
    def _sharpe(returns: list[float]) -> float:
        """Compute Sharpe ratio from a list of returns."""
        if len(returns) < 2:
            return 0.0

        arr = np.array(returns)
        mean = float(arr.mean())
        std = float(arr.std(ddof=1))

        if std < 1e-12:
            return 0.0

        # Annualize (assuming ~252/20 ≈ 12.6 periods per year for 20-day returns)
        return round(mean / std * math.sqrt(12.6), 6)
