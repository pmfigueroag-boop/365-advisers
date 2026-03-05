"""
src/engines/idea_generation/detectors/value_detector.py
──────────────────────────────────────────────────────────────────────────────
Detects undervalued equities using fundamental valuation signals.

Signals tracked:
  • FCF Yield > 8%
  • P/E < 15
  • EV/EBITDA < 10
  • P/B < 1.5
"""

from __future__ import annotations

from src.contracts.features import FundamentalFeatureSet, TechnicalFeatureSet
from src.engines.idea_generation.models import (
    DetectorResult,
    IdeaType,
    SignalDetail,
)
from src.engines.alpha_signals.models import SignalCategory
from src.engines.idea_generation.detectors.base import BaseDetector


class ValueDetector(BaseDetector):
    """Identifies stocks trading at a discount to intrinsic metrics."""

    name = "value"
    weight = 1.0
    signal_category = SignalCategory.VALUE

    # ── Thresholds ────────────────────────────────────────────────────────
    FCF_YIELD_THRESHOLD = 0.08      # 8 %
    PE_THRESHOLD = 15.0
    EV_EBITDA_THRESHOLD = 10.0
    PB_THRESHOLD = 1.5

    def scan(
        self,
        fundamental: FundamentalFeatureSet | None,
        technical: TechnicalFeatureSet | None,
    ) -> DetectorResult | None:
        if fundamental is None:
            return None

        signals: list[SignalDetail] = []
        total_checks = 4

        # 1. FCF Yield
        if fundamental.fcf_yield is not None and fundamental.fcf_yield > self.FCF_YIELD_THRESHOLD:
            signals.append(SignalDetail(
                name="fcf_yield_high",
                description=f"FCF Yield {fundamental.fcf_yield:.1%} exceeds {self.FCF_YIELD_THRESHOLD:.0%}",
                value=fundamental.fcf_yield,
                threshold=self.FCF_YIELD_THRESHOLD,
                strength=self._strength_from_value(
                    fundamental.fcf_yield, self.FCF_YIELD_THRESHOLD
                ),
            ))

        # 2. Low P/E
        if fundamental.pe_ratio is not None and 0 < fundamental.pe_ratio < self.PE_THRESHOLD:
            signals.append(SignalDetail(
                name="pe_low",
                description=f"P/E {fundamental.pe_ratio:.1f} below {self.PE_THRESHOLD:.0f}",
                value=fundamental.pe_ratio,
                threshold=self.PE_THRESHOLD,
                strength=self._strength_from_value(
                    self.PE_THRESHOLD - fundamental.pe_ratio,
                    self.PE_THRESHOLD * 0.3,
                ),
            ))

        # 3. Low EV/EBITDA
        if fundamental.ev_ebitda is not None and 0 < fundamental.ev_ebitda < self.EV_EBITDA_THRESHOLD:
            signals.append(SignalDetail(
                name="ev_ebitda_low",
                description=f"EV/EBITDA {fundamental.ev_ebitda:.1f} below {self.EV_EBITDA_THRESHOLD:.0f}",
                value=fundamental.ev_ebitda,
                threshold=self.EV_EBITDA_THRESHOLD,
                strength=self._strength_from_value(
                    self.EV_EBITDA_THRESHOLD - fundamental.ev_ebitda,
                    self.EV_EBITDA_THRESHOLD * 0.3,
                ),
            ))

        # 4. Low P/B
        if fundamental.pb_ratio is not None and 0 < fundamental.pb_ratio < self.PB_THRESHOLD:
            signals.append(SignalDetail(
                name="pb_low",
                description=f"P/B {fundamental.pb_ratio:.2f} below {self.PB_THRESHOLD:.1f}",
                value=fundamental.pb_ratio,
                threshold=self.PB_THRESHOLD,
                strength=self._strength_from_value(
                    self.PB_THRESHOLD - fundamental.pb_ratio,
                    self.PB_THRESHOLD * 0.3,
                ),
            ))

        if not signals:
            return None

        confidence = self._confidence_from_ratio(len(signals), total_checks)
        signal_strength = len(signals) / total_checks

        return DetectorResult(
            idea_type=IdeaType.VALUE,
            confidence=confidence,
            signal_strength=round(signal_strength, 2),
            signals=signals,
            metadata={
                "signals_fired": len(signals),
                "total_possible": total_checks,
            },
        )
