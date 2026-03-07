"""
src/engines/execution/fill_model.py
─────────────────────────────────────────────────────────────────────────────
FillModel — Models order fill behavior: partial fills, fill rate,
and execution timing for realistic backtest simulation.
"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger("365advisers.execution.fill_model")


class FillModel:
    """Simulates realistic order fill behavior."""

    def __init__(
        self,
        target_participation: float = 0.05,
        fill_probability_base: float = 0.95,
    ) -> None:
        self.target_participation = target_participation
        self.fill_probability_base = fill_probability_base

    def estimate_fill(
        self,
        order_shares: int,
        adv: float,
        execution_urgency: str = "normal",
    ) -> dict:
        """Estimate fill rate and time for an order.

        Args:
            order_shares: Number of shares to fill.
            adv: Average daily volume.
            execution_urgency: "low" | "normal" | "high"

        Returns:
            Fill estimate with fill rate, time, and partial fill info.
        """
        if adv <= 0:
            return {"error": "Invalid ADV", "fill_rate": 0}

        participation = order_shares / adv
        urgency_multiplier = {
            "low": 0.5,
            "normal": 1.0,
            "high": 2.0,
        }.get(execution_urgency, 1.0)

        # Adjust participation for urgency
        effective_participation = min(
            participation * urgency_multiplier,
            self.target_participation * 3,
        )

        # Fill probability decreases as participation increases
        fill_prob = self.fill_probability_base * math.exp(
            -5 * max(0, effective_participation - self.target_participation)
        )
        fill_prob = max(0.1, min(fill_prob, 1.0))

        # Estimated fill time (days)
        fill_days = participation / self.target_participation
        fill_days = max(0.1, min(fill_days, 10.0))

        # Partial fill estimate
        if participation > self.target_participation:
            expected_fill_pct = min(
                1.0, self.target_participation / participation
            )
        else:
            expected_fill_pct = 1.0

        return {
            "order_shares": order_shares,
            "participation_rate": round(participation, 6),
            "execution_urgency": execution_urgency,
            "fill_probability": round(fill_prob, 4),
            "estimated_fill_days": round(fill_days, 2),
            "expected_fill_pct": round(expected_fill_pct, 4),
            "expected_filled_shares": round(order_shares * expected_fill_pct),
            "exceeds_target_participation": participation > self.target_participation,
        }

    def compute_vwap_slippage(
        self,
        intraday_volume_profile: list[float] | None = None,
        execution_window_pct: float = 0.5,
    ) -> float:
        """Estimate VWAP execution slippage in bps.

        Uses a default U-shaped volume profile if none provided.

        Args:
            intraday_volume_profile: Normalized volume distribution (24 bins).
            execution_window_pct: Fraction of trading day for execution.

        Returns:
            Estimated slippage in bps.
        """
        if not intraday_volume_profile:
            # Default U-shaped profile (open/close heavier)
            intraday_volume_profile = [
                0.08, 0.06, 0.05, 0.04, 0.04, 0.03, 0.03, 0.03,
                0.03, 0.03, 0.03, 0.03, 0.04, 0.04, 0.04, 0.04,
                0.04, 0.04, 0.05, 0.05, 0.05, 0.05, 0.06, 0.08,
            ]

        n_bins = len(intraday_volume_profile)
        exec_bins = max(1, int(n_bins * execution_window_pct))

        # Uniform execution across window
        uniform_weight = 1.0 / exec_bins
        volume_weight = sum(intraday_volume_profile[:exec_bins]) / exec_bins

        # Slippage increases when executing in low-volume periods
        slippage_factor = uniform_weight / max(volume_weight, 0.001)
        slippage_bps = 1.5 * slippage_factor  # Base 1.5 bps at perfect VWAP

        return round(min(slippage_bps, 20.0), 2)
