"""
src/engines/technical/regime_detector.py
─────────────────────────────────────────────────────────────────────────────
Regime Detection for the Technical Score V2.

Two detectors:
  TrendRegimeDetector   — ADX + DI → TRENDING / RANGING / TRANSITIONING / VOLATILE
  VolatilityRegimeDetector — BB width history + ATR → COMPRESSION / EXPANSION / MEAN_REVERTING / STABLE

Each detector returns a regime label and a dict of weight multipliers
that dynamically adjust module weights in the ScoringEngine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ─── Trend Regime ────────────────────────────────────────────────────────────

TrendRegime = Literal["TRENDING", "RANGING", "TRANSITIONING", "VOLATILE"]


@dataclass
class TrendRegimeResult:
    regime: TrendRegime
    adx: float
    plus_di: float
    minus_di: float
    di_spread: float          # abs(+DI - -DI)
    weight_adjustments: dict[str, float] = field(default_factory=dict)


class TrendRegimeDetector:
    """
    Classify the market into a trend regime using ADX and directional
    indicators (+DI / -DI).

    Rules:
      TRENDING      — ADX > 25 AND abs(+DI - -DI) > 10  → clear direction
      RANGING       — ADX < 20                           → no trend
      TRANSITIONING — 20 ≤ ADX ≤ 25                      → ambiguous
      VOLATILE      — ADX > 25 AND abs(+DI - -DI) ≤ 10  → strong moves, no direction
    """

    @staticmethod
    def detect(
        adx: float = 20.0,
        plus_di: float = 20.0,
        minus_di: float = 20.0,
    ) -> TrendRegimeResult:
        di_spread = abs(plus_di - minus_di)

        if adx > 25 and di_spread > 10:
            regime: TrendRegime = "TRENDING"
            adjustments = {
                "trend": 1.2,
                "momentum": 1.0,
                "volatility": 1.0,
                "volume": 1.0,
                "structure": 0.7,      # S/R less relevant in strong trends
            }
        elif adx < 20:
            regime = "RANGING"
            adjustments = {
                "trend": 0.8,          # trend signals less reliable
                "momentum": 1.3,       # mean-reversion dominates
                "volatility": 1.0,
                "volume": 1.0,
                "structure": 1.2,      # S/R very relevant in ranges
            }
        elif adx > 25 and di_spread <= 10:
            regime = "VOLATILE"
            adjustments = {
                "trend": 0.9,
                "momentum": 0.9,
                "volatility": 1.3,     # volatility is the dominant signal
                "volume": 1.0,
                "structure": 0.9,
            }
        else:
            regime = "TRANSITIONING"
            adjustments = {
                "trend": 1.0,
                "momentum": 1.0,
                "volatility": 1.0,
                "volume": 1.0,
                "structure": 1.0,
            }

        return TrendRegimeResult(
            regime=regime,
            adx=round(adx, 2),
            plus_di=round(plus_di, 2),
            minus_di=round(minus_di, 2),
            di_spread=round(di_spread, 2),
            weight_adjustments=adjustments,
        )


# ─── Volatility Regime ───────────────────────────────────────────────────────

VolatilityRegime = Literal["COMPRESSION", "EXPANSION", "MEAN_REVERTING", "STABLE"]


@dataclass
class VolatilityRegimeResult:
    regime: VolatilityRegime
    bb_width_current: float
    bb_width_avg_20: float
    bb_width_min_20: float
    bb_width_ratio: float     # current / avg_20
    atr_trend: Literal["RISING", "FLAT", "FALLING"]
    weight_adjustments: dict[str, float] = field(default_factory=dict)


class VolatilityRegimeDetector:
    """
    Classify the volatility regime using BB width history and ATR trend.

    Rules (using BB width relative to 20-period average):
      COMPRESSION    — BB width < 0.7× avg AND ATR declining  → calm before storm
      EXPANSION      — BB width > 1.3× avg AND ATR rising     → volatility event
      MEAN_REVERTING — BB width > 1.3× avg AND ATR stabilizing → post-event
      STABLE         — everything else                          → normal ops
    """

    @staticmethod
    def detect(
        ohlcv: list[dict],
        current_bb_upper: float = 0.0,
        current_bb_lower: float = 0.0,
        current_atr: float = 0.0,
    ) -> VolatilityRegimeResult:

        # ── Compute BB width series from OHLCV ──────────────────────────────
        # BB width ≈ (upper - lower) / basis.  Without full series, approximate
        # using high-low range as a proxy for historical volatility.
        bb_width_current = (
            (current_bb_upper - current_bb_lower)
            if current_bb_upper > 0 and current_bb_lower > 0
            else 0.0
        )

        # Use OHLCV to compute rolling high-low range as BB width proxy
        if len(ohlcv) >= 40:
            hl_ranges = [
                (b.get("high", 0) - b.get("low", 0))
                for b in ohlcv[-40:]
                if b.get("high") and b.get("low")
            ]
        else:
            hl_ranges = [
                (b.get("high", 0) - b.get("low", 0))
                for b in ohlcv
                if b.get("high") and b.get("low")
            ]

        if not hl_ranges or len(hl_ranges) < 10:
            return VolatilityRegimeResult(
                regime="STABLE",
                bb_width_current=bb_width_current,
                bb_width_avg_20=0.0,
                bb_width_min_20=0.0,
                bb_width_ratio=1.0,
                atr_trend="FLAT",
                weight_adjustments=_stable_adjustments(),
            )

        # Use last 20 ranges for average, last 20 for min
        recent_20 = hl_ranges[-20:]
        bb_width_avg_20 = sum(recent_20) / len(recent_20) if recent_20 else 1.0
        bb_width_min_20 = min(recent_20) if recent_20 else 0.0

        # Ratio: how does current BB compare to average
        bb_width_ratio = (
            bb_width_current / bb_width_avg_20
            if bb_width_avg_20 > 0
            else 1.0
        )

        # If BB width is zero (no TV data), fall back to range-based ratio
        if bb_width_current == 0 and len(hl_ranges) >= 5:
            recent_5_avg = sum(hl_ranges[-5:]) / 5
            bb_width_ratio = recent_5_avg / bb_width_avg_20 if bb_width_avg_20 > 0 else 1.0
            bb_width_current = recent_5_avg

        # ── ATR trend detection (last 10 vs previous 10 daily ranges) ────────
        if len(hl_ranges) >= 20:
            early = sum(hl_ranges[-20:-10]) / 10
            late = sum(hl_ranges[-10:]) / 10
            if late > early * 1.15:
                atr_trend = "RISING"
            elif late < early * 0.85:
                atr_trend = "FALLING"
            else:
                atr_trend = "FLAT"
        else:
            atr_trend = "FLAT"

        # ── Regime classification ────────────────────────────────────────────
        if bb_width_ratio < 0.7 and atr_trend in ("FALLING", "FLAT"):
            regime: VolatilityRegime = "COMPRESSION"
            adjustments = {
                "trend": 1.0,
                "momentum": 1.0,
                "volatility": 1.0,
                "volume": 1.1,
                "structure": 1.5,      # breakout imminent, S/R matters a lot
            }
        elif bb_width_ratio > 1.3 and atr_trend == "RISING":
            regime = "EXPANSION"
            adjustments = {
                "trend": 1.1,
                "momentum": 1.0,
                "volatility": 1.3,     # vol is the dominant story
                "volume": 1.0,
                "structure": 0.5,      # S/R levels getting blown through
            }
        elif bb_width_ratio > 1.3 and atr_trend in ("FALLING", "FLAT"):
            regime = "MEAN_REVERTING"
            adjustments = {
                "trend": 0.9,
                "momentum": 1.2,       # mean-reversion plays
                "volatility": 1.1,
                "volume": 1.0,
                "structure": 1.0,
            }
        else:
            regime = "STABLE"
            adjustments = _stable_adjustments()

        return VolatilityRegimeResult(
            regime=regime,
            bb_width_current=round(bb_width_current, 4),
            bb_width_avg_20=round(bb_width_avg_20, 4),
            bb_width_min_20=round(bb_width_min_20, 4),
            bb_width_ratio=round(bb_width_ratio, 4),
            atr_trend=atr_trend,
            weight_adjustments=adjustments,
        )


def _stable_adjustments() -> dict[str, float]:
    return {
        "trend": 1.0,
        "momentum": 1.0,
        "volatility": 1.0,
        "volume": 1.0,
        "structure": 1.0,
    }


# ─── Combined Regime Adjustment ──────────────────────────────────────────────

def combine_regime_adjustments(
    trend_regime: TrendRegimeResult,
    vol_regime: VolatilityRegimeResult,
) -> dict[str, float]:
    """
    Merge trend and volatility regime weight adjustments.
    Uses geometric mean so neither regime can dominate excessively.
    """
    combined = {}
    for module in ("trend", "momentum", "volatility", "volume", "structure"):
        t_adj = trend_regime.weight_adjustments.get(module, 1.0)
        v_adj = vol_regime.weight_adjustments.get(module, 1.0)
        # Geometric mean — balances both signals
        combined[module] = round((t_adj * v_adj) ** 0.5, 4)
    return combined
