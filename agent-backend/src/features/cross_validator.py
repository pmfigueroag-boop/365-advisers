"""
src/features/cross_validator.py
──────────────────────────────────────────────────────────────────────────────
Cross-validation between data sources.

Compares key financial metrics from multiple providers (e.g. yfinance vs Alpha
Vantage) and computes a data_confidence_score (0–1) that reflects agreement.
When sources diverge significantly (>10%), the confidence is lowered.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("365advisers.features.cross_validator")


@dataclass
class CrossValidationResult:
    """Agreement analysis between two data sources."""
    total_fields_compared: int = 0
    fields_agree: int = 0       # Within 10% threshold
    fields_diverge: int = 0     # Diverge >10%
    fields_missing: int = 0     # One source has None
    divergent_fields: list[dict] = field(default_factory=list)
    data_confidence: float = 1.0  # 0–1, 1 = perfect agreement


def cross_validate_fundamentals(
    primary: dict[str, float | None],
    secondary: dict[str, float | None],
    primary_name: str = "yfinance",
    secondary_name: str = "alpha_vantage",
    tolerance: float = 0.10,
) -> CrossValidationResult:
    """
    Compare key financial metrics between two data sources.

    Parameters
    ----------
    primary : dict
        Metrics from primary source (field_name → value).
    secondary : dict
        Metrics from secondary source (same field names).
    tolerance : float
        Max allowed relative deviation (default 10%).

    Returns
    -------
    CrossValidationResult
        Agreement analysis with confidence score.
    """
    result = CrossValidationResult()

    # Fields to compare (only compare if both sources have the field)
    common_fields = set(primary.keys()) & set(secondary.keys())

    for field_name in common_fields:
        val_a = primary.get(field_name)
        val_b = secondary.get(field_name)

        if val_a is None or val_b is None:
            result.fields_missing += 1
            continue

        result.total_fields_compared += 1

        # Compute relative deviation
        reference = max(abs(val_a), abs(val_b), 1e-10)
        deviation = abs(val_a - val_b) / reference

        if deviation <= tolerance:
            result.fields_agree += 1
        else:
            result.fields_diverge += 1
            result.divergent_fields.append({
                "field": field_name,
                "primary_value": round(val_a, 4),
                "secondary_value": round(val_b, 4),
                "deviation_pct": round(deviation * 100, 1),
                "primary_source": primary_name,
                "secondary_source": secondary_name,
            })

    # Compute confidence: ratio of agreeing fields, with penalty for divergence
    if result.total_fields_compared > 0:
        agreement_ratio = result.fields_agree / result.total_fields_compared
        # Harsh penalty: each divergent field costs 15% confidence
        divergence_penalty = min(0.5, result.fields_diverge * 0.15)
        result.data_confidence = round(
            max(0.3, agreement_ratio - divergence_penalty), 3
        )
    else:
        # No fields to compare — cannot validate, keep 80% confidence
        result.data_confidence = 0.8

    if result.fields_diverge > 0:
        logger.warning(
            f"CROSS-VALIDATE: {result.fields_diverge} fields diverge "
            f"({', '.join(d['field'] for d in result.divergent_fields)}). "
            f"confidence={result.data_confidence}"
        )

    return result
