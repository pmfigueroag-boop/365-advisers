"""
src/features/geopolitical_features.py
──────────────────────────────────────────────────────────────────────────────
Feature extractor for GDELT geopolitical event data.

Transforms a GeopoliticalEventData contract into a flat dictionary
of numeric features consumed by the Alpha Signals library, Regime
Weights Engine, and Idea Generation Engine.
"""

from __future__ import annotations

import logging

from src.data.external.contracts.geopolitical import GeopoliticalEventData

logger = logging.getLogger("365advisers.features.geopolitical")


def extract_geopolitical_features(
    data: GeopoliticalEventData | None,
) -> dict[str, float | bool | None]:
    """
    Extract geopolitical features from GDELT data.

    Returns a dict with keys like `geo_risk_index`, `geo_tone_momentum`, etc.
    If data is None, all features are None (unknown).
    """
    if data is None or data.source == "null":
        return _empty_features()

    # High-risk country count
    high_risk_countries = sum(
        1 for c in data.top_country_risks
        if c.risk_level in ("high", "critical")
    )

    # Dominant theme analysis
    worst_theme = None
    worst_tone = 0.0
    for t in data.top_themes:
        if t.tone < worst_tone:
            worst_tone = t.tone
            worst_theme = t.theme

    # Rising themes count
    rising_themes = sum(1 for t in data.top_themes if t.trend == "rising")

    return {
        # Core metrics
        "geo_risk_index": data.risk_index,
        "geo_tone_24h": data.tone_avg_24h,
        "geo_tone_7d": data.tone_avg_7d,
        "geo_tone_momentum": data.tone_momentum,
        "geo_event_count_24h": float(data.event_count_24h),
        "geo_event_count_7d": float(data.event_count_7d),

        # Spike detection
        "geo_spike_detected": data.spike_detected,

        # Country risk
        "geo_high_risk_country_count": float(high_risk_countries),

        # Theme analysis
        "geo_worst_theme_tone": worst_tone if worst_theme else None,
        "geo_rising_theme_count": float(rising_themes),

        # Derived
        "geo_risk_elevated": (
            data.risk_index is not None and data.risk_index > 60
        ),
        "geo_risk_critical": (
            data.risk_index is not None and data.risk_index > 80
        ),
    }


def _empty_features() -> dict[str, float | bool | None]:
    """Return empty feature dict when geopolitical data is unavailable."""
    return {
        "geo_risk_index": None,
        "geo_tone_24h": None,
        "geo_tone_7d": None,
        "geo_tone_momentum": None,
        "geo_event_count_24h": None,
        "geo_event_count_7d": None,
        "geo_spike_detected": None,
        "geo_high_risk_country_count": None,
        "geo_worst_theme_tone": None,
        "geo_rising_theme_count": None,
        "geo_risk_elevated": None,
        "geo_risk_critical": None,
    }
