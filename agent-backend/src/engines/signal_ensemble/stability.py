"""
src/engines/signal_ensemble/stability.py
──────────────────────────────────────────────────────────────────────────────
Rolling stability analysis for signal combinations.

Evaluates whether synergy is consistent across time or an artifact of
specific market conditions.

Stability = fraction of rolling windows where synergy > 0
"""

from __future__ import annotations

import logging
import math
from datetime import date

import numpy as np

from src.engines.signal_ensemble.models import CoFireEvent

logger = logging.getLogger("365advisers.signal_ensemble.stability")


class StabilityAnalyzer:
    """Evaluates temporal consistency of signal ensemble synergy."""

    def __init__(
        self,
        window_months: int = 6,
        stride_months: int = 1,
    ) -> None:
        self._window = window_months
        self._stride = stride_months

    def evaluate(
        self,
        co_fires: list[CoFireEvent],
        max_individual_sharpe: float = 0.0,
    ) -> tuple[float, int, int]:
        """
        Compute stability via rolling window analysis.

        Parameters
        ----------
        co_fires : list[CoFireEvent]
            Co-fire events sorted by date.
        max_individual_sharpe : float
            Best individual signal Sharpe for synergy reference.

        Returns
        -------
        (stability, stable_windows, total_windows)
        """
        if len(co_fires) < 5:
            return 0.0, 0, 0

        # Parse dates and sort
        dated_returns: list[tuple[date, float]] = []
        for cf in co_fires:
            d = date.fromisoformat(cf.date)
            dated_returns.append((d, cf.joint_return))

        dated_returns.sort(key=lambda x: x[0])

        min_date = dated_returns[0][0]
        max_date = dated_returns[-1][0]

        # Generate rolling windows
        windows = self._generate_windows(min_date, max_date)

        if not windows:
            return 0.0, 0, 0

        stable = 0
        total = 0

        for w_start, w_end in windows:
            window_rets = [
                r for d, r in dated_returns
                if w_start <= d <= w_end
            ]
            if len(window_rets) < 3:
                continue

            total += 1
            window_sharpe = self._sharpe(window_rets)
            synergy = window_sharpe - max_individual_sharpe

            if synergy > 0:
                stable += 1

        stability = stable / total if total > 0 else 0.0

        logger.debug(
            "STABILITY: %d/%d windows positive synergy (%.1f%%)",
            stable, total, stability * 100,
        )
        return round(stability, 4), stable, total

    def _generate_windows(
        self,
        min_date: date,
        max_date: date,
    ) -> list[tuple[date, date]]:
        """Generate rolling windows with stride."""
        windows = []
        current = min_date

        while True:
            end = date(
                current.year + (current.month + self._window - 1) // 12,
                (current.month + self._window - 1) % 12 + 1,
                min(current.day, 28),
            )
            if end > max_date:
                break

            windows.append((current, end))

            # Advance by stride months
            new_month = current.month + self._stride
            current = date(
                current.year + (new_month - 1) // 12,
                (new_month - 1) % 12 + 1,
                min(current.day, 28),
            )

        return windows

    @staticmethod
    def _sharpe(returns: list[float]) -> float:
        """Compute Sharpe ratio."""
        if len(returns) < 2:
            return 0.0
        arr = np.array(returns)
        mean = float(arr.mean())
        std = float(arr.std(ddof=1))
        if std < 1e-12:
            return 0.0
        return mean / std * math.sqrt(12.6)
