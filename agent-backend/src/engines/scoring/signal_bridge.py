"""
src/engines/scoring/signal_bridge.py
──────────────────────────────────────────────────────────────────────────────
Bridge between the Alpha Signals Library and the 12-factor Opportunity Model.

Maps category-level signal evaluations to scoring adjustments for each of
the 4 dimensions (business_quality, valuation, financial_strength,
market_behavior), providing richer inputs than agent-only estimates.
"""

from __future__ import annotations

from src.engines.alpha_signals.models import SignalProfile, CategoryScore


# Signal → Factor mapping
# Each signal category maps to specific 12-factor dimensions with a weight
_CATEGORY_FACTOR_MAP = {
    # Category → list of (factor_name, dimension, weight_contribution)
    "value": [
        ("relative_valuation", "valuation", 0.4),
        ("intrinsic_value_gap", "valuation", 0.3),
        ("fcf_yield", "valuation", 0.3),
    ],
    "quality": [
        ("competitive_moat", "business_quality", 0.35),
        ("growth_quality", "financial_strength", 0.30),
        ("earnings_stability", "financial_strength", 0.35),
    ],
    "momentum": [
        ("trend_strength", "market_behavior", 0.5),
        ("momentum", "market_behavior", 0.5),
    ],
    "volatility": [
        ("trend_strength", "market_behavior", 0.3),
        ("momentum", "market_behavior", 0.3),
        ("balance_sheet_strength", "financial_strength", 0.4),
    ],
    "flow": [
        ("institutional_flow", "market_behavior", 0.7),
        ("momentum", "market_behavior", 0.3),
    ],
    "event": [
        ("growth_quality", "financial_strength", 0.3),
        ("industry_structure", "business_quality", 0.3),
        ("management_capital_allocation", "business_quality", 0.4),
    ],
    "growth": [
        ("growth_quality", "financial_strength", 0.4),
        ("earnings_stability", "financial_strength", 0.3),
        ("competitive_moat", "business_quality", 0.3),
    ],
    "macro": [
        ("trend_strength", "market_behavior", 0.25),
        ("momentum", "market_behavior", 0.25),
        ("balance_sheet_strength", "financial_strength", 0.25),
        ("relative_valuation", "valuation", 0.25),
    ],
}


def compute_signal_factor_adjustments(
    profile: SignalProfile,
) -> dict[str, float]:
    """
    Compute per-factor score adjustments (0–10 scale) derived from the
    Alpha Signal profile.

    Returns a dict of { factor_name: score }.  The scores are modifiers
    that should be blended with existing factor scores from the scoring
    engine.

    Factors that have no relevant signal data are not included.
    """
    adjustments: dict[str, list[float]] = {}

    for cat_key, cat_score in profile.category_summary.items():
        mappings = _CATEGORY_FACTOR_MAP.get(cat_key, [])
        if not mappings or cat_score.fired == 0:
            continue

        # Convert composite_strength (0–1) to 0–10 scale
        raw_score = _strength_to_score(cat_score)

        for factor_name, _dimension, weight in mappings:
            weighted_score = raw_score * weight
            adjustments.setdefault(factor_name, []).append(weighted_score)

    # Aggregate weighted contributions per factor
    result: dict[str, float] = {}
    for factor_name, weighted_scores in adjustments.items():
        result[factor_name] = round(sum(weighted_scores), 2)

    return result


def _strength_to_score(cat_score: CategoryScore) -> float:
    """
    Convert a CategoryScore into a 0–10 score value.

    Uses composite_strength (0–1) as the primary input:
      - 0.0 → 5.0 (neutral)
      - 1.0 → 10.0 (maximum positive signal)

    Applies a confidence multiplier:
      - HIGH: full score
      - MEDIUM: 80% of delta from neutral
      - LOW: 50% of delta from neutral
    """
    base = cat_score.composite_strength * 10.0  # 0–10

    # Shift so that 5.0 is neutral, and signal enhances above
    # Score: 5 + (base - 5) * confidence_mult
    neutral = 5.0
    delta = base - neutral

    conf_mult = {
        "high": 1.0,
        "medium": 0.8,
        "low": 0.5,
    }.get(cat_score.confidence.value, 0.5)

    return round(min(10.0, max(0.0, neutral + delta * conf_mult)), 2)


def blend_signal_adjustments(
    existing_factors: dict[str, float],
    signal_adjustments: dict[str, float],
    alpha_weight: float = 0.3,
) -> dict[str, float]:
    """
    Blend signal-derived factor adjustments with existing agent-based scores.

    Parameters
    ----------
    existing_factors : dict
        Current 12-factor scores from the OpportunityModel.
    signal_adjustments : dict
        Per-factor adjustments from compute_signal_factor_adjustments().
    alpha_weight : float
        Weight given to the signal adjustments (0–1).
        Default 0.3 = 30% signals, 70% original.

    Returns
    -------
    dict
        Blended factor scores.
    """
    blended = dict(existing_factors)
    agent_weight = 1.0 - alpha_weight

    for factor_name, signal_score in signal_adjustments.items():
        if factor_name in blended:
            original = blended[factor_name]
            blended[factor_name] = round(
                original * agent_weight + signal_score * alpha_weight, 2
            )

    return blended


# ═════════════════════════════════════════════════════════════════════════════
# CASE-aware bridge (uses CompositeAlphaResult instead of raw SignalProfile)
# ═════════════════════════════════════════════════════════════════════════════

def compute_case_factor_adjustments(
    case_result: "CompositeAlphaResult",
) -> dict[str, float]:
    """
    Compute per-factor score adjustments from a CompositeAlphaResult.

    Uses the richer 0–100 category subscores instead of the raw 0–1
    composite_strength.  Conflict-aware: reduces contributions from
    conflicted categories.

    Parameters
    ----------
    case_result : CompositeAlphaResult
        Output from the Composite Alpha Score Engine.

    Returns
    -------
    dict[str, float]
        Per-factor adjustments on the 0–10 scale.
    """
    from src.engines.composite_alpha.models import CompositeAlphaResult  # noqa: F811

    adjustments: dict[str, list[float]] = {}

    for cat_key, subscore in case_result.subscores.items():
        mappings = _CATEGORY_FACTOR_MAP.get(cat_key, [])
        if not mappings or subscore.fired == 0:
            continue

        # Convert 0–100 subscore to 0–10 scale
        raw_score = subscore.score / 10.0

        # Reduce contribution if category has internal conflicts
        if subscore.conflict_detected:
            raw_score *= subscore.conflict_penalty

        for factor_name, _dimension, weight in mappings:
            weighted_score = raw_score * weight
            adjustments.setdefault(factor_name, []).append(weighted_score)

    result: dict[str, float] = {}
    for factor_name, weighted_scores in adjustments.items():
        result[factor_name] = round(sum(weighted_scores), 2)

    return result


def compute_case_alpha_weight(
    case_result: "CompositeAlphaResult",
    base_weight: float = 0.3,
) -> float:
    """
    Dynamically adjust the alpha_weight based on signal environment.

    Stronger environments → higher alpha influence on the 12-factor model.

    Parameters
    ----------
    case_result : CompositeAlphaResult
        Output from the Composite Alpha Score Engine.
    base_weight : float
        Default alpha weight (0.3).

    Returns
    -------
    float
        Adjusted alpha weight (0.2 – 0.5).
    """
    from src.engines.composite_alpha.models import SignalEnvironment

    weight_map = {
        SignalEnvironment.VERY_STRONG: 0.50,
        SignalEnvironment.STRONG: 0.40,
        SignalEnvironment.NEUTRAL: base_weight,
        SignalEnvironment.WEAK: 0.25,
        SignalEnvironment.NEGATIVE: 0.20,
    }

    return weight_map.get(case_result.signal_environment, base_weight)
