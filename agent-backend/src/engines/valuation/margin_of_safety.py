"""
src/engines/valuation/margin_of_safety.py
──────────────────────────────────────────────────────────────────────────────
Margin of Safety Calculator.

Implements Benjamin Graham / Warren Buffett-style margin of safety
assessment and the Graham Number.
"""

from __future__ import annotations

import logging
import math

from src.engines.valuation.models import (
    MarginOfSafety,
    ValuationVerdict,
)

logger = logging.getLogger("365advisers.valuation.margin_of_safety")


class MarginCalculator:
    """
    Calculate margin of safety and Graham Number.

    Thresholds:
        Margin > 25%  →  UNDERVALUED
        Margin < -10% →  OVERVALUED
        Otherwise     →  FAIR_VALUE
    """

    UNDERVALUED_THRESHOLD = 25.0   # %
    OVERVALUED_THRESHOLD = -10.0   # %

    @classmethod
    def calculate(
        cls,
        ticker: str,
        fair_value: float,
        current_price: float,
        eps: float | None = None,
        book_value_per_share: float | None = None,
    ) -> MarginOfSafety:
        """
        Calculate margin of safety.

        Margin % = (fair_value - current_price) / fair_value × 100

        Positive margin = stock is cheap vs. fair value.
        Negative margin = stock is expensive vs. fair value.
        """
        if fair_value <= 0 or current_price <= 0:
            return MarginOfSafety(
                ticker=ticker,
                fair_value=fair_value,
                current_price=current_price,
                verdict=ValuationVerdict.FAIR_VALUE,
            )

        margin_pct = ((fair_value - current_price) / fair_value) * 100

        # Verdict
        if margin_pct >= cls.UNDERVALUED_THRESHOLD:
            verdict = ValuationVerdict.UNDERVALUED
        elif margin_pct <= cls.OVERVALUED_THRESHOLD:
            verdict = ValuationVerdict.OVERVALUED
        else:
            verdict = ValuationVerdict.FAIR_VALUE

        # Graham Number
        graham = cls.graham_number(eps, book_value_per_share)

        return MarginOfSafety(
            ticker=ticker,
            fair_value=round(fair_value, 2),
            current_price=round(current_price, 2),
            margin_pct=round(margin_pct, 2),
            verdict=verdict,
            graham_number=round(graham, 2) if graham else None,
        )

    @staticmethod
    def graham_number(
        eps: float | None,
        book_value_per_share: float | None,
    ) -> float | None:
        """
        Calculate the Graham Number.

        Graham Number = √(22.5 × EPS × Book Value per Share)

        Returns None if inputs are invalid (negative or None).
        """
        if eps is None or book_value_per_share is None:
            return None
        if eps <= 0 or book_value_per_share <= 0:
            return None

        return math.sqrt(22.5 * eps * book_value_per_share)
