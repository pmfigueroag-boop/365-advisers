"""
src/engines/technical/scoring.py
─────────────────────────────────────────────────────────────────────────────
ScoringEngine — converts IndicatorResult into a normalised 0–10 score per
module and an aggregated TechnicalScore.

All scoring logic is deterministic and rule-based (no LLM).
Weights are configurable per indicator module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.engines.technical.indicators import IndicatorResult


# ─── Score types ─────────────────────────────────────────────────────────────

@dataclass
class ModuleScores:
    trend:      float   # 0–10
    momentum:   float
    volatility: float
    volume:     float
    structure:  float


@dataclass
class TechnicalScore:
    aggregate: float    # 0–10, weighted
    modules:   ModuleScores
    signal:    Literal["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"]
    strength:  Literal["Strong", "Moderate", "Weak"]


# ─── Module weights ───────────────────────────────────────────────────────────

DEFAULT_WEIGHTS = {
    "trend":      0.30,
    "momentum":   0.25,
    "volatility": 0.20,
    "volume":     0.15,
    "structure":  0.10,
}


# ─── Individual score functions ───────────────────────────────────────────────

STATUS_SCORES = {
    "STRONG_BULLISH": 9.5,
    "BULLISH":        7.5,
    "NEUTRAL":        5.0,
    "BEARISH":        3.0,
    "STRONG_BEARISH": 1.0,
}


def _score_trend(result) -> float:
    return STATUS_SCORES.get(result.status, 5.0)


def _score_momentum(result) -> float:
    base = STATUS_SCORES.get(result.status, 5.0)

    # RSI fine-tuning within neutral zone
    rsi = result.rsi
    if result.rsi_zone == "NEUTRAL":
        if 50 < rsi < 60:
            base += 0.5
        elif 40 < rsi < 50:
            base -= 0.5

    return round(max(0.0, min(10.0, base)), 2)


def _score_volatility(result) -> float:
    """
    Volatility scoring is context-aware, not directional.
    Normal volatility scores 6–7 (healthy market).
    HIGH or LOW extremes score lower (risk flags).
    The BB position adds directional color.
    """
    condition_base = {
        "NORMAL":   7.0,
        "ELEVATED": 5.5,
        "HIGH":     3.5,
        "LOW":      5.0,
    }.get(result.condition, 5.0)

    # BB position adjustment
    bb_adj = {
        "LOWER":      1.5,   # potential bounce
        "LOWER_MID":  0.5,
        "MID":        0.0,
        "UPPER_MID": -0.5,
        "UPPER":     -1.0,   # overbought territory
    }.get(result.bb_position, 0.0)

    return round(max(0.0, min(10.0, condition_base + bb_adj)), 2)


def _score_volume(result) -> float:
    base = {
        "STRONG": 8.0,
        "NORMAL": 5.5,
        "WEAK":   3.0,
    }.get(result.status, 5.0)

    # OBV trend adjustment
    obv_adj = {
        "RISING":  1.0,
        "FLAT":    0.0,
        "FALLING": -1.0,
    }.get(result.obv_trend, 0.0)

    return round(max(0.0, min(10.0, base + obv_adj)), 2)


def _score_structure(result) -> float:
    """Score based on breakout probability, direction, and V2 data."""
    bp = result.breakout_probability   # 0–1.0
    direction = result.breakout_direction

    if direction == "BULLISH":
        base = 5.0 + bp * 5.0        # 5.0 – 10.0
    elif direction == "BEARISH":
        base = 5.0 - bp * 4.0        # 1.0 – 5.0
    else:
        base = 4.5 + bp * 1.5        # 4.5 – 6.0 neutral zone

    # V2: Market structure alignment bonus
    ms = getattr(result, "market_structure", "MIXED")
    if ms == "HH_HL" and direction == "BULLISH":
        base += 1.0   # uptrend structure confirms bullish breakout
    elif ms == "LH_LL" and direction == "BEARISH":
        base += 0.5   # downtrend confirmed
    elif ms == "LH_LL" and direction == "BULLISH":
        base -= 1.0   # structure conflicts with breakout direction

    # V2: Strong level support
    level_str = getattr(result, "level_strength", {})
    if any(v.get("strong", False) for v in level_str.values()):
        base += 0.5   # strong levels add confidence

    # V2: Pattern signals
    patterns = getattr(result, "patterns", [])
    if "DOUBLE_BOTTOM" in patterns or "HIGHER_LOWS" in patterns:
        base += 0.5
    if "DOUBLE_TOP" in patterns or "LOWER_HIGHS" in patterns:
        base -= 0.5

    return round(max(0.0, min(10.0, base)), 2)


# ─── Aggregate + Signal derivation ───────────────────────────────────────────

def _derive_signal(score: float) -> Literal["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"]:
    if score >= 8.0:
        return "STRONG_BUY"
    if score >= 6.5:
        return "BUY"
    if score >= 4.5:
        return "NEUTRAL"
    if score >= 3.0:
        return "SELL"
    return "STRONG_SELL"


def _derive_strength(score: float) -> Literal["Strong", "Moderate", "Weak"]:
    if score >= 7.5 or score <= 2.5:
        return "Strong"
    if score >= 6.0 or score <= 4.0:
        return "Moderate"
    return "Weak"


# ─── ScoringEngine ───────────────────────────────────────────────────────────

class ScoringEngine:
    """Deterministic scorer. No LLM. Fully testable."""

    @staticmethod
    def compute(
        result: IndicatorResult,
        weights: dict[str, float] | None = None,
        regime_adjustments: dict[str, float] | None = None,
    ) -> TechnicalScore:
        w = dict(weights or DEFAULT_WEIGHTS)  # copy to avoid mutation

        # Apply regime-based weight adjustments if provided
        if regime_adjustments:
            for module, multiplier in regime_adjustments.items():
                if module in w:
                    w[module] = w[module] * multiplier

        modules = ModuleScores(
            trend      = _score_trend(result.trend),
            momentum   = _score_momentum(result.momentum),
            volatility = _score_volatility(result.volatility),
            volume     = _score_volume(result.volume),
            structure  = _score_structure(result.structure),
        )

        aggregate = (
            modules.trend      * w["trend"]      +
            modules.momentum   * w["momentum"]   +
            modules.volatility * w["volatility"] +
            modules.volume     * w["volume"]     +
            modules.structure  * w["structure"]
        ) / sum(w.values())

        aggregate = round(aggregate, 2)

        return TechnicalScore(
            aggregate = aggregate,
            modules   = modules,
            signal    = _derive_signal(aggregate),
            strength  = _derive_strength(aggregate),
        )
