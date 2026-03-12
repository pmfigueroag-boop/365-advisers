"""
src/engines/technical/math_utils.py
──────────────────────────────────────────────────────────────────────────────
Mathematical utilities for the institutional-grade scoring engine.

Provides sigmoid, clamp, and normalisation functions used by every scoring
module to produce continuous 0–10 scores from raw indicator values.
"""

from __future__ import annotations

import math


def sigmoid(x: float) -> float:
    """Standard sigmoid function, output in [0, 1]."""
    # Clamp input to avoid overflow in exp()
    x = max(-20.0, min(20.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def clamp(value: float, lo: float = 0.0, hi: float = 10.0) -> float:
    """Clamp a value to [lo, hi] and round to 2 decimals."""
    return round(max(lo, min(hi, value)), 2)


def normalize_to_score(value: float, center: float, scale: float) -> float:
    """
    Map a continuous value to [0, 10] using a sigmoid centred at `center`.

    - Values >> center → approaches 10
    - Values << center → approaches 0
    - value == center → 5.0

    Args:
        value:  raw indicator reading
        center: the "neutral" point (e.g., RSI=50, SMA distance=0)
        scale:  controls sensitivity — smaller scale = steeper transition

    Returns:
        Score in [0, 10].
    """
    return clamp(sigmoid((value - center) / max(scale, 0.001)) * 10)


def inverse_score(value: float, center: float, scale: float) -> float:
    """
    Like normalize_to_score but inverted: high values → low scores.
    Used for indicators where high = bearish (e.g., RSI overbought = bearish).
    """
    return clamp((1.0 - sigmoid((value - center) / max(scale, 0.001))) * 10)
