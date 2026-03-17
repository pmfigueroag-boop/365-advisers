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

    # ── Calibration mutations ─────────────────────────────────────────────

    def update_weight(self, signal_id: str, new_weight: float) -> bool:
        """Update a signal's weight. Returns True if signal existed."""
        sig = self._signals.get(signal_id)
        if sig is None:
            return False
        sig.weight = max(0.0, new_weight)
        logger.debug(f"SIGNAL-REGISTRY: Updated weight for '{signal_id}' to {sig.weight:.3f}")
        return True

    def update_threshold(self, signal_id: str, new_threshold: float) -> bool:
        """Update a signal's threshold. Returns True if signal existed."""
        sig = self._signals.get(signal_id)
        if sig is None:
            return False
        sig.threshold = new_threshold
        return True

    def snapshot(self) -> dict[str, dict]:
        """Export current state for versioning."""
        return {
            sid: {
                "weight": sig.weight,
                "threshold": sig.threshold,
                "strong_threshold": sig.strong_threshold,
                "enabled": sig.enabled,
            }
            for sid, sig in self._signals.items()
        }

    def restore(self, snapshot: dict[str, dict]) -> int:
        """Restore from a snapshot. Returns count of signals updated."""
        updated = 0
        for sid, params in snapshot.items():
            sig = self._signals.get(sid)
            if sig is None:
                continue
            if "weight" in params:
                sig.weight = params["weight"]
            if "threshold" in params:
                sig.threshold = params["threshold"]
            if "strong_threshold" in params:
                sig.strong_threshold = params["strong_threshold"]
            if "enabled" in params:
                sig.enabled = params["enabled"]
            updated += 1
        logger.info(f"SIGNAL-REGISTRY: Restored {updated} signals from snapshot")
        return updated

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
