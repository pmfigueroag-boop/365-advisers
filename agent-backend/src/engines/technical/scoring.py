"""
src/engines/technical/scoring.py
─────────────────────────────────────────────────────────────────────────────
ScoringEngine — converts IndicatorResult into a normalised 0–10 score per
module and an aggregated TechnicalScore.

All scoring logic is deterministic and rule-based (no LLM).
Weights are configurable per indicator module.

V2: Each score function now returns (score, evidence) for explainability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
class ModuleEvidence:
    """Evidence strings per module explaining each score."""
    trend:      list[str] = field(default_factory=list)
    momentum:   list[str] = field(default_factory=list)
    volatility: list[str] = field(default_factory=list)
    volume:     list[str] = field(default_factory=list)
    structure:  list[str] = field(default_factory=list)


@dataclass
class TechnicalScore:
    aggregate: float    # 0–10, weighted
    modules:   ModuleScores
    signal:    Literal["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"]
    strength:  Literal["Strong", "Moderate", "Weak"]
    evidence:  ModuleEvidence = field(default_factory=ModuleEvidence)
    confidence: float = 0.5           # 0–1, inter-module agreement
    strongest_module: str = ""
    weakest_module: str = ""
    confirmation_level: Literal["HIGH", "MEDIUM", "LOW"] = "LOW"


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


def _score_trend(result) -> tuple[float, list[str]]:
    score = STATUS_SCORES.get(result.status, 5.0)
    evidence: list[str] = []

    # Build evidence trail
    if result.price_vs_sma50 == "ABOVE":
        evidence.append(f"Price ABOVE SMA50 (${result.sma_50:.2f})")
    elif result.price_vs_sma50 == "BELOW":
        evidence.append(f"Price BELOW SMA50 (${result.sma_50:.2f})")

    if result.price_vs_sma200 == "ABOVE":
        evidence.append(f"Price ABOVE SMA200 (${result.sma_200:.2f})")
    elif result.price_vs_sma200 == "BELOW":
        evidence.append(f"Price BELOW SMA200 (${result.sma_200:.2f})")

    if result.golden_cross:
        evidence.append("Golden Cross detected (SMA50 > SMA200)")
    elif result.death_cross:
        evidence.append("Death Cross detected (SMA50 < SMA200)")

    if result.macd_crossover == "BULLISH":
        evidence.append(f"MACD bullish crossover (MACD={result.macd_value:.2f} > Signal={result.macd_signal:.2f})")
    elif result.macd_crossover == "BEARISH":
        evidence.append(f"MACD bearish crossover (MACD={result.macd_value:.2f} < Signal={result.macd_signal:.2f})")

    return score, evidence


def _score_momentum(result) -> tuple[float, list[str]]:
    base = STATUS_SCORES.get(result.status, 5.0)
    evidence: list[str] = []

    # RSI evidence
    rsi = result.rsi
    if result.rsi_zone == "OVERSOLD":
        evidence.append(f"RSI oversold at {rsi:.1f} (< 30)")
    elif result.rsi_zone == "OVERBOUGHT":
        evidence.append(f"RSI overbought at {rsi:.1f} (> 70)")
    else:
        evidence.append(f"RSI neutral at {rsi:.1f}")

    # RSI fine-tuning within neutral zone
    if result.rsi_zone == "NEUTRAL":
        if 50 < rsi < 60:
            base += 0.5
            evidence.append("RSI mild bullish bias (50-60)")
        elif 40 < rsi < 50:
            base -= 0.5
            evidence.append("RSI mild bearish bias (40-50)")

    # Stochastic evidence
    if result.stoch_zone == "OVERSOLD":
        evidence.append(f"Stochastic oversold (%K={result.stoch_k:.1f})")
    elif result.stoch_zone == "OVERBOUGHT":
        evidence.append(f"Stochastic overbought (%K={result.stoch_k:.1f})")

    return round(max(0.0, min(10.0, base)), 2), evidence


def _score_volatility(result) -> tuple[float, list[str]]:
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

    evidence: list[str] = [f"Volatility condition: {result.condition} (ATR%={result.atr_pct:.3f})"]

    # BB position adjustment
    bb_adj = {
        "LOWER":      1.5,   # potential bounce
        "LOWER_MID":  0.5,
        "MID":        0.0,
        "UPPER_MID": -0.5,
        "UPPER":     -1.0,   # overbought territory
    }.get(result.bb_position, 0.0)

    if bb_adj != 0:
        evidence.append(f"BB position: {result.bb_position} (adj {bb_adj:+.1f})")
    else:
        evidence.append(f"BB position: {result.bb_position}")

    return round(max(0.0, min(10.0, condition_base + bb_adj)), 2), evidence


def _score_volume(result) -> tuple[float, list[str]]:
    base = {
        "STRONG": 8.0,
        "NORMAL": 5.5,
        "WEAK":   3.0,
    }.get(result.status, 5.0)

    evidence: list[str] = [f"Volume strength: {result.status} ({result.volume_vs_avg:.2f}x avg)"]

    # OBV trend adjustment
    obv_adj = {
        "RISING":  1.0,
        "FLAT":    0.0,
        "FALLING": -1.0,
    }.get(result.obv_trend, 0.0)

    evidence.append(f"OBV trend: {result.obv_trend}")

    return round(max(0.0, min(10.0, base + obv_adj)), 2), evidence


def _score_structure(result) -> tuple[float, list[str]]:
    """Score based on breakout probability, direction, and V2 data."""
    bp = result.breakout_probability   # 0–1.0
    direction = result.breakout_direction
    evidence: list[str] = []

    if direction == "BULLISH":
        base = 5.0 + bp * 5.0        # 5.0 – 10.0
        evidence.append(f"Bullish breakout direction (prob={bp:.0%})")
    elif direction == "BEARISH":
        base = 5.0 - bp * 4.0        # 1.0 – 5.0
        evidence.append(f"Bearish breakout direction (prob={bp:.0%})")
    else:
        base = 4.5 + bp * 1.5        # 4.5 – 6.0 neutral zone
        evidence.append(f"Neutral breakout stance (prob={bp:.0%})")

    # V2: Market structure alignment bonus
    ms = getattr(result, "market_structure", "MIXED")
    if ms == "HH_HL" and direction == "BULLISH":
        base += 1.0   # uptrend structure confirms bullish breakout
        evidence.append("Market structure HH/HL confirms bullish setup")
    elif ms == "LH_LL" and direction == "BEARISH":
        base += 0.5   # downtrend confirmed
        evidence.append("Market structure LH/LL confirms bearish setup")
    elif ms == "LH_LL" and direction == "BULLISH":
        base -= 1.0   # structure conflicts with breakout direction
        evidence.append("WARNING: LH/LL structure conflicts with bullish breakout")

    # V2: Strong level support
    level_str = getattr(result, "level_strength", {})
    if any(v.get("strong", False) for v in level_str.values()):
        base += 0.5   # strong levels add confidence
        evidence.append("Strong S/R levels detected (3+ touches)")

    # V2: Pattern signals
    patterns = getattr(result, "patterns", [])
    if "DOUBLE_BOTTOM" in patterns or "HIGHER_LOWS" in patterns:
        base += 0.5
        bullish_patterns = [p for p in patterns if p in ("DOUBLE_BOTTOM", "HIGHER_LOWS")]
        evidence.append(f"Bullish patterns: {', '.join(bullish_patterns)}")
    if "DOUBLE_TOP" in patterns or "LOWER_HIGHS" in patterns:
        base -= 0.5
        bearish_patterns = [p for p in patterns if p in ("DOUBLE_TOP", "LOWER_HIGHS")]
        evidence.append(f"Bearish patterns: {', '.join(bearish_patterns)}")

    return round(max(0.0, min(10.0, base)), 2), evidence


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


def _compute_confidence(
    modules: ModuleScores,
    signal: str,
) -> tuple[float, str]:
    """
    Compute inter-module agreement as a confidence metric (0–1).

    - If most modules align with the composite signal direction → HIGH
    - Partial alignment → MEDIUM
    - Disagreement → LOW

    Returns (confidence_float, confirmation_level_str).
    """
    bullish_signal = signal in ("STRONG_BUY", "BUY")
    bearish_signal = signal in ("STRONG_SELL", "SELL")

    scores = {
        "trend": modules.trend,
        "momentum": modules.momentum,
        "volatility": modules.volatility,
        "volume": modules.volume,
        "structure": modules.structure,
    }

    agreeing = 0
    total = 5
    for mod_score in scores.values():
        if bullish_signal and mod_score >= 6.0:
            agreeing += 1
        elif bearish_signal and mod_score <= 4.0:
            agreeing += 1
        elif not bullish_signal and not bearish_signal and 4.0 <= mod_score <= 6.0:
            agreeing += 1

    confidence = round(agreeing / total, 2)

    if agreeing >= 4:
        level = "HIGH"
    elif agreeing >= 3:
        level = "MEDIUM"
    else:
        level = "LOW"

    return confidence, level


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

        # Compute scores with evidence
        trend_score, trend_ev = _score_trend(result.trend)
        momentum_score, momentum_ev = _score_momentum(result.momentum)
        volatility_score, volatility_ev = _score_volatility(result.volatility)
        volume_score, volume_ev = _score_volume(result.volume)
        structure_score, structure_ev = _score_structure(result.structure)

        modules = ModuleScores(
            trend      = trend_score,
            momentum   = momentum_score,
            volatility = volatility_score,
            volume     = volume_score,
            structure  = structure_score,
        )

        evidence = ModuleEvidence(
            trend      = trend_ev,
            momentum   = momentum_ev,
            volatility = volatility_ev,
            volume     = volume_ev,
            structure  = structure_ev,
        )

        aggregate = (
            modules.trend      * w["trend"]      +
            modules.momentum   * w["momentum"]   +
            modules.volatility * w["volatility"] +
            modules.volume     * w["volume"]     +
            modules.structure  * w["structure"]
        ) / sum(w.values())

        aggregate = round(aggregate, 2)
        signal = _derive_signal(aggregate)

        # Compute confidence and find strongest/weakest modules
        confidence, confirmation_level = _compute_confidence(modules, signal)

        score_map = {
            "trend": modules.trend,
            "momentum": modules.momentum,
            "volatility": modules.volatility,
            "volume": modules.volume,
            "structure": modules.structure,
        }
        strongest = max(score_map, key=score_map.get)
        weakest = min(score_map, key=score_map.get)

        return TechnicalScore(
            aggregate = aggregate,
            modules   = modules,
            signal    = signal,
            strength  = _derive_strength(aggregate),
            evidence  = evidence,
            confidence = confidence,
            strongest_module = strongest,
            weakest_module = weakest,
            confirmation_level = confirmation_level,
        )
