"""
src/engines/idea_generation/strategy_profiles.py
──────────────────────────────────────────────────────────────────────────────
Strategy Profile system for the IDEA module.

Converts the engine into a multi-strategy platform by defining
configurable profiles that control:
  - Which detectors run
  - How ideas are ranked (weight vector)
  - Minimum thresholds for quality gating
  - Preferred evaluation horizons
  - UI presentation hints

Usage::

    from src.engines.idea_generation.strategy_profiles import (
        default_profile_registry,
    )

    profile = default_profile_registry.get_by_key("swing")
    engine  = IdeaGenerationEngine(strategy_profile=profile)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("365advisers.idea_generation.strategy_profiles")


# ── Ranking Weights ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RankingWeights:
    """Configurable weight vector for the composite ranking formula.

    priority_score = (signal_strength × detector_weight × w_signal)
                   + (alpha_score × w_alpha)
                   + (confidence_score × w_confidence)
                   + multi_detector_bonus

    All weights should sum to ~1.0 for consistency, but it's not mandatory.
    """
    w_signal: float = 0.40
    w_alpha: float = 0.35
    w_confidence: float = 0.25
    multi_detector_bonus: float = 0.10

    def to_dict(self) -> dict:
        return {
            "w_signal": self.w_signal,
            "w_alpha": self.w_alpha,
            "w_confidence": self.w_confidence,
            "multi_detector_bonus": self.multi_detector_bonus,
        }


# ── Default institutional weights (backward-compatible) ─────────────────────

DEFAULT_WEIGHTS = RankingWeights()


# ── Strategy Profile ────────────────────────────────────────────────────────


@dataclass
class StrategyProfile:
    """A named configuration for the IDEA engine.

    Attributes
    ----------
    key : str
        Stable slug used in API calls, logs, and persistence.
    display_name : str
        Human-readable label for UI.
    description : str
        Brief explanation of the strategy's philosophy.
    enabled_detectors : frozenset[str]
        Whitelist of detector keys to run.  Empty means "use defaults".
    disabled_detectors : frozenset[str]
        Blacklist of detector keys to exclude (applied after whitelist).
    ranking_weights : RankingWeights
        Custom weight vector for ranking.
    minimum_confidence : float
        Ideas below this confidence_score are filtered out (0.0 = no filter).
    minimum_signal_strength : float
        Ideas below this signal_strength are filtered out (0.0 = no filter).
    preferred_horizons : tuple[str, ...]
        Suggested evaluation horizons for backtesting (e.g. ("5D", "20D")).
    sort_default : str
        Default sort column in UI: "priority" | "signal_strength" | "confidence".
    ui_hints : dict
        Presentation hints for the frontend (colors, icons, badges).
    active : bool
        Whether this profile is available for selection.
    """
    key: str
    display_name: str
    description: str = ""
    enabled_detectors: frozenset[str] = field(default_factory=frozenset)
    disabled_detectors: frozenset[str] = field(default_factory=frozenset)
    ranking_weights: RankingWeights = field(default_factory=lambda: DEFAULT_WEIGHTS)
    minimum_confidence: float = 0.0
    minimum_signal_strength: float = 0.0
    preferred_horizons: tuple[str, ...] = ("5D", "20D", "60D")
    sort_default: str = "priority"
    ui_hints: dict = field(default_factory=dict)
    active: bool = True

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dict for API responses."""
        return {
            "key": self.key,
            "display_name": self.display_name,
            "description": self.description,
            "enabled_detectors": sorted(self.enabled_detectors),
            "disabled_detectors": sorted(self.disabled_detectors),
            "ranking_weights": self.ranking_weights.to_dict(),
            "minimum_confidence": self.minimum_confidence,
            "minimum_signal_strength": self.minimum_signal_strength,
            "preferred_horizons": list(self.preferred_horizons),
            "sort_default": self.sort_default,
            "ui_hints": self.ui_hints,
            "active": self.active,
        }


# ── Strategy Profile Registry ───────────────────────────────────────────────


class StrategyProfileRegistry:
    """Central catalog of strategy profiles.

    Analogous to DetectorRegistry — provides validation,
    listing, and lookup for available profiles.
    """

    def __init__(self) -> None:
        self._profiles: dict[str, StrategyProfile] = {}

    def register(self, profile: StrategyProfile) -> None:
        """Register a profile.  Raises ValueError on duplicate key."""
        if profile.key in self._profiles:
            raise ValueError(
                f"Strategy profile key '{profile.key}' is already registered"
            )
        self._profiles[profile.key] = profile
        logger.debug(
            "strategy_profile_registered",
            extra={"key": profile.key, "display_name": profile.display_name},
        )

    def get_by_key(self, key: str) -> StrategyProfile | None:
        """Look up a profile by key.  Returns None if not found."""
        return self._profiles.get(key)

    def get_or_raise(self, key: str) -> StrategyProfile:
        """Look up a profile by key.  Raises ValueError if not found."""
        profile = self._profiles.get(key)
        if profile is None:
            available = ", ".join(sorted(self._profiles.keys()))
            raise ValueError(
                f"Unknown strategy profile '{key}'. "
                f"Available profiles: {available}"
            )
        return profile

    def list_active(self) -> list[StrategyProfile]:
        """Return all active profiles, sorted by key."""
        return sorted(
            [p for p in self._profiles.values() if p.active],
            key=lambda p: p.key,
        )

    def list_all(self) -> list[StrategyProfile]:
        """Return all profiles including inactive, sorted by key."""
        return sorted(self._profiles.values(), key=lambda p: p.key)

    def __len__(self) -> int:
        return len(self._profiles)

    def __contains__(self, key: str) -> bool:
        return key in self._profiles


# ── Built-in Profiles ───────────────────────────────────────────────────────


def _build_default_registry() -> StrategyProfileRegistry:
    """Create the registry with all 5 built-in strategy profiles."""
    reg = StrategyProfileRegistry()

    # ── 1. Buy & Hold ────────────────────────────────────────────────────
    reg.register(StrategyProfile(
        key="buy_and_hold",
        display_name="Buy & Hold",
        description=(
            "Long-term investor profile focused on fundamental quality. "
            "Prioritizes value, quality, and growth detectors with emphasis "
            "on confidence over momentum signals. Best for horizons of 20D+."
        ),
        enabled_detectors=frozenset({"value", "quality", "growth"}),
        ranking_weights=RankingWeights(
            w_signal=0.25,
            w_alpha=0.40,
            w_confidence=0.35,
            multi_detector_bonus=0.15,
        ),
        minimum_confidence=0.3,
        minimum_signal_strength=0.0,
        preferred_horizons=("20D", "60D"),
        sort_default="priority",
        ui_hints={
            "icon": "trending_up",
            "color": "#2196F3",
            "badge": "Long-Term",
        },
    ))

    # ── 2. Swing ─────────────────────────────────────────────────────────
    reg.register(StrategyProfile(
        key="swing",
        display_name="Swing Trading",
        description=(
            "Short-to-medium term profile focused on timing and momentum. "
            "Prioritizes momentum, reversal, and event detectors with high "
            "signal strength weighting for quick entries. Horizons 1D–20D."
        ),
        enabled_detectors=frozenset({"momentum", "reversal", "event"}),
        ranking_weights=RankingWeights(
            w_signal=0.55,
            w_alpha=0.25,
            w_confidence=0.20,
            multi_detector_bonus=0.05,
        ),
        minimum_confidence=0.0,
        minimum_signal_strength=0.4,
        preferred_horizons=("1D", "5D", "20D"),
        sort_default="signal_strength",
        ui_hints={
            "icon": "swap_horiz",
            "color": "#FF9800",
            "badge": "Short-Term",
        },
    ))

    # ── 3. Deep Value ────────────────────────────────────────────────────
    reg.register(StrategyProfile(
        key="deep_value",
        display_name="Deep Value",
        description=(
            "Contrarian value-focused profile that demands high conviction. "
            "Value detector dominant, quality as secondary confirmation. "
            "Requires high confidence — filters out noisy or weak setups."
        ),
        enabled_detectors=frozenset({"value", "quality"}),
        ranking_weights=RankingWeights(
            w_signal=0.30,
            w_alpha=0.45,
            w_confidence=0.25,
            multi_detector_bonus=0.20,
        ),
        minimum_confidence=0.5,
        minimum_signal_strength=0.0,
        preferred_horizons=("20D", "60D"),
        sort_default="priority",
        ui_hints={
            "icon": "savings",
            "color": "#4CAF50",
            "badge": "High-Conviction",
        },
    ))

    # ── 4. Growth / Quality ──────────────────────────────────────────────
    reg.register(StrategyProfile(
        key="growth_quality",
        display_name="Growth + Quality",
        description=(
            "Growth-oriented profile that penalizes weak or noisy setups. "
            "Combines growth and quality detectors with a moderate confidence "
            "floor. Filters ideas where signal quality is insufficient."
        ),
        enabled_detectors=frozenset({"growth", "quality", "momentum"}),
        ranking_weights=RankingWeights(
            w_signal=0.35,
            w_alpha=0.35,
            w_confidence=0.30,
            multi_detector_bonus=0.10,
        ),
        minimum_confidence=0.35,
        minimum_signal_strength=0.3,
        preferred_horizons=("5D", "20D", "60D"),
        sort_default="priority",
        ui_hints={
            "icon": "rocket_launch",
            "color": "#9C27B0",
            "badge": "Growth",
        },
    ))

    # ── 5. Event-Driven ──────────────────────────────────────────────────
    reg.register(StrategyProfile(
        key="event_driven",
        display_name="Event-Driven",
        description=(
            "Catalyst-focused profile targeting event, momentum, and reversal "
            "signals. Expects rapid alpha decay — optimized for short holding "
            "periods. High signal weight, lower alpha emphasis."
        ),
        enabled_detectors=frozenset({"event", "momentum", "reversal"}),
        ranking_weights=RankingWeights(
            w_signal=0.50,
            w_alpha=0.20,
            w_confidence=0.30,
            multi_detector_bonus=0.05,
        ),
        minimum_confidence=0.0,
        minimum_signal_strength=0.3,
        preferred_horizons=("1D", "5D"),
        sort_default="signal_strength",
        ui_hints={
            "icon": "bolt",
            "color": "#F44336",
            "badge": "Catalyst",
        },
    ))

    return reg


# ── Module-level singleton ───────────────────────────────────────────────────

default_profile_registry = _build_default_registry()
