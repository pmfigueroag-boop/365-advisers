"""
src/engines/long_short/engine.py
──────────────────────────────────────────────────────────────────────────────
Long/Short Portfolio Construction Engine.

Constructs a hedged portfolio from separate long and short candidate lists,
applies volatility-parity sizing to each leg, and enforces exposure
constraints (gross, net, beta).
"""

from __future__ import annotations

import logging
from typing import Any

from src.engines.long_short.models import (
    LongShortPosition,
    LongShortPortfolio,
    LongShortResult,
    ExposureMetrics,
    PositionSide,
)
from src.engines.long_short.exposure import ExposureCalculator
from src.engines.long_short.borrow_cost import BorrowCostEstimator

logger = logging.getLogger("365advisers.long_short")


class LongShortEngine:
    """
    Constructs a Long/Short portfolio from candidate lists.

    Default constraints (overridable):
        max_gross_exposure  = 2.00  (200%)
        max_net_exposure    = 0.30  (±30%)
        max_single_position = 0.10  (10%)
        target_beta         = 0.0   (market-neutral target)
    """

    DEFAULT_MAX_GROSS = 2.0
    DEFAULT_MAX_NET = 0.30
    DEFAULT_MAX_SINGLE = 0.10
    DEFAULT_TARGET_BETA = 0.0

    @classmethod
    def construct(
        cls,
        long_candidates: list[dict[str, Any]],
        short_candidates: list[dict[str, Any]],
        *,
        max_gross_exposure: float = DEFAULT_MAX_GROSS,
        max_net_exposure: float = DEFAULT_MAX_NET,
        max_single_position: float = DEFAULT_MAX_SINGLE,
        target_beta: float | None = DEFAULT_TARGET_BETA,
    ) -> LongShortResult:
        """
        Construct a Long/Short portfolio from raw candidate dicts.

        Each candidate dict should contain:
            ticker: str
            weight: float          (raw conviction weight, 0.0–1.0)
            beta: float            (optional, default 1.0)
            sector: str            (optional)
            volatility_atr: float  (optional, default 2.0)
            market_cap: float      (optional, for borrow cost)
            avg_volume: float      (optional, for borrow cost)
            short_interest: float  (optional, for borrow cost)

        Returns:
            LongShortResult with constructed portfolio, exposure, and constraints.
        """
        constraints: list[str] = []
        violations: list[str] = []

        # ── 1. Parse candidates into typed positions ─────────────────────
        long_positions = cls._parse_candidates(long_candidates, PositionSide.LONG)
        short_positions = cls._parse_candidates(short_candidates, PositionSide.SHORT)

        if not long_positions and not short_positions:
            return LongShortResult(
                violations=["No valid candidates provided for either leg."],
            )

        # ── 2. Cap individual positions ──────────────────────────────────
        for pos in long_positions + short_positions:
            if pos.weight > max_single_position:
                constraints.append(
                    f"{pos.ticker} ({pos.side.value}) capped: "
                    f"{pos.weight:.2%} → {max_single_position:.2%}"
                )
                pos.weight = max_single_position

        # ── 3. Apply volatility parity within each leg ───────────────────
        cls._apply_vol_parity(long_positions)
        cls._apply_vol_parity(short_positions)

        # ── 4. Estimate borrow costs for short leg ───────────────────────
        total_borrow_bps = 0.0
        for pos in short_positions:
            estimate = BorrowCostEstimator.estimate(
                ticker=pos.ticker,
                # pass through market_cap etc. if available (stored in metadata)
            )
            pos.borrow_rate = estimate.annual_rate
            total_borrow_bps += estimate.estimated_daily_cost_bps * pos.weight

        # ── 5. Calculate initial exposure ────────────────────────────────
        exposure = ExposureCalculator.calculate(long_positions, short_positions)

        # ── 6. Enforce gross exposure limit ──────────────────────────────
        if exposure.gross_exposure > max_gross_exposure:
            scale = max_gross_exposure / exposure.gross_exposure
            for pos in long_positions + short_positions:
                pos.weight *= scale
            constraints.append(
                f"Gross exposure scaled: {exposure.gross_exposure:.2%} → "
                f"{max_gross_exposure:.2%} (scale: {scale:.4f})"
            )
            exposure = ExposureCalculator.calculate(long_positions, short_positions)

        # ── 7. Enforce net exposure limit ────────────────────────────────
        if abs(exposure.net_exposure) > max_net_exposure:
            violations.append(
                f"Net exposure {exposure.net_exposure:+.2%} exceeds "
                f"±{max_net_exposure:.2%} limit. Consider rebalancing legs."
            )

        # ── 8. Report beta neutrality ────────────────────────────────────
        if target_beta is not None and abs(exposure.beta_exposure) > 0.15:
            violations.append(
                f"Beta exposure {exposure.beta_exposure:+.4f} exceeds "
                f"neutral threshold. Portfolio is NOT market-neutral."
            )

        # ── 9. Assemble result ───────────────────────────────────────────
        portfolio = LongShortPortfolio(
            long_positions=long_positions,
            short_positions=short_positions,
            exposure=exposure,
            total_borrow_cost_annual_bps=round(total_borrow_bps * 252, 2),
        )

        logger.info(
            "L/S portfolio: %d long / %d short | Gross: %.2f%% | Net: %+.2f%% | Beta: %+.4f",
            len(long_positions),
            len(short_positions),
            exposure.gross_exposure * 100,
            exposure.net_exposure * 100,
            exposure.beta_exposure,
        )

        return LongShortResult(
            portfolio=portfolio,
            exposure=exposure,
            constraints_applied=constraints,
            violations=violations,
        )

    # ── Internal helpers ─────────────────────────────────────────────────

    @staticmethod
    def _parse_candidates(
        candidates: list[dict[str, Any]],
        side: PositionSide,
    ) -> list[LongShortPosition]:
        """Convert raw dicts into typed LongShortPosition instances."""
        positions: list[LongShortPosition] = []
        for c in candidates:
            ticker = c.get("ticker")
            weight = c.get("weight", 0.0)
            if not ticker or weight <= 0:
                continue
            positions.append(LongShortPosition(
                ticker=ticker,
                side=side,
                weight=min(weight, 1.0),
                beta=c.get("beta", 1.0),
                sector=c.get("sector", "Unknown"),
                volatility_atr=c.get("volatility_atr", 2.0),
                entry_price=c.get("entry_price"),
                current_price=c.get("current_price"),
            ))
        return positions

    @staticmethod
    def _apply_vol_parity(positions: list[LongShortPosition]) -> None:
        """
        Equalise risk contribution within a leg using inverse-ATR weighting.
        Preserves the aggregate weight sum of the leg.
        """
        if not positions:
            return

        original_sum = sum(p.weight for p in positions)
        if original_sum <= 0:
            return

        raw = []
        for p in positions:
            atr = max(p.volatility_atr, 0.5)
            raw.append(p.weight / atr)

        raw_sum = sum(raw)
        if raw_sum <= 0:
            return

        for i, p in enumerate(positions):
            p.weight = (raw[i] / raw_sum) * original_sum
