"""
src/features/credit_spread_features.py
──────────────────────────────────────────────────────────────────────────────
Bonus 7.1: Credit Spread Change feature extractor.

Fetches HY credit spread from FRED and computes 30-day change (bps).
Series: BAMLH0A0HYM2 (BofA US High Yield OAS)

This is a macro-level feature shared across all tickers.
Cached for 1 hour to avoid excessive API calls.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from src.config import get_settings

logger = logging.getLogger("365advisers.features.credit_spread")

# Use module-level cache to avoid repeated FRED calls within the same session
_CACHE: dict[str, tuple[float, float]] = {}  # key -> (value, timestamp)
_CACHE_TTL = 3600  # 1 hour


async def fetch_credit_spread_change() -> float | None:
    """
    Fetch HY credit spread from FRED API and compute 30-day change in bps.

    Returns positive value if spread widened (risk-off), negative if tightened.
    Returns None if FRED API is unavailable.
    """
    cache_key = "credit_spread_change"
    now = time.time()

    # Check cache
    if cache_key in _CACHE:
        cached_val, cached_at = _CACHE[cache_key]
        if now - cached_at < _CACHE_TTL:
            return cached_val

    settings = get_settings()
    fred_key = getattr(settings, "FRED_API_KEY", None)
    if not fred_key:
        logger.debug("FRED_API_KEY not configured — credit spread unavailable")
        return None

    series_id = "BAMLH0A0HYM2"  # BofA US HY OAS
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")

    url = (
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}"
        f"&api_key={fred_key}"
        f"&file_type=json"
        f"&observation_start={start_date}"
        f"&observation_end={end_date}"
        f"&sort_order=desc"
        f"&limit=50"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning(f"FRED returned HTTP {resp.status_code}")
                return None

            data = resp.json()
            observations = data.get("observations", [])

            # Filter valid numeric observations
            values = []
            for obs in observations:
                try:
                    val = float(obs["value"])
                    values.append(val)
                except (ValueError, KeyError):
                    continue

            if len(values) < 2:
                logger.debug("FRED: Not enough data points for credit spread change")
                return None

            # Latest value vs value ~30 days ago
            latest = values[0]
            lookback_idx = min(len(values) - 1, 20)  # ~20 trading days ≈ 1 month
            prior = values[lookback_idx]

            change_bps = round((latest - prior) * 100, 1)  # OAS is in %, convert to bps

            # Cache result
            _CACHE[cache_key] = (change_bps, now)

            logger.info(
                f"FRED HY OAS: current={latest:.2f}%, "
                f"prior={prior:.2f}%, "
                f"change={change_bps:+.1f} bps"
            )
            return change_bps

    except Exception as exc:
        logger.warning(f"FRED credit spread fetch failed: {exc}")
        return None


def fetch_credit_spread_change_sync() -> float | None:
    """Synchronous wrapper for use in non-async contexts."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're inside an async context already, return None
            # (the async version should be used instead)
            return None
        return loop.run_until_complete(fetch_credit_spread_change())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(fetch_credit_spread_change())
        finally:
            loop.close()
