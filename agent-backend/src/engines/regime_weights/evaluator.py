"""
src/engines/regime_weights/evaluator.py
──────────────────────────────────────────────────────────────────────────────
Per-regime performance evaluator.

Segments backtest events by market regime and computes Sharpe, hit rate,
and average alpha for each signal in each regime.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date

import numpy as np

from src.engines.backtesting.models import SignalEvent
from src.engines.backtesting.regime_detector import MarketRegime
from src.engines.regime_weights.models import RegimeSignalStats

logger = logging.getLogger("365advisers.regime_weights.evaluator")


class RegimePerformanceEvaluator:
    """Computes per-signal performance stats per regime."""

    def evaluate(
        self,
        events_by_signal: dict[str, list[SignalEvent]],
        regimes: dict[date, MarketRegime],
        forward_window: int = 20,
        min_events: int = 10,
    ) -> dict[str, dict[str, RegimeSignalStats]]:
        """
        Segment events by regime and compute stats.

        Parameters
        ----------
        events_by_signal : dict
            {signal_id: [SignalEvent, ...]}
        regimes : dict
            {date: MarketRegime} from RegimeDetector.classify()
        forward_window : int
            Forward return window to evaluate.
        min_events : int
            Minimum events for valid stats.

        Returns
        -------
        dict[str, dict[str, RegimeSignalStats]]
            {signal_id: {regime_value: RegimeSignalStats}}
        """
        result: dict[str, dict[str, RegimeSignalStats]] = {}

        for signal_id, events in events_by_signal.items():
            # Segment events by regime
            regime_events: dict[str, list[float]] = defaultdict(list)

            for event in events:
                regime = self._find_regime(event.fired_date, regimes)
                if regime is None:
                    continue

                ret = event.forward_returns.get(forward_window)
                if ret is not None:
                    regime_events[regime.value].append(ret)

            # Compute stats per regime
            signal_stats: dict[str, RegimeSignalStats] = {}
            for regime_val in [r.value for r in MarketRegime]:
                returns = regime_events.get(regime_val, [])
                stats = self._compute_stats(
                    signal_id, regime_val, returns, min_events,
                )
                signal_stats[regime_val] = stats

            result[signal_id] = signal_stats

        logger.info(
            "REGIME-EVAL: Evaluated %d signals across %d regimes",
            len(result), len(MarketRegime),
        )
        return result

    def _find_regime(
        self,
        fired_date: date,
        regimes: dict[date, MarketRegime],
    ) -> MarketRegime | None:
        """Find the regime for a given date, with ±3 day tolerance."""
        regime = regimes.get(fired_date)
        if regime is not None:
            return regime

        from datetime import timedelta
        for offset in range(1, 4):
            for delta in (offset, -offset):
                nearby = fired_date + timedelta(days=delta)
                regime = regimes.get(nearby)
                if regime is not None:
                    return regime
        return None

    @staticmethod
    def _compute_stats(
        signal_id: str,
        regime: str,
        returns: list[float],
        min_events: int,
    ) -> RegimeSignalStats:
        """Compute Sharpe, hit rate, alpha for a set of returns."""
        n = len(returns)
        if n < min_events:
            return RegimeSignalStats(
                signal_id=signal_id,
                regime=regime,
                events_count=n,
            )

        arr = np.array(returns)
        mean_ret = float(arr.mean())
        std_ret = float(arr.std(ddof=1)) if n > 1 else 1e-12

        sharpe = (mean_ret / std_ret * math.sqrt(12.6)) if std_ret > 1e-12 else 0.0
        hit_rate = float((arr > 0).sum()) / n

        return RegimeSignalStats(
            signal_id=signal_id,
            regime=regime,
            events_count=n,
            sharpe=round(sharpe, 4),
            hit_rate=round(hit_rate, 4),
            avg_alpha=round(mean_ret, 6),
            avg_return=round(mean_ret, 6),
            regime_multiplier=1.0,  # Will be set by engine
        )
