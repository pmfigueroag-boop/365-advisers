"""
src/engines/idea_generation/detectors/base.py
──────────────────────────────────────────────────────────────────────────────
Abstract base class for all opportunity detectors.

Each detector receives normalised feature sets and returns a DetectorResult
if it identifies an actionable opportunity — or None if no signal fires.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.contracts.features import FundamentalFeatureSet, TechnicalFeatureSet
from src.engines.idea_generation.models import (
    DetectorResult,
    ConfidenceLevel,
    SignalStrength,
)


class BaseDetector(ABC):
    """Interface contract for opportunity detectors."""

    name: str = "base"
    weight: float = 1.0

    @abstractmethod
    def scan(
        self,
        fundamental: FundamentalFeatureSet | None,
        technical: TechnicalFeatureSet | None,
    ) -> DetectorResult | None:
        """
        Analyse normalised features and return a DetectorResult
        if an opportunity is detected, or None otherwise.
        """

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
