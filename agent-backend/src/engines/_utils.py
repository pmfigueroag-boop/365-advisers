"""
src/engines/_utils.py
──────────────────────────────────────────────────────────────────────────────
Shared utility functions for all alpha engines.
"""

from __future__ import annotations

import math


def safe_float(val, default=None) -> float | None:
    """
    Convert a value to float, returning *default* on failure.

    Handles None, "DATA_INCOMPLETE", NaN, and non-numeric strings gracefully.
    """
    if val is None:
        return default
    if isinstance(val, str):
        if val.upper() in ("DATA_INCOMPLETE", "N/A", "NAN", ""):
            return default
        try:
            f = float(val)
        except (ValueError, TypeError):
            return default
    else:
        try:
            f = float(val)
        except (ValueError, TypeError):
            return default

    if math.isnan(f) or math.isinf(f):
        return default
    return f


def sigmoid(value: float, center: float = 0.0, scale: float = 1.0) -> float:
    """
    Map a raw value to a 0–10 score via logistic sigmoid.

    Parameters
    ----------
    value : float
        Raw input value.
    center : float
        Value that maps to exactly 5.0.
    scale : float
        Controls steepness.  Larger = steeper transition.
    """
    z = scale * (value - center)
    z = max(-20.0, min(20.0, z))  # clamp to avoid overflow
    return 10.0 / (1.0 + math.exp(-z))


def clamp(v, lo=0.0, hi=100.0) -> float:
    """Clamp a numeric value to [lo, hi], defaulting to midpoint on error."""
    try:
        return min(max(float(v), lo), hi)
    except (ValueError, TypeError):
        return (lo + hi) / 2.0
