"""
src/features/filing_features.py
──────────────────────────────────────────────────────────────────────────────
Feature extractor for SEC filing events.

Transforms a FilingEventData contract into a flat dictionary of binary
flags and count features consumed by the Alpha Signals library and
the Idea Generation Engine.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from src.data.external.contracts.filing_event import FilingEventData

logger = logging.getLogger("365advisers.features.filing")


def extract_filing_features(
    data: FilingEventData | None,
) -> dict[str, float | bool | None]:
    """
    Extract filing-based features from SEC EDGAR data.

    Returns a dict with keys like `has_8k_7d`, `has_10k_30d`, etc.
    If data is None, all features are None (unknown).
    """
    if data is None or data.source == "null":
        return _empty_features()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Date thresholds
    _7d = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    _30d = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    _90d = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")

    # Binary flags
    has_8k_7d = any(
        f.filing_type == "8-K" and f.filed_date >= _7d
        for f in data.filings
    )
    has_10k_30d = any(
        f.filing_type == "10-K" and f.filed_date >= _30d
        for f in data.filings
    )
    has_10q_30d = any(
        f.filing_type == "10-Q" and f.filed_date >= _30d
        for f in data.filings
    )
    has_proxy_30d = any(
        f.filing_type.startswith("DEF") and f.filed_date >= _30d
        for f in data.filings
    )
    has_ownership_change = len(data.ownership_filings) > 0
    has_contested_proxy = any(
        p.contested for p in data.proxy_filings
    )

    # Count features
    filing_count_30d = sum(1 for f in data.filings if f.filed_date >= _30d)
    filing_count_90d = sum(1 for f in data.filings if f.filed_date >= _90d)
    material_event_count = sum(
        1 for f in data.filings
        if f.urgency in ("material", "critical")
    )

    # Critical items in recent 8-Ks
    critical_8k_items: list[str] = []
    for f in data.filings:
        if f.filing_type == "8-K" and f.filed_date >= _7d:
            critical_8k_items.extend(f.items)

    return {
        # Binary flags
        "has_8k_7d": has_8k_7d,
        "has_10k_30d": has_10k_30d,
        "has_10q_30d": has_10q_30d,
        "has_proxy_30d": has_proxy_30d,
        "has_ownership_change": has_ownership_change,
        "has_contested_proxy": has_contested_proxy,
        "has_material_event": data.has_material_event,

        # Counts
        "filing_count_30d": float(filing_count_30d),
        "filing_count_90d": float(filing_count_90d),
        "material_event_count": float(material_event_count),

        # Derived
        "filing_velocity": filing_count_30d / 30.0 if filing_count_30d else 0.0,
        "critical_8k_item_count": float(len(set(critical_8k_items))),
    }


def _empty_features() -> dict[str, float | bool | None]:
    """Return empty feature dict when filing data is unavailable."""
    return {
        "has_8k_7d": None,
        "has_10k_30d": None,
        "has_10q_30d": None,
        "has_proxy_30d": None,
        "has_ownership_change": None,
        "has_contested_proxy": None,
        "has_material_event": None,
        "filing_count_30d": None,
        "filing_count_90d": None,
        "material_event_count": None,
        "filing_velocity": None,
        "critical_8k_item_count": None,
    }
