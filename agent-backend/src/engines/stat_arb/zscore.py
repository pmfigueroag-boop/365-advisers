"""
src/engines/stat_arb/zscore.py
──────────────────────────────────────────────────────────────────────────────
Z-score computation and signal generation for pairs trading.
"""

from __future__ import annotations

import numpy as np

from src.engines.stat_arb.models import ZScoreSignal


def compute_spread(
    prices_a: list[float] | np.ndarray,
    prices_b: list[float] | np.ndarray,
    hedge_ratio: float = 1.0,
) -> np.ndarray:
    """
    Compute the spread between two price series.

    spread_t = prices_a_t - hedge_ratio × prices_b_t
    """
    a = np.asarray(prices_a, dtype=np.float64)
    b = np.asarray(prices_b, dtype=np.float64)
    n = min(len(a), len(b))
    return a[:n] - hedge_ratio * b[:n]


def compute_zscore(
    spread: list[float] | np.ndarray,
    lookback: int = 60,
) -> np.ndarray:
    """
    Compute the rolling z-score of a spread series.

    z_t = (spread_t - mean_{lookback}) / std_{lookback}
    """
    s = np.asarray(spread, dtype=np.float64)
    n = len(s)
    z = np.full(n, 0.0)

    for i in range(lookback, n):
        window = s[i - lookback : i]
        mean = np.mean(window)
        std = np.std(window)
        if std > 1e-10:
            z[i] = (s[i] - mean) / std

    return z


def generate_signals(
    z_scores: list[float] | np.ndarray,
    entry_threshold: float = 2.0,
    exit_threshold: float = 0.5,
) -> list[ZScoreSignal]:
    """
    Generate trading signals from a z-score series.

    Rules:
        z < -entry  → LONG_A_SHORT_B  (spread is low, expect reversion up)
        z > +entry  → LONG_B_SHORT_A  (spread is high, expect reversion down)
        |z| < exit  → EXIT            (spread has reverted)
        otherwise   → NEUTRAL

    Args:
        z_scores: Z-score time series.
        entry_threshold: Absolute z-score to enter a trade (default ±2.0).
        exit_threshold: Absolute z-score to exit a trade (default ±0.5).

    Returns:
        List of ZScoreSignal values, one per data point.
    """
    z = np.asarray(z_scores, dtype=np.float64)
    signals: list[ZScoreSignal] = []

    in_position = False
    current_signal = ZScoreSignal.NEUTRAL

    for z_val in z:
        if not in_position:
            if z_val < -entry_threshold:
                current_signal = ZScoreSignal.LONG_A_SHORT_B
                in_position = True
            elif z_val > entry_threshold:
                current_signal = ZScoreSignal.LONG_B_SHORT_A
                in_position = True
            else:
                current_signal = ZScoreSignal.NEUTRAL
        else:
            # Check for exit
            if abs(z_val) < exit_threshold:
                current_signal = ZScoreSignal.EXIT
                in_position = False
            # Otherwise maintain current position signal
            # (already set from entry)

        signals.append(current_signal)

    return signals


def current_signal_from_zscore(
    z_score: float,
    entry_threshold: float = 2.0,
    exit_threshold: float = 0.5,
) -> ZScoreSignal:
    """
    Determine the current signal from a single z-score value.

    Simplified point-in-time evaluation (no position memory).
    """
    if z_score < -entry_threshold:
        return ZScoreSignal.LONG_A_SHORT_B
    elif z_score > entry_threshold:
        return ZScoreSignal.LONG_B_SHORT_A
    elif abs(z_score) < exit_threshold:
        return ZScoreSignal.EXIT
    return ZScoreSignal.NEUTRAL
