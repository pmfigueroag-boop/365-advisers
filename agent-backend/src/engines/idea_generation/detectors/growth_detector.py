"""
src/engines/idea_generation/detectors/growth_detector.py
──────────────────────────────────────────────────────────────────────────────
Detects high-growth equities using fundamental growth signals.

Signals tracked:
  • Revenue Acceleration (QoQ growth rate increasing)
  • Earnings Surprise (EPS beat > 5%)
  • Operating Leverage (Earnings growth > Revenue growth)
  • Revenue Acceleration (second-derivative of revenue growth positive)
"""

from __future__ import annotations

from src.contracts.features import FundamentalFeatureSet, TechnicalFeatureSet
from src.engines.idea_generation.models import (
    DetectorResult,
    IdeaType,
    SignalDetail,
)
from src.engines.alpha_signals.models import SignalCategory
from src.engines.idea_generation.detectors.base import BaseDetector, ScanContext


class GrowthDetector(BaseDetector):
    """Identifies stocks exhibiting accelerating growth characteristics."""

    name = "growth"
    weight = 1.0
    signal_category = SignalCategory.GROWTH

    # ── Thresholds ────────────────────────────────────────────────────────
    REVENUE_GROWTH_THRESHOLD = 0.10       # 10% YoY
    EARNINGS_SURPRISE_THRESHOLD = 0.05    # 5% EPS beat
    OPERATING_LEVERAGE_MIN = 1.0          # Earnings growth / Revenue growth
    REVENUE_ACCEL_THRESHOLD = 0.0         # Positive acceleration

    def scan(
        self,
        fundamental: FundamentalFeatureSet | None,
        technical: TechnicalFeatureSet | None,
        context: ScanContext | None = None,
    ) -> DetectorResult | None:
        if fundamental is None:
            return None

        signals: list[SignalDetail] = []
        total_checks = 4

        # 1. Revenue Growth
        rev_growth = getattr(fundamental, "revenue_growth_yoy", None)
        if rev_growth is not None and rev_growth > self.REVENUE_GROWTH_THRESHOLD:
            signals.append(SignalDetail(
                name="revenue_growth_strong",
                description=f"Revenue Growth {rev_growth:.1%} exceeds {self.REVENUE_GROWTH_THRESHOLD:.0%}",
                value=rev_growth,
                threshold=self.REVENUE_GROWTH_THRESHOLD,
                strength=self._strength_from_value(
                    rev_growth, self.REVENUE_GROWTH_THRESHOLD
                ),
            ))

        # 2. Earnings Surprise
        earnings_growth = getattr(fundamental, "earnings_growth_yoy", None)
        if earnings_growth is not None and earnings_growth > self.EARNINGS_SURPRISE_THRESHOLD:
            signals.append(SignalDetail(
                name="earnings_momentum",
                description=f"Earnings Growth {earnings_growth:.1%} exceeds {self.EARNINGS_SURPRISE_THRESHOLD:.0%}",
                value=earnings_growth,
                threshold=self.EARNINGS_SURPRISE_THRESHOLD,
                strength=self._strength_from_value(
                    earnings_growth, self.EARNINGS_SURPRISE_THRESHOLD
                ),
            ))

        # 3. Operating Leverage (earnings growing faster than revenue)
        # True operating leverage = Earnings growth / Revenue growth > 1.0
        # This means each unit of revenue growth translates into more than
        # proportional earnings growth — the fundamental definition.
        if (
            rev_growth is not None and rev_growth > 0.01
            and earnings_growth is not None and earnings_growth > 0
        ):
            op_leverage = earnings_growth / rev_growth
            if op_leverage > self.OPERATING_LEVERAGE_MIN:
                signals.append(SignalDetail(
                    name="operating_leverage",
                    description=f"Operating leverage {op_leverage:.1f}× (EPS growth {earnings_growth:.1%} / Rev growth {rev_growth:.1%})",
                    value=op_leverage,
                    threshold=self.OPERATING_LEVERAGE_MIN,
                    strength=self._strength_from_value(op_leverage, self.OPERATING_LEVERAGE_MIN),
                ))

        # 4. Revenue Acceleration (second derivative — growth is accelerating)
        # Uses the slope of the growth rate series computed in feature extraction.
        # Positive acceleration means the company is not just growing, but
        # growing *faster* — the strongest growth signal.
        rev_accel = getattr(fundamental, "revenue_acceleration", None)
        if rev_accel is not None and rev_accel > self.REVENUE_ACCEL_THRESHOLD:
            signals.append(SignalDetail(
                name="revenue_accelerating",
                description=f"Revenue acceleration {rev_accel:+.4f} — growth rate increasing",
                value=rev_accel,
                threshold=self.REVENUE_ACCEL_THRESHOLD,
                strength=self._strength_from_value(max(rev_accel, 0.001), 0.01),
            ))

        if not signals:
            return None

        confidence = self._confidence_from_ratio(len(signals), total_checks)
        signal_strength = len(signals) / total_checks

        return DetectorResult(
            idea_type=IdeaType.GROWTH,
            confidence=confidence,
            signal_strength=round(signal_strength, 2),
            signals=signals,
            metadata={
                "signals_fired": len(signals),
                "total_possible": total_checks,
                "source": "growth_detector",
            },
        )
