"""
src/engines/alpha_signals/decay.py
──────────────────────────────────────────────────────────────────────────────
Evidence-Based Signal Decay Model.

Implements exponential decay per signal category to prevent stale signals
from maintaining full confidence.  Half-lives are calibrated to the
information horizon of each signal type:

  - Technical / flow / volatility  →  fast decay   (5 days)
  - Event                          →  medium decay  (10 days)
  - Value / quality / growth       →  slow decay    (30 days)
  - Macro                          →  very slow     (60 days)

Usage::

    from src.engines.alpha_signals.decay import apply_decay, HALF_LIFE_HOURS

    decayed_confidence = apply_decay(
        confidence=0.85,
        category="momentum",
        hours_since_signal=48.0,
    )
"""

from __future__ import annotations

import math
from src.engines.alpha_signals.models import SignalCategory


# ── Half-Life Table (hours) ──────────────────────────────────────────────────
# Derived from signal persistence analysis:
#   - Technical signals (momentum, flow, vol) decay within 1 week
#   - Event signals are repriced in ~2 weeks
#   - Fundamental signals (value, quality, growth) persist for ~1 month
#   - Macro signals persist for ~2 months

HALF_LIFE_HOURS: dict[str, float] = {
    SignalCategory.MOMENTUM.value:   120.0,   # 5 days
    SignalCategory.FLOW.value:       120.0,   # 5 days
    SignalCategory.VOLATILITY.value: 120.0,   # 5 days
    SignalCategory.EVENT.value:      240.0,   # 10 days
    SignalCategory.VALUE.value:      720.0,   # 30 days
    SignalCategory.QUALITY.value:    720.0,   # 30 days
    SignalCategory.GROWTH.value:     720.0,   # 30 days
    SignalCategory.MACRO.value:     1440.0,   # 60 days
}

# Minimum decay floor — never let confidence drop below 10% of original
DECAY_FLOOR = 0.10


def compute_decay_factor(
    category: str,
    hours_since_signal: float,
) -> float:
    """
    Compute the exponential decay factor for a signal.

    Parameters
    ----------
    category : str
        Signal category (e.g. "momentum", "value").
    hours_since_signal : float
        Hours elapsed since the signal was generated.

    Returns
    -------
    float
        Decay factor in [DECAY_FLOOR, 1.0].
        1.0 = fresh signal, DECAY_FLOOR = maximally decayed.
    """
    if hours_since_signal <= 0:
        return 1.0

    half_life = HALF_LIFE_HOURS.get(category, 240.0)  # default 10d

    # Exponential decay: factor = 0.5^(t / half_life)
    factor = math.pow(0.5, hours_since_signal / half_life)

    return max(DECAY_FLOOR, factor)


def apply_decay(
    confidence: float,
    category: str,
    hours_since_signal: float,
) -> float:
    """
    Apply exponential decay to a signal's confidence value.

    Parameters
    ----------
    confidence : float
        Original confidence value (0.0–1.0).
    category : str
        Signal category string.
    hours_since_signal : float
        Hours elapsed since the signal was generated.

    Returns
    -------
    float
        Decayed confidence value.
    """
    factor = compute_decay_factor(category, hours_since_signal)
    return round(confidence * factor, 4)
