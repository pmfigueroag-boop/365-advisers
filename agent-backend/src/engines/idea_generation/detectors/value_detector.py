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
from src.engines.idea_generation.detectors.base import BaseDetector, ScanContext


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
        context: ScanContext | None = None,
    ) -> DetectorResult | None:
        if fundamental is None:
            return None

        signals: list[SignalDetail] = []
        total_checks = 4

        # Sector-relative adjustment: scale valuation thresholds by sector
        # median.  Technology (PE ~30) gets a higher PE threshold than
        # Energy (PE ~12), matching how Alpha Signals C4 already operates.
        adj = fundamental.sector_pe_adjustment  # 1.0 = no adjustment
        pe_thr = self.PE_THRESHOLD * adj
        ev_thr = self.EV_EBITDA_THRESHOLD * adj
        pb_thr = self.PB_THRESHOLD * adj

        # 1. FCF Yield (not sector-adjusted — cash is cash)
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

        # 2. Low P/E (sector-adjusted)
        if fundamental.pe_ratio is not None and 0 < fundamental.pe_ratio < pe_thr:
            signals.append(SignalDetail(
                name="pe_low",
                description=f"P/E {fundamental.pe_ratio:.1f} below {pe_thr:.0f} (sector-adj)",
                value=fundamental.pe_ratio,
                threshold=pe_thr,
                strength=self._strength_from_value(
                    pe_thr - fundamental.pe_ratio,
                    pe_thr * 0.3,
                ),
            ))

        # 3. Low EV/EBITDA (sector-adjusted)
        if fundamental.ev_ebitda is not None and 0 < fundamental.ev_ebitda < ev_thr:
            signals.append(SignalDetail(
                name="ev_ebitda_low",
                description=f"EV/EBITDA {fundamental.ev_ebitda:.1f} below {ev_thr:.0f} (sector-adj)",
                value=fundamental.ev_ebitda,
                threshold=ev_thr,
                strength=self._strength_from_value(
                    ev_thr - fundamental.ev_ebitda,
                    ev_thr * 0.3,
                ),
            ))

        # 4. Low P/B (sector-adjusted)
        if fundamental.pb_ratio is not None and 0 < fundamental.pb_ratio < pb_thr:
            signals.append(SignalDetail(
                name="pb_low",
                description=f"P/B {fundamental.pb_ratio:.2f} below {pb_thr:.1f} (sector-adj)",
                value=fundamental.pb_ratio,
                threshold=pb_thr,
                strength=self._strength_from_value(
                    pb_thr - fundamental.pb_ratio,
                    pb_thr * 0.3,
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
