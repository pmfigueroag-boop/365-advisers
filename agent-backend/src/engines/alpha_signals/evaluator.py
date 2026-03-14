"""
src/engines/alpha_signals/evaluator.py
──────────────────────────────────────────────────────────────────────────────
Evaluates all registered (enabled) alpha signals against a pair of
normalised feature sets and produces a SignalProfile for a single asset.

The evaluator is stateless — it reads definitions from the registry and
resolves each signal's feature_path against the provided features.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.contracts.features import FundamentalFeatureSet, TechnicalFeatureSet
from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    EvaluatedSignal,
    SignalCategory,
    SignalDirection,
    SignalStrength,
    ConfidenceLevel,
    CategoryScore,
    SignalProfile,
)
from src.engines.alpha_signals.registry import registry

logger = logging.getLogger("365advisers.alpha_signals.evaluator")

# Strength numeric mapping for composite calculations
_STRENGTH_NUMERIC = {
    SignalStrength.STRONG: 1.0,
    SignalStrength.MODERATE: 0.6,
    SignalStrength.WEAK: 0.3,
}


class SignalEvaluator:
    """
    Evaluates all enabled signals from the registry against feature sets.

    Usage::

        evaluator = SignalEvaluator()
        profile = evaluator.evaluate("MSFT", fundamental_fs, technical_fs)
    """

    def evaluate(
        self,
        ticker: str,
        fundamental: FundamentalFeatureSet | None = None,
        technical: TechnicalFeatureSet | None = None,
    ) -> SignalProfile:
        """
        Evaluate all enabled signals for a single asset.

        Parameters
        ----------
        ticker : str
            Asset symbol.
        fundamental : FundamentalFeatureSet | None
            Normalised fundamental features (may be None).
        technical : TechnicalFeatureSet | None
            Normalised technical features (may be None).

        Returns
        -------
        SignalProfile
            Complete evaluated signal profile.
        """
        enabled_signals = registry.get_enabled()
        evaluated: list[EvaluatedSignal] = []

        for signal_def in enabled_signals:
            result = self._evaluate_single(signal_def, fundamental, technical)
            if result is not None:
                evaluated.append(result)

        # Build category summaries
        fired_signals = [s for s in evaluated if s.fired]
        category_summary = self._build_category_summary(evaluated)

        return SignalProfile(
            ticker=ticker.upper(),
            evaluated_at=datetime.now(timezone.utc),
            total_signals=len(evaluated),
            fired_signals=len(fired_signals),
            signals=evaluated,
            category_summary=category_summary,
        )

    # ── Private helpers ───────────────────────────────────────────────────

    def _evaluate_single(
        self,
        signal_def: AlphaSignalDefinition,
        fundamental: FundamentalFeatureSet | None,
        technical: TechnicalFeatureSet | None,
    ) -> EvaluatedSignal | None:
        """Evaluate a single signal definition against feature sets."""
        value = self._resolve_feature(signal_def.feature_path, fundamental, technical)
        if value is None:
            return EvaluatedSignal(
                signal_id=signal_def.id,
                signal_name=signal_def.name,
                category=signal_def.category,
                fired=False,
                value=None,
                threshold=signal_def.threshold,
                strength=SignalStrength.WEAK,
                confidence=0.0,
                description=f"{signal_def.name}: data unavailable",
            )

        # C4: Sector-relative threshold adjustment for valuation signals
        adjusted_def = signal_def
        if (
            fundamental is not None
            and signal_def.category == SignalCategory.VALUE
            and fundamental.sector_pe_adjustment != 1.0
            and any(kw in signal_def.feature_path for kw in ("pe_ratio", "ev_ebitda", "pb_ratio", "ev_revenue"))
        ):
            factor = fundamental.sector_pe_adjustment
            from copy import copy
            adjusted_def = copy(signal_def)
            adjusted_def.threshold = signal_def.threshold * factor
            if signal_def.strong_threshold is not None:
                adjusted_def.strong_threshold = signal_def.strong_threshold * factor

        fired = self._check_fired(adjusted_def, value)
        strength = self._compute_strength(signal_def, value) if fired else SignalStrength.WEAK
        confidence = self._compute_confidence(signal_def, value) if fired else 0.0
        description = self._build_description(signal_def, value, fired)

        return EvaluatedSignal(
            signal_id=signal_def.id,
            signal_name=signal_def.name,
            category=signal_def.category,
            fired=fired,
            value=round(value, 6),
            threshold=signal_def.threshold,
            strength=strength,
            confidence=round(confidence, 3),
            description=description,
        )

    @staticmethod
    def _resolve_feature(
        feature_path: str,
        fundamental: FundamentalFeatureSet | None,
        technical: TechnicalFeatureSet | None,
    ) -> float | None:
        """
        Resolve a dot-path like 'fundamental.fcf_yield' or
        'technical.rsi' to an actual float value.
        """
        parts = feature_path.split(".", 1)
        if len(parts) != 2:
            logger.warning(f"SIGNAL-EVAL: Invalid feature_path '{feature_path}'")
            return None

        source, attr = parts

        if source == "fundamental" and fundamental is not None:
            val = getattr(fundamental, attr, None)
        elif source == "technical" and technical is not None:
            val = getattr(technical, attr, None)
        else:
            return None

        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _check_fired(signal_def: AlphaSignalDefinition, value: float) -> bool:
        """Check if the signal condition is met."""
        if signal_def.direction == SignalDirection.ABOVE:
            return value > signal_def.threshold
        elif signal_def.direction == SignalDirection.BELOW:
            return value < signal_def.threshold
        elif signal_def.direction == SignalDirection.BETWEEN:
            upper = signal_def.upper_threshold if signal_def.upper_threshold is not None else signal_def.threshold
            lower = min(signal_def.threshold, upper)
            upper = max(signal_def.threshold, upper)
            return lower <= value <= upper
        return False

    @staticmethod
    def _compute_strength(signal_def: AlphaSignalDefinition, value: float) -> SignalStrength:
        """
        Classify signal strength based on how far value exceeds threshold.
        """
        threshold = signal_def.threshold
        if threshold == 0:
            return SignalStrength.MODERATE

        strong_threshold = signal_def.strong_threshold

        if signal_def.direction == SignalDirection.ABOVE:
            if strong_threshold is not None and value >= strong_threshold:
                return SignalStrength.STRONG
            # Fallback: 1.5x threshold = strong
            if value >= threshold * 1.5:
                return SignalStrength.STRONG
            return SignalStrength.MODERATE

        elif signal_def.direction == SignalDirection.BELOW:
            if strong_threshold is not None and value <= strong_threshold:
                return SignalStrength.STRONG
            # For BELOW: further below = stronger
            if threshold != 0 and value <= threshold * 0.6:
                return SignalStrength.STRONG
            return SignalStrength.MODERATE

        return SignalStrength.MODERATE

    @staticmethod
    def _compute_confidence(signal_def: AlphaSignalDefinition, value: float) -> float:
        """
        Compute confidence as a 0.0–1.0 measure of how decisively
        the signal fired.

        Uses a sigmoid rather than linear ratio to avoid:
        - Requiring 2×threshold for max confidence (ABOVE)
        - Diverging to infinity for small values (BELOW)
        """
        import math

        threshold = signal_def.threshold
        strong = signal_def.strong_threshold

        if signal_def.direction == SignalDirection.ABOVE:
            if threshold == 0:
                return 0.5
            if strong is None:
                strong = threshold * 1.5 if threshold > 0 else threshold * 0.5
            span = abs(strong - threshold) or 1.0
            ratio = (value - threshold) / span
            # Sigmoid: maps 0→~0.3, 0.5→~0.5, 1.0→~0.7, 2.0→~0.9
            return min(1.0 / (1.0 + math.exp(-2.0 * ratio)), 1.0)

        elif signal_def.direction == SignalDirection.BELOW:
            if threshold == 0:
                return 0.5
            if strong is None:
                strong = threshold * 0.6 if threshold > 0 else threshold * 1.5
            span = abs(threshold - strong) or 1.0
            ratio = (threshold - value) / span
            return min(1.0 / (1.0 + math.exp(-2.0 * ratio)), 1.0)

        return 0.5

    @staticmethod
    def _build_description(
        signal_def: AlphaSignalDefinition,
        value: float,
        fired: bool,
    ) -> str:
        """Build a human-readable description of the evaluation."""
        op = ">" if signal_def.direction == SignalDirection.ABOVE else "<"
        status = "✓" if fired else "✗"

        # Format value smartly
        if abs(value) < 1.0:
            val_str = f"{value:.1%}"
            thr_str = f"{signal_def.threshold:.0%}"
        elif abs(value) < 100:
            val_str = f"{value:.2f}"
            thr_str = f"{signal_def.threshold:.1f}"
        else:
            val_str = f"{value:,.0f}"
            thr_str = f"{signal_def.threshold:,.0f}"

        return f"{status} {signal_def.name}: {val_str} {op} {thr_str}"

    def _build_category_summary(
        self, signals: list[EvaluatedSignal]
    ) -> dict[str, CategoryScore]:
        """Aggregate evaluated signals into per-category scores."""
        categories: dict[str, list[EvaluatedSignal]] = {}
        for sig in signals:
            key = sig.category.value
            categories.setdefault(key, []).append(sig)

        summary: dict[str, CategoryScore] = {}
        for cat_key, cat_signals in categories.items():
            fired = [s for s in cat_signals if s.fired]
            total = len(cat_signals)
            fired_count = len(fired)

            # Composite strength: weighted average of fired signals
            if fired:
                composite = sum(
                    _STRENGTH_NUMERIC.get(s.strength, 0.3) for s in fired
                ) / total  # divided by total, not fired count, to penalize gaps
            else:
                composite = 0.0

            # Confidence from ratio
            if total == 0:
                confidence = ConfidenceLevel.LOW
            else:
                ratio = fired_count / total
                if ratio >= 0.6:
                    confidence = ConfidenceLevel.HIGH
                elif ratio >= 0.4:
                    confidence = ConfidenceLevel.MEDIUM
                else:
                    confidence = ConfidenceLevel.LOW

            # Dominant strength
            if fired:
                strength_counts = {
                    SignalStrength.STRONG: 0,
                    SignalStrength.MODERATE: 0,
                    SignalStrength.WEAK: 0,
                }
                for s in fired:
                    strength_counts[s.strength] = strength_counts.get(s.strength, 0) + 1
                dominant = max(strength_counts, key=lambda k: strength_counts[k])
            else:
                dominant = SignalStrength.WEAK

            summary[cat_key] = CategoryScore(
                category=SignalCategory(cat_key),
                fired=fired_count,
                total=total,
                composite_strength=round(min(composite, 1.0), 3),
                confidence=confidence,
                dominant_strength=dominant,
            )

        return summary
