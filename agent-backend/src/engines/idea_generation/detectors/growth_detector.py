"""
src/engines/idea_generation/detectors/growth_detector.py
──────────────────────────────────────────────────────────────────────────────
Detects high-growth equities using fundamental growth signals.

Signals tracked:
  • Revenue Acceleration (QoQ growth rate increasing)
  • Earnings Surprise (EPS beat > 5%)
  • Operating Leverage (EBIT growth > Revenue growth)
  • CapEx Intensity (CapEx / D&A > 1.3)
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
    OPERATING_LEVERAGE_THRESHOLD = 1.5    # EBIT growth / Rev growth
    CAPEX_INTENSITY_THRESHOLD = 1.3       # CapEx / D&A

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

        # 1. Revenue Growth / Acceleration
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

        # 3. Operating Leverage (proxy: margin_trend > 0 implies EBIT growing faster)
        margin_trend = getattr(fundamental, "margin_trend", None)
        if margin_trend is not None and margin_trend > 0.03:
            signals.append(SignalDetail(
                name="operating_leverage",
                description=f"Margin expansion {margin_trend:.1%} signals operating leverage",
                value=margin_trend,
                threshold=0.03,
                strength=self._strength_from_value(margin_trend, 0.03),
            ))

        # 4. CapEx Intensity (proxy: high beta often correlates with growth investment)
        roic = getattr(fundamental, "roic", None)
        if roic is not None and roic > 0.20:
            signals.append(SignalDetail(
                name="high_growth_returns",
                description=f"ROIC {roic:.1%} indicates high-return growth investment",
                value=roic,
                threshold=0.20,
                strength=self._strength_from_value(roic, 0.20),
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
