"""
src/engines/long_short/borrow_cost.py
──────────────────────────────────────────────────────────────────────────────
Borrow-fee estimation model for short positions.

Uses a tiered model based on market-cap, average daily volume, and
estimated short interest to approximate borrow difficulty and cost.
"""

from __future__ import annotations

import math

from src.engines.long_short.models import BorrowCostEstimate, BorrowTier


class BorrowCostEstimator:
    """
    Estimates the annualised borrow cost for shorting a given equity.

    The model uses three proxy inputs (market cap, ADV, short interest %)
    to classify the stock into a borrow tier and assign a rate.

    Tier thresholds (annualised):
        General Collateral  ≤ 0.30%    (large-cap, liquid)
        Easy-to-Borrow      0.30–1.0%  (mid-cap, moderate SI)
        Hard-to-Borrow      1.0–5.0%   (small-cap or high SI)
        Special             > 5.0%      (heavily shorted / low float)
    """

    # ── Default rates per tier (annualised, as decimals) ─────────────────
    TIER_RATES: dict[BorrowTier, float] = {
        BorrowTier.GENERAL_COLLATERAL: 0.0025,   # 0.25%
        BorrowTier.EASY_TO_BORROW: 0.0065,       # 0.65%
        BorrowTier.HARD_TO_BORROW: 0.030,         # 3.0%
        BorrowTier.SPECIAL: 0.080,                 # 8.0%
    }

    # ── Classification thresholds ────────────────────────────────────────
    LARGE_CAP_THRESHOLD = 10_000_000_000      # $10 B
    MID_CAP_THRESHOLD = 2_000_000_000         # $2 B
    HIGH_ADV_THRESHOLD = 5_000_000            # 5 M shares/day
    LOW_ADV_THRESHOLD = 500_000               # 500 K shares/day
    HIGH_SHORT_INTEREST = 0.20                # 20% of float
    VERY_HIGH_SHORT_INTEREST = 0.40           # 40% of float

    @classmethod
    def estimate(
        cls,
        ticker: str,
        market_cap: float | None = None,
        avg_daily_volume: float | None = None,
        short_interest_pct: float | None = None,
    ) -> BorrowCostEstimate:
        """
        Estimate borrow cost based on available data.

        Args:
            ticker: Stock ticker symbol.
            market_cap: Market capitalisation in USD. None → assume mid-cap.
            avg_daily_volume: 20-day average daily volume (shares). None → assume moderate.
            short_interest_pct: Short interest as fraction of float (0.0–1.0). None → assume low.

        Returns:
            BorrowCostEstimate with tier classification and rate.
        """
        mcap = market_cap or 5_000_000_000  # default mid-cap
        adv = avg_daily_volume or 2_000_000
        si = short_interest_pct or 0.05

        tier = cls._classify(mcap, adv, si)
        rate = cls.TIER_RATES[tier]

        # Adjust rate within tier based on short interest intensity
        if si > cls.HIGH_SHORT_INTEREST:
            intensity = min(si / cls.VERY_HIGH_SHORT_INTEREST, 2.0)
            rate *= (1.0 + 0.5 * intensity)

        daily_bps = (rate / 252.0) * 10_000  # convert to daily bps

        note = cls._availability_note(tier, si)

        return BorrowCostEstimate(
            ticker=ticker,
            annual_rate=round(rate, 6),
            tier=tier,
            estimated_daily_cost_bps=round(daily_bps, 4),
            availability_note=note,
        )

    @classmethod
    def _classify(cls, market_cap: float, adv: float, si: float) -> BorrowTier:
        """Classify into borrow tier based on fundamentals."""
        # Special: very high short interest or very low liquidity
        if si >= cls.VERY_HIGH_SHORT_INTEREST:
            return BorrowTier.SPECIAL
        if adv < cls.LOW_ADV_THRESHOLD and si > cls.HIGH_SHORT_INTEREST:
            return BorrowTier.SPECIAL

        # Hard-to-Borrow: high SI or small-cap with limited volume
        if si >= cls.HIGH_SHORT_INTEREST:
            return BorrowTier.HARD_TO_BORROW
        if market_cap < cls.MID_CAP_THRESHOLD and adv < cls.LOW_ADV_THRESHOLD:
            return BorrowTier.HARD_TO_BORROW

        # General Collateral: large-cap + liquid + low SI
        if market_cap >= cls.LARGE_CAP_THRESHOLD and adv >= cls.HIGH_ADV_THRESHOLD:
            return BorrowTier.GENERAL_COLLATERAL

        # Everything else: Easy-to-Borrow
        return BorrowTier.EASY_TO_BORROW

    @classmethod
    def _availability_note(cls, tier: BorrowTier, si: float) -> str:
        """Generate a human-readable availability note."""
        notes = {
            BorrowTier.GENERAL_COLLATERAL: "Widely available; minimal cost impact.",
            BorrowTier.EASY_TO_BORROW: "Generally available; standard institutional rate.",
            BorrowTier.HARD_TO_BORROW: f"Limited availability (SI: {si:.1%}). Rate may fluctuate.",
            BorrowTier.SPECIAL: f"Heavily restricted (SI: {si:.1%}). Locate required; rate volatile.",
        }
        return notes[tier]
