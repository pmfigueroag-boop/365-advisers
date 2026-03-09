"""
src/engines/event_backtester/event_bus.py — Event queue with priority dispatch.
"""
from __future__ import annotations
import heapq
import logging
from typing import Callable
from src.engines.event_backtester.models import EventType

logger = logging.getLogger("365advisers.backtester.bus")

_PRIORITY = {EventType.MARKET: 0, EventType.SIGNAL: 1, EventType.ORDER: 2, EventType.FILL: 3}


class EventBus:
    """Priority-ordered event queue."""

    def __init__(self):
        self._queue: list[tuple[int, int, object]] = []
        self._handlers: dict[EventType, list[Callable]] = {}
        self._counter = 0

    def register(self, event_type: EventType, handler: Callable):
        self._handlers.setdefault(event_type, []).append(handler)

    def emit(self, event):
        priority = _PRIORITY.get(event.event_type, 5)
        heapq.heappush(self._queue, (priority, self._counter, event))
        self._counter += 1

    def process_next(self) -> bool:
        if not self._queue:
            return False
        _, _, event = heapq.heappop(self._queue)
        for handler in self._handlers.get(event.event_type, []):
            handler(event)
        return True

    def process_all(self) -> int:
        count = 0
        while self.process_next():
            count += 1
        return count

    @property
    def pending(self) -> int:
        return len(self._queue)

    def clear(self):
        self._queue.clear()
        self._counter = 0
