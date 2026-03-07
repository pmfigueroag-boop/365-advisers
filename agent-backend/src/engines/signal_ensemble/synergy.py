"""
src/engines/signal_ensemble/synergy.py
──────────────────────────────────────────────────────────────────────────────
Synergy scorer — measures whether a combination predicts better than
individual signals.

Synergy(A, B) = Sharpe(co_fire_returns) − max(Sharpe(A), Sharpe(B))
"""

from __future__ import annotations

import logging
import math

import numpy as np

from src.engines.backtesting.models import SignalEvent
from src.engines.signal_ensemble.models import CoFireEvent, SignalCombination

logger = logging.getLogger("365advisers.signal_ensemble.synergy")


class SynergyScorer:
    """Scores signal combinations for synergistic predictive power."""

    def score(
        self,
        combo_signals: list[str],
        co_fires: list[CoFireEvent],
        events_by_signal: dict[str, list[SignalEvent]],
        forward_window: int = 20,
    ) -> SignalCombination:
        """
        Compute synergy metrics for a signal combination.

        Parameters
        ----------
        combo_signals : list[str]
            Signal IDs in the combination.
        co_fires : list[CoFireEvent]
            Co-fire events for this combination.
        events_by_signal : dict
            All signal events for individual Sharpe reference.
        forward_window : int
            Forward return window.

        Returns
        -------
        SignalCombination
        """
        # Joint returns from co-fire events
        joint_returns = [cf.joint_return for cf in co_fires]
        joint_sharpe = self._sharpe(joint_returns)
        joint_hr = self._hit_rate(joint_returns)

        # Individual Sharpe for each signal
        individual_sharpes = []
        individual_hrs = []
        for sig_id in combo_signals:
            rets = [
                e.forward_returns.get(forward_window, 0.0)
                for e in events_by_signal.get(sig_id, [])
                if e.forward_returns.get(forward_window) is not None
            ]
            individual_sharpes.append(self._sharpe(rets))
            individual_hrs.append(self._hit_rate(rets))

        max_ind_sharpe = max(individual_sharpes) if individual_sharpes else 0.0
        avg_ind_hr = sum(individual_hrs) / max(len(individual_hrs), 1)

        synergy = joint_sharpe - max_ind_sharpe
        incremental_power = joint_hr - avg_ind_hr

        return SignalCombination(
            signals=combo_signals,
            co_fire_count=len(co_fires),
            joint_sharpe=round(joint_sharpe, 4),
            max_individual_sharpe=round(max_ind_sharpe, 4),
            synergy_score=round(synergy, 4),
            joint_hit_rate=round(joint_hr, 4),
            avg_individual_hit_rate=round(avg_ind_hr, 4),
            incremental_power=round(incremental_power, 4),
        )

    @staticmethod
    def _sharpe(returns: list[float]) -> float:
        """Compute annualised Sharpe from a list of returns."""
        if len(returns) < 2:
            return 0.0
        arr = np.array(returns)
        mean = float(arr.mean())
        std = float(arr.std(ddof=1))
        if std < 1e-12:
            return 0.0
        return mean / std * math.sqrt(12.6)

    @staticmethod
    def _hit_rate(returns: list[float]) -> float:
        """Fraction of positive returns."""
        if not returns:
            return 0.0
        return sum(1 for r in returns if r > 0) / len(returns)
