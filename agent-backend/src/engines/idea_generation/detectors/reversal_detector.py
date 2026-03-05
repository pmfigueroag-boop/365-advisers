"""
src/engines/idea_generation/detectors/reversal_detector.py
──────────────────────────────────────────────────────────────────────────────
Detects potential trend reversals — oversold conditions or capitulation
setups that may precede a price recovery.

Signals tracked:
  • RSI oversold (< 30)
  • Stochastic oversold (%K < 20)
  • Price near/below Bollinger Band lower
  • MACD histogram turning positive (bear → bull crossover)
  • Volume capitulation spike (> 2× 20-day avg)
"""

from __future__ import annotations

from src.contracts.features import FundamentalFeatureSet, TechnicalFeatureSet
from src.engines.idea_generation.models import (
    DetectorResult,
    IdeaType,
    SignalDetail,
    SignalStrength,
)
from src.engines.idea_generation.detectors.base import BaseDetector


class ReversalDetector(BaseDetector):
    """Identifies potential bottom / reversal setups."""

    name = "reversal"
    weight = 0.8  # slightly lower weight — reversals are higher risk

    # ── Thresholds ────────────────────────────────────────────────────────
    RSI_OVERSOLD = 30.0
    STOCH_OVERSOLD = 20.0
    BB_PROXIMITY = 1.02          # within 2 % of lower band
    VOLUME_CAPITULATION = 2.0    # 2× average

    def scan(
        self,
        fundamental: FundamentalFeatureSet | None,
        technical: TechnicalFeatureSet | None,
    ) -> DetectorResult | None:
        if technical is None:
            return None

        signals: list[SignalDetail] = []
        total_checks = 5

        # 1. RSI oversold
        if technical.rsi < self.RSI_OVERSOLD:
            signals.append(SignalDetail(
                name="rsi_oversold",
                description=f"RSI {technical.rsi:.1f} in oversold territory (< 30)",
                value=technical.rsi,
                threshold=self.RSI_OVERSOLD,
                strength=(
                    SignalStrength.STRONG if technical.rsi < 20
                    else SignalStrength.MODERATE if technical.rsi < 25
                    else SignalStrength.WEAK
                ),
            ))

        # 2. Stochastic oversold
        if technical.stoch_k < self.STOCH_OVERSOLD:
            signals.append(SignalDetail(
                name="stoch_oversold",
                description=f"Stochastic %K {technical.stoch_k:.1f} oversold (< 20)",
                value=technical.stoch_k,
                threshold=self.STOCH_OVERSOLD,
                strength=(
                    SignalStrength.STRONG if technical.stoch_k < 10
                    else SignalStrength.MODERATE
                ),
            ))

        # 3. Price near Bollinger Band lower
        if technical.bb_lower > 0 and technical.current_price > 0:
            ratio = technical.current_price / technical.bb_lower
            if ratio <= self.BB_PROXIMITY:
                signals.append(SignalDetail(
                    name="near_bb_lower",
                    description=f"Price ${technical.current_price:.2f} within {((ratio - 1) * 100):.1f}% of BB lower ${technical.bb_lower:.2f}",
                    value=ratio,
                    threshold=self.BB_PROXIMITY,
                    strength=(
                        SignalStrength.STRONG if ratio <= 1.0
                        else SignalStrength.MODERATE
                    ),
                ))

        # 4. MACD histogram turning positive (early reversal)
        # We detect when the histogram is very small negative or just crossed zero
        if -0.1 <= technical.macd_hist <= 0.3 and technical.macd < 0:
            signals.append(SignalDetail(
                name="macd_reversal",
                description=f"MACD histogram {technical.macd_hist:+.4f} near zero crossover with MACD negative",
                value=technical.macd_hist,
                threshold=0.0,
                strength=SignalStrength.MODERATE,
            ))

        # 5. Volume capitulation spike
        if technical.volume_avg_20 > 0:
            vol_ratio = technical.volume / technical.volume_avg_20
            if vol_ratio > self.VOLUME_CAPITULATION:
                signals.append(SignalDetail(
                    name="volume_capitulation",
                    description=f"Volume {vol_ratio:.1f}× avg — potential capitulation",
                    value=vol_ratio,
                    threshold=self.VOLUME_CAPITULATION,
                    strength=self._strength_from_value(
                        vol_ratio, self.VOLUME_CAPITULATION
                    ),
                ))

        if not signals:
            return None

        # Reversals need at least 2 confirming signals to be meaningful
        if len(signals) < 2:
            return None

        confidence = self._confidence_from_ratio(len(signals), total_checks)
        signal_strength = len(signals) / total_checks

        return DetectorResult(
            idea_type=IdeaType.REVERSAL,
            confidence=confidence,
            signal_strength=round(signal_strength, 2),
            signals=signals,
            metadata={
                "signals_fired": len(signals),
                "total_possible": total_checks,
                "note": "Reversal ideas require at least 2 confirming signals",
            },
        )
