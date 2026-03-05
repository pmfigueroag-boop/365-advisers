"""
src/engines/portfolio/risk_budget.py
──────────────────────────────────────────────────────────────────────────────
Risk Budget Engine — enforces portfolio-level risk constraints.

Extracted from portfolio_builder.py and enhanced with configurable limits
and per-constraint violation tracking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("365advisers.portfolio.risk_budget")


@dataclass
class RiskLimits:
    """Configurable risk constraints for portfolio construction."""
    max_single_position: float = 10.0       # % — single position cap
    max_sector_exposure: float = 25.0       # % — sector concentration cap
    max_high_volatility: float = 15.0       # % — high-vol bucket cap
    max_total_allocation: float = 100.0     # % — total capital cap
    min_position_weight: float = 0.5        # % — positions below this are dropped


@dataclass
class RiskCheckResult:
    """Result of a risk budget evaluation."""
    passed: bool = True
    violations: list[str] = field(default_factory=list)
    positions: list[dict] = field(default_factory=list)
    sector_exposures: dict[str, float] = field(default_factory=dict)
    total_allocation: float = 0.0


class RiskBudgetEngine:
    """
    Enforces portfolio-level risk constraints.

    Constraints:
      1. Single position cap (default 10%)
      2. Sector concentration cap (default 25%)
      3. Total allocation cap (100%)
      4. Minimum position size filter
    """

    def __init__(self, limits: RiskLimits | None = None):
        self.limits = limits or RiskLimits()

    def evaluate(self, positions: list[dict]) -> RiskCheckResult:
        """
        Evaluate and enforce risk limits on a list of positions.

        Args:
            positions: List of dicts with keys: ticker, target_weight, sector, role, volatility_atr

        Returns:
            RiskCheckResult with adjusted positions and violations.
        """
        result = RiskCheckResult()
        working = [dict(p) for p in positions]  # defensive copy

        # ── Step 1: Cap individual positions ──────────────────────────────
        for p in working:
            if p["target_weight"] > self.limits.max_single_position:
                result.violations.append(
                    f"{p['ticker']}: position capped at {self.limits.max_single_position}% "
                    f"(was {p['target_weight']:.1f}%)"
                )
                p["target_weight"] = self.limits.max_single_position

        # ── Step 2: Drop tiny positions ───────────────────────────────────
        working = [p for p in working if p["target_weight"] >= self.limits.min_position_weight]

        # ── Step 3: Total allocation cap ──────────────────────────────────
        total = sum(p["target_weight"] for p in working)
        if total > self.limits.max_total_allocation:
            scale = self.limits.max_total_allocation / total
            result.violations.append(
                f"Portfolio exceeded {self.limits.max_total_allocation}% "
                f"(was {total:.1f}%). Pro-rata scale applied ({scale:.2f}x)."
            )
            for p in working:
                p["target_weight"] *= scale

        # ── Step 4: Sector concentration limits ───────────────────────────
        sector_map: dict[str, float] = {}
        for p in working:
            sec = p.get("sector", "Unknown")
            sector_map[sec] = sector_map.get(sec, 0.0) + p["target_weight"]

        for sec, exposure in list(sector_map.items()):
            if exposure > self.limits.max_sector_exposure:
                scale = self.limits.max_sector_exposure / exposure
                result.violations.append(
                    f"Sector {sec} exceeded {self.limits.max_sector_exposure}% "
                    f"(was {exposure:.1f}%). Trimmed."
                )
                sector_map[sec] = self.limits.max_sector_exposure
                for p in working:
                    if p.get("sector") == sec:
                        p["target_weight"] *= scale

        # ── Finalize ──────────────────────────────────────────────────────
        for p in working:
            p["target_weight"] = round(p["target_weight"], 2)

        result.passed = len(result.violations) == 0
        result.positions = working
        result.sector_exposures = {k: round(v, 2) for k, v in sector_map.items() if v > 0}
        result.total_allocation = round(sum(p["target_weight"] for p in working), 2)

        return result
