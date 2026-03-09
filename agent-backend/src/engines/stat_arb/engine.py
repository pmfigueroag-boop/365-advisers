"""
src/engines/stat_arb/engine.py
──────────────────────────────────────────────────────────────────────────────
Statistical Arbitrage Strategy Engine.

Evaluates individual pairs, generates trade signals, and constructs
long/short legs for integration with the LongShortEngine.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from src.engines.stat_arb.models import (
    PairCandidate,
    ZScoreSignal,
)
from src.engines.stat_arb.cointegration import engle_granger_test
from src.engines.stat_arb.zscore import (
    compute_spread,
    compute_zscore,
    current_signal_from_zscore,
)

logger = logging.getLogger("365advisers.stat_arb.engine")


class StatArbEngine:
    """
    Orchestrates stat-arb evaluation and trade construction.

    Typical flow:
        1. evaluate_pair(prices_a, prices_b) → PairCandidate with signal
        2. construct_trade(pair, capital)     → long/short leg dicts
        3. Feed legs into LongShortEngine     → hedged portfolio
    """

    DEFAULT_LOOKBACK = 60
    DEFAULT_ENTRY_THRESHOLD = 2.0
    DEFAULT_EXIT_THRESHOLD = 0.5

    @classmethod
    def evaluate_pair(
        cls,
        ticker_a: str,
        ticker_b: str,
        prices_a: list[float],
        prices_b: list[float],
        *,
        lookback: int = DEFAULT_LOOKBACK,
        entry_threshold: float = DEFAULT_ENTRY_THRESHOLD,
        exit_threshold: float = DEFAULT_EXIT_THRESHOLD,
    ) -> PairCandidate:
        """
        Evaluate a specific pair: cointegration + current z-score + signal.

        Returns a PairCandidate with all diagnostic fields populated.
        """
        # Run cointegration
        coint = engle_granger_test(prices_a, prices_b)
        coint.ticker_a = ticker_a
        coint.ticker_b = ticker_b

        a = np.asarray(prices_a, dtype=np.float64)
        b = np.asarray(prices_b, dtype=np.float64)
        n = min(len(a), len(b))
        a, b = a[:n], b[:n]

        # Correlation
        corr = float(np.corrcoef(a, b)[0, 1]) if n > 2 else 0.0

        # Spread and z-score
        spread = compute_spread(a, b, hedge_ratio=coint.hedge_ratio)
        z_scores = compute_zscore(spread, lookback=min(lookback, n // 2))
        current_z = float(z_scores[-1]) if len(z_scores) > 0 else 0.0
        signal = current_signal_from_zscore(current_z, entry_threshold, exit_threshold)

        return PairCandidate(
            ticker_a=ticker_a,
            ticker_b=ticker_b,
            correlation=round(corr, 4),
            cointegration=coint,
            half_life=coint.half_life,
            current_z_score=round(current_z, 4),
            current_signal=signal,
            spread_mean=round(float(np.mean(spread)), 4),
            spread_std=round(float(np.std(spread)), 4),
        )

    @classmethod
    def construct_trade(
        cls,
        pair: PairCandidate,
        capital: float = 100000.0,
        position_weight: float = 0.05,
    ) -> dict[str, Any]:
        """
        Construct trade legs from a pair with an active signal.

        Returns a dict with:
            signal: the current signal
            long_leg: {ticker, weight, side}
            short_leg: {ticker, weight, side}
            notional_per_leg: capital × position_weight

        Returns empty legs if signal is NEUTRAL or EXIT.
        """
        signal = pair.current_signal

        if signal in (ZScoreSignal.NEUTRAL, ZScoreSignal.EXIT):
            return {
                "signal": signal.value,
                "long_leg": None,
                "short_leg": None,
                "notional_per_leg": 0,
                "reason": "No active entry signal.",
            }

        notional = capital * position_weight

        if signal == ZScoreSignal.LONG_A_SHORT_B:
            long_ticker = pair.ticker_a
            short_ticker = pair.ticker_b
        else:  # LONG_B_SHORT_A
            long_ticker = pair.ticker_b
            short_ticker = pair.ticker_a

        hedge_ratio = pair.cointegration.hedge_ratio if pair.cointegration else 1.0

        return {
            "signal": signal.value,
            "long_leg": {
                "ticker": long_ticker,
                "weight": position_weight,
                "side": "long",
                "notional": round(notional, 2),
            },
            "short_leg": {
                "ticker": short_ticker,
                "weight": round(position_weight * abs(hedge_ratio), 4),
                "side": "short",
                "notional": round(notional * abs(hedge_ratio), 2),
            },
            "hedge_ratio": round(hedge_ratio, 4),
            "z_score": pair.current_z_score,
            "half_life": pair.half_life,
            "notional_per_leg": round(notional, 2),
        }
