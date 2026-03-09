"""
src/engines/long_short/exposure.py
──────────────────────────────────────────────────────────────────────────────
Exposure calculator for Long/Short portfolios.

Computes gross, net, and beta-adjusted exposure from position lists.
"""

from __future__ import annotations

from src.engines.long_short.models import (
    ExposureMetrics,
    LongShortPosition,
    PositionSide,
)


class ExposureCalculator:
    """Stateless calculator for L/S portfolio exposure metrics."""

    @staticmethod
    def calculate(
        long_positions: list[LongShortPosition],
        short_positions: list[LongShortPosition],
    ) -> ExposureMetrics:
        """
        Calculate aggregate exposure metrics.

        Args:
            long_positions: List of long leg positions.
            short_positions: List of short leg positions.

        Returns:
            ExposureMetrics with gross, net, beta, and leverage figures.
        """
        long_wt = sum(p.weight for p in long_positions)
        short_wt = sum(p.weight for p in short_positions)

        gross = long_wt + short_wt
        net = long_wt - short_wt

        # Beta exposure: Σ(weight × beta) for longs minus Σ(weight × beta) for shorts
        beta_long = sum(p.weight * p.beta for p in long_positions)
        beta_short = sum(p.weight * p.beta for p in short_positions)
        beta_exposure = beta_long - beta_short

        return ExposureMetrics(
            gross_exposure=round(gross, 6),
            net_exposure=round(net, 6),
            long_exposure=round(long_wt, 6),
            short_exposure=round(short_wt, 6),
            beta_exposure=round(beta_exposure, 6),
            leverage_ratio=round(gross, 6),  # gross exposure IS the leverage ratio
            long_count=len(long_positions),
            short_count=len(short_positions),
        )

    @staticmethod
    def is_market_neutral(exposure: ExposureMetrics, threshold: float = 0.10) -> bool:
        """Check if the portfolio is approximately market-neutral."""
        return abs(exposure.beta_exposure) <= threshold

    @staticmethod
    def is_dollar_neutral(exposure: ExposureMetrics, threshold: float = 0.05) -> bool:
        """Check if the portfolio is approximately dollar-neutral."""
        return abs(exposure.net_exposure) <= threshold
