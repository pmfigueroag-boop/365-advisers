"""
src/engines/signal_selection/correlation.py
──────────────────────────────────────────────────────────────────────────────
Pairwise Pearson correlation analysis for signal forward returns.

Matches co-occurring events (same ticker, within a date tolerance window)
to build a correlation matrix across all signal pairs.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from itertools import combinations

import numpy as np

from src.engines.backtesting.models import SignalEvent

logger = logging.getLogger("365advisers.signal_selection.correlation")


class CorrelationAnalyzer:
    """Computes pairwise Pearson correlation between signals."""

    def __init__(self, date_tolerance: int = 2) -> None:
        """
        Parameters
        ----------
        date_tolerance : int
            Maximum day difference for considering events as co-occurring.
        """
        self._date_tol = date_tolerance

    def compute_matrix(
        self,
        events_by_signal: dict[str, list[SignalEvent]],
        forward_window: int = 20,
        min_overlap: int = 10,
    ) -> dict[str, dict[str, float]]:
        """
        Build pairwise Pearson correlation matrix.

        Parameters
        ----------
        events_by_signal : dict
            {signal_id: [SignalEvent, ...]}
        forward_window : int
            Which forward return window to use.
        min_overlap : int
            Minimum co-occurring events for a valid correlation.

        Returns
        -------
        dict[str, dict[str, float]]
            Nested dict: corr_matrix[sig_a][sig_b] = ρ
        """
        signal_ids = sorted(events_by_signal.keys())
        matrix: dict[str, dict[str, float]] = {
            s: {s2: 0.0 for s2 in signal_ids} for s in signal_ids
        }

        # Set diagonal to 1.0
        for s in signal_ids:
            matrix[s][s] = 1.0

        # Build ticker→date index for each signal
        indexes = {}
        for sig_id, events in events_by_signal.items():
            idx: dict[str, list[tuple]] = defaultdict(list)
            for e in events:
                ret = e.forward_returns.get(forward_window)
                if ret is not None:
                    idx[e.ticker].append((e.fired_date, ret))
            indexes[sig_id] = idx

        # Compute pairwise
        for sig_a, sig_b in combinations(signal_ids, 2):
            pairs = self._match_events(
                indexes[sig_a], indexes[sig_b],
            )
            if len(pairs) < min_overlap:
                continue

            rets_a = [p[0] for p in pairs]
            rets_b = [p[1] for p in pairs]
            rho = self._pearson(rets_a, rets_b)

            matrix[sig_a][sig_b] = round(rho, 6)
            matrix[sig_b][sig_a] = round(rho, 6)

        logger.info(
            "CORR: Computed %d×%d correlation matrix",
            len(signal_ids), len(signal_ids),
        )
        return matrix

    def _match_events(
        self,
        idx_a: dict[str, list[tuple]],
        idx_b: dict[str, list[tuple]],
    ) -> list[tuple[float, float]]:
        """Match co-occurring events by ticker and date proximity."""
        pairs = []
        common_tickers = set(idx_a.keys()) & set(idx_b.keys())

        for ticker in common_tickers:
            events_a = sorted(idx_a[ticker], key=lambda x: x[0])
            events_b = sorted(idx_b[ticker], key=lambda x: x[0])

            # Build a date→return lookup for B
            b_lookup: dict[str, float] = {}
            for date_b, ret_b in events_b:
                b_lookup[str(date_b)] = ret_b

            for date_a, ret_a in events_a:
                # Exact match first
                key = str(date_a)
                if key in b_lookup:
                    pairs.append((ret_a, b_lookup[key]))
                    continue

                # Try within tolerance
                best_ret = None
                best_diff = self._date_tol + 1
                for date_b, ret_b in events_b:
                    diff = abs(self._day_diff(date_a, date_b))
                    if diff <= self._date_tol and diff < best_diff:
                        best_diff = diff
                        best_ret = ret_b

                if best_ret is not None:
                    pairs.append((ret_a, best_ret))

        return pairs

    @staticmethod
    def _day_diff(d1, d2) -> int:
        """Day difference between two date-like objects."""
        from datetime import date
        if isinstance(d1, date) and isinstance(d2, date):
            return (d1 - d2).days
        # Fallback: convert via str
        return 0

    @staticmethod
    def _pearson(x: list[float], y: list[float]) -> float:
        """Compute Pearson correlation coefficient."""
        n = len(x)
        if n < 2:
            return 0.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        var_x = sum((xi - mean_x) ** 2 for xi in x)
        var_y = sum((yi - mean_y) ** 2 for yi in y)

        denom = math.sqrt(var_x * var_y)
        if denom < 1e-12:
            return 0.0

        return cov / denom
