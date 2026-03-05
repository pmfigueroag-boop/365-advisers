"""
src/engines/alpha_signals/registry.py
──────────────────────────────────────────────────────────────────────────────
Singleton registry for alpha signal definitions.

Signals are auto-registered when their module is imported.  The registry
provides lookup, filtering, and enable/disable operations.
"""

from __future__ import annotations

import logging
from typing import Iterator

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    SignalCategory,
)

logger = logging.getLogger("365advisers.alpha_signals.registry")


class SignalRegistry:
    """
    Central catalog of alpha signal definitions.

    Usage::

        from src.engines.alpha_signals.registry import registry

        registry.register(my_signal)
        enabled = registry.get_enabled()
    """

    def __init__(self) -> None:
        self._signals: dict[str, AlphaSignalDefinition] = {}

    # ── Registration ──────────────────────────────────────────────────────

    def register(self, signal: AlphaSignalDefinition) -> None:
        """Register a signal definition.  Overwrites if id already exists."""
        self._signals[signal.id] = signal
        logger.debug(f"SIGNAL-REGISTRY: Registered '{signal.id}' ({signal.category.value})")

    def register_many(self, signals: list[AlphaSignalDefinition]) -> None:
        """Convenience: register a list of signals at once."""
        for s in signals:
            self.register(s)

    def unregister(self, signal_id: str) -> bool:
        """Remove a signal definition.  Returns True if it existed."""
        removed = self._signals.pop(signal_id, None)
        if removed:
            logger.debug(f"SIGNAL-REGISTRY: Unregistered '{signal_id}'")
        return removed is not None

    # ── Enable / Disable ──────────────────────────────────────────────────

    def enable(self, signal_id: str) -> None:
        if signal_id in self._signals:
            self._signals[signal_id].enabled = True

    def disable(self, signal_id: str) -> None:
        if signal_id in self._signals:
            self._signals[signal_id].enabled = False

    def set_enabled_bulk(self, signal_ids: list[str], enabled: bool) -> None:
        for sid in signal_ids:
            if sid in self._signals:
                self._signals[sid].enabled = enabled

    # ── Queries ───────────────────────────────────────────────────────────

    def get(self, signal_id: str) -> AlphaSignalDefinition | None:
        return self._signals.get(signal_id)

    def get_enabled(self) -> list[AlphaSignalDefinition]:
        return [s for s in self._signals.values() if s.enabled]

    def get_by_category(self, category: SignalCategory) -> list[AlphaSignalDefinition]:
        return [s for s in self._signals.values() if s.category == category]

    def get_enabled_by_category(self, category: SignalCategory) -> list[AlphaSignalDefinition]:
        return [
            s for s in self._signals.values()
            if s.category == category and s.enabled
        ]

    def get_all(self) -> list[AlphaSignalDefinition]:
        return list(self._signals.values())

    def categories(self) -> set[SignalCategory]:
        return {s.category for s in self._signals.values()}

    @property
    def size(self) -> int:
        return len(self._signals)

    def __len__(self) -> int:
        return len(self._signals)

    def __iter__(self) -> Iterator[AlphaSignalDefinition]:
        return iter(self._signals.values())

    def __contains__(self, signal_id: str) -> bool:
        return signal_id in self._signals

    # ── Introspection ─────────────────────────────────────────────────────

    def summary(self) -> dict[str, int]:
        """Return count of enabled signals per category."""
        counts: dict[str, int] = {}
        for s in self._signals.values():
            if s.enabled:
                key = s.category.value
                counts[key] = counts.get(key, 0) + 1
        return counts


# ── Module-level singleton ────────────────────────────────────────────────────

registry = SignalRegistry()
