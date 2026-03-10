"""
src/engines/idea_generation/detectors/base.py
──────────────────────────────────────────────────────────────────────────────
Abstract base class for all opportunity detectors.

Each detector receives normalised feature sets (or a pre-evaluated
SignalProfile from the Alpha Signals Library) and returns a DetectorResult
if it identifies an actionable opportunity — or None if no signal fires.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from src.contracts.features import FundamentalFeatureSet, TechnicalFeatureSet
from src.engines.alpha_signals.models import SignalProfile, SignalCategory
from src.engines.idea_generation.models import (
    DetectorResult,
    ConfidenceLevel,
    SignalDetail,
    SignalStrength,
    IdeaType,
)

logger = logging.getLogger("365advisers.idea_generation.detectors.base")


# ── Scan Context — optional metadata passed uniformly to all detectors ────────

@dataclass
class ScanContext:
    """Optional contextual data for detectors that need external state.

    All fields are optional so detectors that don't need context
    can simply ignore it, preserving the uniform scan() interface.
    """
    previous_score: float | None = None
    current_score: float | None = None
    extra: dict = field(default_factory=dict)

    # ── Serialization for Celery transport ────────────────────────────
    def to_dict(self) -> dict:
        """Convert to a JSON-safe dict for Celery task args."""
        return {
            "previous_score": self.previous_score,
            "current_score": self.current_score,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "ScanContext":
        """Reconstruct from a serialized dict. Returns defaults if *data* is None."""
        if not data:
            return cls()
        return cls(
            previous_score=data.get("previous_score"),
            current_score=data.get("current_score"),
            extra=data.get("extra", {}),
        )


# Map alpha signal categories to IGE idea types.
# MACRO maps to EVENT because macro catalysts are event-driven by nature.
_CATEGORY_TO_IDEA_TYPE: dict[SignalCategory, IdeaType] = {
    SignalCategory.VALUE: IdeaType.VALUE,
    SignalCategory.QUALITY: IdeaType.QUALITY,
    SignalCategory.GROWTH: IdeaType.GROWTH,
    SignalCategory.MOMENTUM: IdeaType.MOMENTUM,
    SignalCategory.VOLATILITY: IdeaType.REVERSAL,
    SignalCategory.FLOW: IdeaType.MOMENTUM,
    SignalCategory.EVENT: IdeaType.EVENT,
    SignalCategory.MACRO: IdeaType.EVENT,
}


class BaseDetector(ABC):
    """Interface contract for opportunity detectors."""

    name: str = "base"
    weight: float = 1.0

    # The signal category this detector corresponds to
    signal_category: SignalCategory | None = None

    @abstractmethod
    def scan(
        self,
        fundamental: FundamentalFeatureSet | None,
        technical: TechnicalFeatureSet | None,
        context: ScanContext | None = None,
    ) -> DetectorResult | None:
        """
        Analyse normalised features and return a DetectorResult
        if an opportunity is detected, or None otherwise.

        Parameters
        ----------
        context : ScanContext | None
            Optional metadata such as previous scores for event detection.
            Detectors that don't need it simply ignore this parameter.
        """

    def scan_from_profile(self, profile: SignalProfile) -> DetectorResult | None:
        """
        Build a DetectorResult from a pre-evaluated SignalProfile.

        This method uses the Alpha Signals Library output instead of
        computing signals internally.  Detectors can override this for
        custom logic, but the default implementation filters signals
        by the detector's signal_category and aggregates them.
        """
        if self.signal_category is None:
            return None

        cat_key = self.signal_category.value
        cat_score = profile.category_summary.get(cat_key)
        if cat_score is None or cat_score.fired == 0:
            return None

        # Collect fired signals for this category
        cat_signals = [
            s for s in profile.signals
            if s.category == self.signal_category and s.fired
        ]
        if not cat_signals:
            return None

        # Convert EvaluatedSignals → SignalDetails
        signal_details = [
            SignalDetail(
                name=s.signal_id,
                description=s.description,
                value=s.value if s.value is not None else 0.0,
                threshold=s.threshold,
                strength=SignalStrength(s.strength.value),
            )
            for s in cat_signals
        ]

        # Map confidence level
        confidence = ConfidenceLevel(cat_score.confidence.value)

        idea_type = _CATEGORY_TO_IDEA_TYPE.get(self.signal_category)
        if idea_type is None:
            logger.warning(
                "DETECTOR: No IdeaType mapping for category %s — skipping",
                self.signal_category.value,
            )
            return None

        return DetectorResult(
            idea_type=idea_type,
            confidence=confidence,
            signal_strength=round(cat_score.composite_strength, 2),
            signals=signal_details,
            metadata={
                "signals_fired": cat_score.fired,
                "total_possible": cat_score.total,
                "source": "alpha_signals_library",
            },
        )

    # ── Shared helpers ────────────────────────────────────────────────────

    @staticmethod
    def _confidence_from_ratio(fired: int, total: int) -> ConfidenceLevel:
        """Map signal activation ratio to confidence level."""
        if total == 0:
            return ConfidenceLevel.LOW
        ratio = fired / total
        if ratio >= 0.6:
            return ConfidenceLevel.HIGH
        if ratio >= 0.4:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    @staticmethod
    def _strength_from_value(
        value: float,
        threshold: float,
        strong_mult: float = 1.5,
    ) -> SignalStrength:
        """
        Classify a signal as STRONG / MODERATE / WEAK based on how far
        the observed value exceeds the activation threshold.
        """
        if threshold == 0:
            return SignalStrength.MODERATE
        ratio = abs(value) / abs(threshold)
        if ratio >= strong_mult:
            return SignalStrength.STRONG
        if ratio >= 1.0:
            return SignalStrength.MODERATE
        return SignalStrength.WEAK
