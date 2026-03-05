"""
src/engines/portfolio/engine.py
──────────────────────────────────────────────────────────────────────────────
PortfolioEngine facade — entry point for portfolio construction.

Orchestrates: Classification → Volatility Parity → Risk Budget → Output.
Optionally: Rebalance against current state.
"""

from __future__ import annotations

import logging
from dataclasses import asdict

from src.engines.portfolio.portfolio_builder import PortfolioConstructionModel
from src.engines.portfolio.risk_budget import RiskBudgetEngine, RiskLimits, RiskCheckResult
from src.engines.portfolio.rebalancer import Rebalancer, RebalanceResult
from src.data.repositories.portfolio_repository import PortfolioRepository

logger = logging.getLogger("365advisers.engines.portfolio")


class PortfolioEngine:
    """
    Façade for the Portfolio Construction Engine.

    Usage:
        # Build a new portfolio from analysis results
        result = PortfolioEngine.build(analyses)

        # Rebalance an existing portfolio
        rebalance = PortfolioEngine.rebalance(portfolio_id, new_targets)
    """

    @staticmethod
    def build(
        analyses: list[dict],
        risk_limits: RiskLimits | None = None,
        persist: bool = False,
        portfolio_name: str = "Auto-Generated Portfolio",
    ) -> dict:
        """
        Build a portfolio from individual ticker analysis results.

        Args:
            analyses: List of analysis dicts with keys:
                      ticker, sector, opportunity_score, dimensions, position_sizing
            risk_limits: Custom risk limits (optional, uses defaults)
            persist: Whether to save the portfolio to the database
            portfolio_name: Name for the persisted portfolio

        Returns:
            Portfolio recommendation dict with positions, exposures, and violations.
        """
        # ── Step 1: Use existing builder for classification + volatility parity ──
        raw_portfolio = PortfolioConstructionModel.build_portfolio(analyses)

        # ── Step 2: Run enhanced risk budget checks ──────────────────────
        risk_engine = RiskBudgetEngine(risk_limits)
        all_positions = raw_portfolio["core_positions"] + raw_portfolio["satellite_positions"]
        risk_result = risk_engine.evaluate(all_positions)

        # ── Step 3: Re-split into core/satellite after risk adjustments ──
        core = [p for p in risk_result.positions if p.get("role") == "CORE"]
        satellite = [p for p in risk_result.positions if p.get("role") != "CORE"]

        # ── Step 4: Combine violations ───────────────────────────────────
        all_violations = raw_portfolio.get("violations_detected", []) + risk_result.violations

        # ── Step 5: Compute final totals ─────────────────────────────────
        core_total = round(sum(p["target_weight"] for p in core), 2)
        sat_total = round(sum(p["target_weight"] for p in satellite), 2)

        result = {
            "total_allocation": round(core_total + sat_total, 2),
            "core_allocation_total": core_total,
            "satellite_allocation_total": sat_total,
            "risk_level": "MODERATE" if sat_total <= 50.0 else "ELEVATED",
            "sector_exposures": risk_result.sector_exposures,
            "core_positions": sorted(core, key=lambda x: x["target_weight"], reverse=True),
            "satellite_positions": sorted(satellite, key=lambda x: x["target_weight"], reverse=True),
            "violations_detected": all_violations,
            "position_count": len(risk_result.positions),
        }

        # ── Step 6: Persist if requested ─────────────────────────────────
        if persist and risk_result.positions:
            portfolio_id = PortfolioRepository.save_portfolio(
                name=portfolio_name,
                strategy="Core-Satellite",
                risk_level=result["risk_level"],
                total_allocation=result["total_allocation"],
                positions=risk_result.positions,
            )
            if portfolio_id:
                result["portfolio_id"] = portfolio_id
                logger.info(f"Portfolio saved with ID {portfolio_id}")

        return result

    @staticmethod
    def rebalance(
        portfolio_id: int,
        new_targets: list[dict],
        threshold_pct: float = 2.0,
    ) -> dict:
        """
        Compare an existing portfolio against new target allocations.

        Args:
            portfolio_id: ID of the saved portfolio to rebalance.
            new_targets: List of {ticker, target_weight} for new targets.
            threshold_pct: Minimum drift (%) to trigger a rebalance action.

        Returns:
            Rebalance result with per-position actions.
        """
        existing = PortfolioRepository.get_portfolio(portfolio_id)
        if not existing:
            return {"error": f"Portfolio {portfolio_id} not found"}

        # Build current weights map
        current_weights = {
            pos["ticker"]: pos["target_weight"]
            for pos in existing.get("positions", [])
        }

        rebalancer = Rebalancer(threshold_pct=threshold_pct)
        result = rebalancer.compute(current_weights, new_targets)

        return {
            "portfolio_id": portfolio_id,
            "portfolio_name": existing.get("name", ""),
            "needs_rebalance": result.needs_rebalance,
            "total_drift": result.total_drift,
            "summary": result.summary,
            "actions": [asdict(a) for a in result.actions],
        }
