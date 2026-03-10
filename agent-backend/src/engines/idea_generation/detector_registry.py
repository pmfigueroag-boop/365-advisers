"""
src/engines/idea_generation/detector_registry.py
──────────────────────────────────────────────────────────────────────────────
Detector Registry — central catalogue of all opportunity detectors.

The engine builds its active detector set from this registry instead of
maintaining a hardcoded list.  Detectors can be enabled/disabled by
configuration, executed as subsets, and listed for diagnostics.

Usage::

    from src.engines.idea_generation.detector_registry import (
        default_registry,
        build_active_detectors,
    )

    # All enabled detectors (default behaviour)
    detectors = build_active_detectors()

    # Only value + growth
    detectors = build_active_detectors(enabled_keys={"value", "growth"})

    # Everything except event
    detectors = build_active_detectors(disabled_keys={"event"})
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Type

from src.engines.idea_generation.detectors.base import BaseDetector
from src.engines.idea_generation.models import IdeaType

logger = logging.getLogger("365advisers.idea_generation.registry")


# ── DetectorSpec ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DetectorSpec:
    """Immutable descriptor for a registered detector.

    Attributes
    ----------
    key : str
        Stable slug used as the canonical identifier in metrics, logs,
        dedup keys, and configuration (e.g. ``"value"``, ``"growth"``).
    detector_class : Type[BaseDetector]
        Concrete detector class to instantiate.
    idea_type : IdeaType
        Primary idea type this detector produces.
    enabled : bool
        Whether the detector is active by default.
    priority : int
        Execution order hint (lower = earlier). Detectors with equal
        priority run in registration order.
    capabilities : frozenset[str]
        Optional feature flags (e.g. ``{"requires_context"}``).
    """
    key: str
    detector_class: Type[BaseDetector]
    idea_type: IdeaType
    enabled: bool = True
    priority: int = 100
    capabilities: frozenset[str] = field(default_factory=frozenset)


# ── DetectorRegistry ─────────────────────────────────────────────────────────

class DetectorRegistry:
    """Thread-safe registry of detector specifications.

    Prevents duplicate keys and provides query helpers for building
    the active detector set at scan time.
    """

    def __init__(self) -> None:
        self._specs: dict[str, DetectorSpec] = {}

    # ── Mutation ──────────────────────────────────────────────────────

    def register(self, spec: DetectorSpec) -> None:
        """Register a detector.  Raises ``ValueError`` on duplicate key."""
        if spec.key in self._specs:
            raise ValueError(
                f"Detector key '{spec.key}' is already registered"
            )
        self._specs[spec.key] = spec
        logger.debug(
            "detector_registered",
            extra={"key": spec.key, "idea_type": spec.idea_type.value},
        )

    # ── Queries ───────────────────────────────────────────────────────

    def list_all(self) -> list[DetectorSpec]:
        """All registered specs, sorted by priority then registration order."""
        return sorted(self._specs.values(), key=lambda s: s.priority)

    def get_by_key(self, key: str) -> DetectorSpec | None:
        return self._specs.get(key)

    def get_active(
        self,
        enabled_keys: set[str] | None = None,
        disabled_keys: set[str] | None = None,
    ) -> list[DetectorSpec]:
        """Return active specs after applying include/exclude filters.

        Parameters
        ----------
        enabled_keys
            If provided, *only* these keys are considered (whitelist).
        disabled_keys
            Keys to exclude even if enabled (blacklist).
        """
        specs = self.list_all()

        if enabled_keys is not None:
            specs = [s for s in specs if s.key in enabled_keys]
        else:
            specs = [s for s in specs if s.enabled]

        if disabled_keys:
            specs = [s for s in specs if s.key not in disabled_keys]

        return specs

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, key: str) -> bool:
        return key in self._specs


# ── Default registry ─────────────────────────────────────────────────────────

def _build_default_registry() -> DetectorRegistry:
    """Create the default registry with all built-in detectors."""
    from src.engines.idea_generation.detectors.value_detector import ValueDetector
    from src.engines.idea_generation.detectors.quality_detector import QualityDetector
    from src.engines.idea_generation.detectors.momentum_detector import MomentumDetector
    from src.engines.idea_generation.detectors.reversal_detector import ReversalDetector
    from src.engines.idea_generation.detectors.growth_detector import GrowthDetector
    from src.engines.idea_generation.detectors.event_detector import EventDetector

    reg = DetectorRegistry()

    reg.register(DetectorSpec(
        key="value", detector_class=ValueDetector,
        idea_type=IdeaType.VALUE, priority=10,
    ))
    reg.register(DetectorSpec(
        key="quality", detector_class=QualityDetector,
        idea_type=IdeaType.QUALITY, priority=20,
    ))
    reg.register(DetectorSpec(
        key="momentum", detector_class=MomentumDetector,
        idea_type=IdeaType.MOMENTUM, priority=30,
    ))
    reg.register(DetectorSpec(
        key="reversal", detector_class=ReversalDetector,
        idea_type=IdeaType.REVERSAL, priority=40,
    ))
    reg.register(DetectorSpec(
        key="growth", detector_class=GrowthDetector,
        idea_type=IdeaType.GROWTH, priority=50,
    ))
    reg.register(DetectorSpec(
        key="event", detector_class=EventDetector,
        idea_type=IdeaType.EVENT, priority=60,
        capabilities=frozenset({"requires_context"}),
    ))

    return reg


default_registry = _build_default_registry()


# ── Factory ───────────────────────────────────────────────────────────────────

def build_active_detectors(
    registry: DetectorRegistry | None = None,
    enabled_keys: set[str] | None = None,
    disabled_keys: set[str] | None = None,
) -> list[BaseDetector]:
    """Instantiate detectors from the registry.

    Parameters
    ----------
    registry
        Registry to use; defaults to ``default_registry``.
    enabled_keys
        Whitelist of detector keys.  ``None`` means "all enabled".
    disabled_keys
        Blacklist of keys to skip.

    Returns
    -------
    list[BaseDetector]
        Ready-to-use detector instances, ordered by priority.
    """
    reg = registry or default_registry
    specs = reg.get_active(enabled_keys=enabled_keys, disabled_keys=disabled_keys)
    return [spec.detector_class() for spec in specs]
