"""
src/engines/idea_generation/detectors/momentum_detector.py
──────────────────────────────────────────────────────────────────────────────
Detects strong upward price trends using technical momentum signals.

Signals tracked:
  • Golden Cross (SMA50 > SMA200)
  • Bullish RSI (50 < RSI < 70)
  • MACD Histogram positive
  • Volume above 1.2× 20-day average
  • Price above EMA-20
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


class MomentumDetector(BaseDetector):
    """Identifies assets exhibiting strong directional momentum."""

    name = "momentum"
    weight = 1.0

    # ── Thresholds ────────────────────────────────────────────────────────
    RSI_LOW = 50.0
    RSI_HIGH = 70.0
    VOLUME_RATIO_THRESHOLD = 1.2
    MACD_HIST_THRESHOLD = 0.0

    def scan(
        self,
        fundamental: FundamentalFeatureSet | None,
        technical: TechnicalFeatureSet | None,
    ) -> DetectorResult | None:
        if technical is None:
            return None

        signals: list[SignalDetail] = []
        total_checks = 5

        # 1. Golden Cross — SMA50 > SMA200
        if technical.sma_50 > 0 and technical.sma_200 > 0:
            if technical.sma_50 > technical.sma_200:
                spread_pct = (technical.sma_50 - technical.sma_200) / technical.sma_200
                signals.append(SignalDetail(
                    name="golden_cross",
                    description=f"SMA50 ({technical.sma_50:.2f}) > SMA200 ({technical.sma_200:.2f})",
                    value=spread_pct,
                    threshold=0.0,
                    strength=(
                        SignalStrength.STRONG if spread_pct > 0.05
                        else SignalStrength.MODERATE if spread_pct > 0.02
                        else SignalStrength.WEAK
                    ),
                ))

        # 2. Bullish RSI (50-70 sweet spot)
        if self.RSI_LOW < technical.rsi < self.RSI_HIGH:
            signals.append(SignalDetail(
                name="rsi_bullish",
                description=f"RSI {technical.rsi:.1f} in bullish zone (50-70)",
                value=technical.rsi,
                threshold=self.RSI_LOW,
                strength=(
                    SignalStrength.STRONG if technical.rsi > 60
                    else SignalStrength.MODERATE
                ),
            ))

        # 3. MACD Histogram positive
        if technical.macd_hist > self.MACD_HIST_THRESHOLD:
            signals.append(SignalDetail(
                name="macd_bullish",
                description=f"MACD Histogram {technical.macd_hist:+.4f} positive",
                value=technical.macd_hist,
                threshold=self.MACD_HIST_THRESHOLD,
                strength=self._strength_from_value(
                    technical.macd_hist, 0.5
                ),
            ))

        # 4. Volume surge
        if technical.volume_avg_20 > 0:
            vol_ratio = technical.volume / technical.volume_avg_20
            if vol_ratio > self.VOLUME_RATIO_THRESHOLD:
                signals.append(SignalDetail(
                    name="volume_surge",
                    description=f"Volume {vol_ratio:.1f}× above 20-day avg",
                    value=vol_ratio,
                    threshold=self.VOLUME_RATIO_THRESHOLD,
                    strength=self._strength_from_value(
                        vol_ratio, self.VOLUME_RATIO_THRESHOLD
                    ),
                ))

        # 5. Price above EMA20
        if technical.ema_20 > 0 and technical.current_price > technical.ema_20:
            spread_pct = (technical.current_price - technical.ema_20) / technical.ema_20
            signals.append(SignalDetail(
                name="above_ema20",
                description=f"Price ${technical.current_price:.2f} above EMA20 ${technical.ema_20:.2f}",
                value=spread_pct,
                threshold=0.0,
                strength=(
                    SignalStrength.STRONG if spread_pct > 0.03
                    else SignalStrength.MODERATE if spread_pct > 0.01
                    else SignalStrength.WEAK
                ),
            ))

        if not signals:
            return None

        confidence = self._confidence_from_ratio(len(signals), total_checks)
        signal_strength = len(signals) / total_checks

        return DetectorResult(
            idea_type=IdeaType.MOMENTUM,
            confidence=confidence,
            signal_strength=round(signal_strength, 2),
            signals=signals,
            metadata={
                "signals_fired": len(signals),
                "total_possible": total_checks,
            },
        )
