"""
src/engines/idea_generation/detectors/quality_detector.py
──────────────────────────────────────────────────────────────────────────────
Detects high-quality business franchises using profitability, stability
and leverage signals.

Signals tracked:
  • ROIC > 15 %
  • Margin trend ≥ 0 (stable or expanding)
  • Revenue growth > 5 % AND earnings growth > 0 %
  • Earnings stability > 7.0
  • Debt-to-equity < 0.5
"""

from __future__ import annotations

from src.contracts.features import FundamentalFeatureSet, TechnicalFeatureSet
from src.engines.idea_generation.models import (
    DetectorResult,
    IdeaType,
    SignalDetail,
)
from src.engines.idea_generation.detectors.base import BaseDetector


class QualityDetector(BaseDetector):
    """Identifies companies with durable competitive advantages."""

    name = "quality"
    weight = 1.0

    # ── Thresholds ────────────────────────────────────────────────────────
    ROIC_THRESHOLD = 0.15           # 15 %
    MARGIN_TREND_THRESHOLD = 0.0    # non-negative
    REV_GROWTH_THRESHOLD = 0.05     # 5 %
    EARN_GROWTH_THRESHOLD = 0.0     # positive
    EARN_STABILITY_THRESHOLD = 7.0  # out of 10
    DTE_THRESHOLD = 0.5

    def scan(
        self,
        fundamental: FundamentalFeatureSet | None,
        technical: TechnicalFeatureSet | None,
    ) -> DetectorResult | None:
        if fundamental is None:
            return None

        signals: list[SignalDetail] = []
        total_checks = 5

        # 1. High ROIC
        if fundamental.roic is not None and fundamental.roic > self.ROIC_THRESHOLD:
            signals.append(SignalDetail(
                name="roic_high",
                description=f"ROIC {fundamental.roic:.1%} exceeds {self.ROIC_THRESHOLD:.0%}",
                value=fundamental.roic,
                threshold=self.ROIC_THRESHOLD,
                strength=self._strength_from_value(
                    fundamental.roic, self.ROIC_THRESHOLD
                ),
            ))

        # 2. Stable or expanding margins
        if fundamental.margin_trend is not None and fundamental.margin_trend >= self.MARGIN_TREND_THRESHOLD:
            signals.append(SignalDetail(
                name="margin_stable",
                description=f"Margin trend {fundamental.margin_trend:+.2%} — stable or expanding",
                value=fundamental.margin_trend,
                threshold=self.MARGIN_TREND_THRESHOLD,
                strength=self._strength_from_value(
                    max(fundamental.margin_trend, 0.01), 0.01
                ),
            ))

        # 3. Profitable growth
        rev_ok = (
            fundamental.revenue_growth_yoy is not None
            and fundamental.revenue_growth_yoy > self.REV_GROWTH_THRESHOLD
        )
        earn_ok = (
            fundamental.earnings_growth_yoy is not None
            and fundamental.earnings_growth_yoy > self.EARN_GROWTH_THRESHOLD
        )
        if rev_ok and earn_ok:
            signals.append(SignalDetail(
                name="profitable_growth",
                description=(
                    f"Revenue +{fundamental.revenue_growth_yoy:.1%} / "
                    f"Earnings +{fundamental.earnings_growth_yoy:.1%}"
                ),
                value=fundamental.revenue_growth_yoy,  # type: ignore[arg-type]
                threshold=self.REV_GROWTH_THRESHOLD,
                strength=self._strength_from_value(
                    fundamental.revenue_growth_yoy, self.REV_GROWTH_THRESHOLD  # type: ignore[arg-type]
                ),
            ))

        # 4. Earnings Stability
        if (
            fundamental.earnings_stability is not None
            and fundamental.earnings_stability > self.EARN_STABILITY_THRESHOLD
        ):
            signals.append(SignalDetail(
                name="earnings_stable",
                description=f"Earnings Stability {fundamental.earnings_stability:.1f}/10",
                value=fundamental.earnings_stability,
                threshold=self.EARN_STABILITY_THRESHOLD,
                strength=self._strength_from_value(
                    fundamental.earnings_stability, self.EARN_STABILITY_THRESHOLD
                ),
            ))

        # 5. Low leverage
        if fundamental.debt_to_equity is not None and fundamental.debt_to_equity < self.DTE_THRESHOLD:
            signals.append(SignalDetail(
                name="low_leverage",
                description=f"D/E {fundamental.debt_to_equity:.2f} below {self.DTE_THRESHOLD:.1f}",
                value=fundamental.debt_to_equity,
                threshold=self.DTE_THRESHOLD,
                strength=self._strength_from_value(
                    self.DTE_THRESHOLD - fundamental.debt_to_equity,
                    self.DTE_THRESHOLD * 0.3,
                ),
            ))

        if not signals:
            return None

        confidence = self._confidence_from_ratio(len(signals), total_checks)
        signal_strength = len(signals) / total_checks

        return DetectorResult(
            idea_type=IdeaType.QUALITY,
            confidence=confidence,
            signal_strength=round(signal_strength, 2),
            signals=signals,
            metadata={
                "signals_fired": len(signals),
                "total_possible": total_checks,
            },
        )
