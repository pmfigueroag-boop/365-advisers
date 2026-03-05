"""
src/orchestration/sse_streamer.py
──────────────────────────────────────────────────────────────────────────────
SSE event formatting — extracted from main.py.

Provides compact helpers for building Server-Sent Events strings
and replaying cached event sequences.
"""

from __future__ import annotations

import json
import asyncio
import logging

logger = logging.getLogger("365advisers.orchestration.sse")


def sse(event: str, data: dict) -> str:
    """Format a single SSE event line."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def replay_cached_events(events: list[dict], delay: float = 0.02):
    """
    Async generator that replays a list of cached SSE events.

    Args:
        events: List of {"event": str, "data": dict} dicts.
        delay: Delay between events for smooth UI rendering.

    Yields:
        Formatted SSE strings.
    """
    for ev in events:
        yield sse(ev["event"], ev["data"])
        await asyncio.sleep(delay)


async def replay_fundamental_cache(cached_data: dict):
    """Replay a cached fundamental analysis as SSE events."""
    events = cached_data.get("events", [])
    async for line in replay_cached_events(events):
        yield line
    yield sse("done", {"from_cache": True})


async def replay_legacy_cache(ticker: str, entry: dict):
    """Replay a cached legacy analysis (data_ready + agents + dalio)."""
    data_ready = dict(entry["data_ready"])
    data_ready["from_cache"] = True
    data_ready["cached_at"] = entry.get("cached_at")

    yield sse("data_ready", data_ready)
    await asyncio.sleep(0)

    for agent in entry.get("agents", []):
        yield sse("agent_update", agent)
        await asyncio.sleep(0.05)

    yield sse("dalio_verdict", entry.get("dalio", {}))
    await asyncio.sleep(0)
    yield sse("done", {})
