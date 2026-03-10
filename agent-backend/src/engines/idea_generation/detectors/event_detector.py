"""
src/engines/idea_generation/detectors/event_detector.py
──────────────────────────────────────────────────────────────────────────────
Detects event-driven catalysts that may precede significant price moves.

Signals tracked:
  • Opportunity Score significant change (Δ > 1.5 vs last reading)
  • Earnings surprise (EPS growth > 20 % YoY)
  • Volatility contraction (BB Width squeeze — pre-expansion setup)
  • Large beta in sector rotation context
"""

from __future__ import annotations

from src.contracts.features import FundamentalFeatureSet, TechnicalFeatureSet
from src.engines.idea_generation.models import (
    DetectorResult,
    IdeaType,
    SignalDetail,
    SignalStrength,
)
from src.engines.alpha_signals.models import SignalCategory
from src.engines.idea_generation.detectors.base import BaseDetector, ScanContext


class EventDetector(BaseDetector):
    """Identifies catalyst-driven opportunities."""

    name = "event"
    weight = 0.9
    signal_category = SignalCategory.EVENT

    # ── Thresholds ────────────────────────────────────────────────────────
    SCORE_DELTA_THRESHOLD = 1.5
    EARNINGS_SURPRISE_THRESHOLD = 0.20   # 20 %
    BB_WIDTH_SQUEEZE_THRESHOLD = 0.04    # Tight BB width

    def scan(
        self,
        fundamental: FundamentalFeatureSet | None,
        technical: TechnicalFeatureSet | None,
        context: ScanContext | None = None,
    ) -> DetectorResult | None:
        signals: list[SignalDetail] = []
        total_checks = 4

        # Extract score data from context (if available)
        previous_score = context.previous_score if context else None
        current_score = context.current_score if context else None

        # 1. Score change detection
        if previous_score is not None and current_score is not None:
            delta = abs(current_score - previous_score)
            if delta > self.SCORE_DELTA_THRESHOLD:
                direction = "improvement" if current_score > previous_score else "deterioration"
                signals.append(SignalDetail(
                    name="score_change",
                    description=f"Score {direction}: {previous_score:.1f} → {current_score:.1f} (Δ{delta:.1f})",
                    value=delta,
                    threshold=self.SCORE_DELTA_THRESHOLD,
                    strength=self._strength_from_value(delta, self.SCORE_DELTA_THRESHOLD),
                ))

        # 2. Earnings surprise
        if fundamental is not None and fundamental.earnings_growth_yoy is not None:
            if abs(fundamental.earnings_growth_yoy) > self.EARNINGS_SURPRISE_THRESHOLD:
                direction = "positive" if fundamental.earnings_growth_yoy > 0 else "negative"
                signals.append(SignalDetail(
                    name="earnings_surprise",
                    description=f"Earnings {direction} surprise: {fundamental.earnings_growth_yoy:+.1%} YoY",
                    value=fundamental.earnings_growth_yoy,
                    threshold=self.EARNINGS_SURPRISE_THRESHOLD,
                    strength=self._strength_from_value(
                        abs(fundamental.earnings_growth_yoy),
                        self.EARNINGS_SURPRISE_THRESHOLD,
                    ),
                ))

        # 3. Volatility contraction (BB width squeeze)
        if technical is not None and technical.bb_upper > 0 and technical.bb_basis > 0:
            bb_width = (technical.bb_upper - technical.bb_lower) / technical.bb_basis
            if bb_width < self.BB_WIDTH_SQUEEZE_THRESHOLD:
                signals.append(SignalDetail(
                    name="volatility_squeeze",
                    description=f"BB Width {bb_width:.3f} — volatility contraction (pre-expansion)",
                    value=bb_width,
                    threshold=self.BB_WIDTH_SQUEEZE_THRESHOLD,
                    strength=(
                        SignalStrength.STRONG if bb_width < 0.02
                        else SignalStrength.MODERATE
                    ),
                ))

        # 4. High beta indicates sector-rotation sensitivity
        if fundamental is not None and fundamental.beta is not None:
            if fundamental.beta > 1.5:
                signals.append(SignalDetail(
                    name="high_beta_catalyst",
                    description=f"Beta {fundamental.beta:.2f} — sensitive to sector rotation",
                    value=fundamental.beta,
                    threshold=1.5,
                    strength=self._strength_from_value(fundamental.beta, 1.5),
                ))

        if not signals:
            return None

        confidence = self._confidence_from_ratio(len(signals), total_checks)
        signal_strength = len(signals) / total_checks

        return DetectorResult(
            idea_type=IdeaType.EVENT,
            confidence=confidence,
            signal_strength=round(signal_strength, 2),
            signals=signals,
            metadata={
                "signals_fired": len(signals),
                "total_possible": total_checks,
                "has_score_delta": previous_score is not None,
            },
        )
