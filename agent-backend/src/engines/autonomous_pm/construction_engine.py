"""
src/engines/autonomous_pm/construction_engine.py
──────────────────────────────────────────────────────────────────────────────
Portfolio Construction Engine — builds 6 portfolio types from alpha signals
filtered by regime context and opportunity data.

Consumes: SuperAlpha rankings, InvestmentBrain regime/opportunities.
Output:   APMPortfolio with justified positions and factor exposures.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.autonomous_pm.models import (
    APMPortfolio,
    APMPosition,
    AllocationMethodAPM,
    PortfolioObjective,
)

logger = logging.getLogger("365advisers.apm.construction")


# ── Style rules ──────────────────────────────────────────────────────────────

_OBJECTIVE_CONFIG: dict[PortfolioObjective, dict] = {
    PortfolioObjective.GROWTH: {
        "min_alpha": 60,
        "preferred_factors": ["momentum", "growth", "innovation"],
        "max_positions": 12,
        "allocation_method": AllocationMethodAPM.MAX_SHARPE,
        "description": "High-conviction growth assets with strong momentum and alpha signals.",
    },
    PortfolioObjective.VALUE: {
        "min_alpha": 50,
        "preferred_factors": ["value", "quality", "earnings"],
        "max_positions": 15,
        "allocation_method": AllocationMethodAPM.RISK_PARITY,
        "description": "Undervalued, high-quality assets with margin of safety.",
    },
    PortfolioObjective.INCOME: {
        "min_alpha": 40,
        "preferred_factors": ["dividend", "cashflow", "quality"],
        "max_positions": 15,
        "allocation_method": AllocationMethodAPM.EQUAL_RISK_CONTRIBUTION,
        "description": "Stable, cash-generative assets with consistent income streams.",
    },
    PortfolioObjective.BALANCED: {
        "min_alpha": 45,
        "preferred_factors": ["quality", "value", "momentum"],
        "max_positions": 20,
        "allocation_method": AllocationMethodAPM.FACTOR_DIVERSIFICATION,
        "description": "Diversified blend of growth and value with balanced factor exposures.",
    },
    PortfolioObjective.DEFENSIVE: {
        "min_alpha": 35,
        "preferred_factors": ["quality", "low_volatility", "dividend"],
        "max_positions": 15,
        "allocation_method": AllocationMethodAPM.MIN_VARIANCE,
        "description": "Low-volatility, high-quality assets for capital preservation.",
    },
    PortfolioObjective.OPPORTUNISTIC: {
        "min_alpha": 65,
        "preferred_factors": ["momentum", "event", "sentiment"],
        "max_positions": 10,
        "allocation_method": AllocationMethodAPM.VOLATILITY_TARGETING,
        "description": "High-alpha, event-driven plays for maximum risk-adjusted return potential.",
    },
}

# ── Regime-sector alignment ─────────────────────────────────────────────────

_REGIME_SECTORS: dict[str, list[str]] = {
    "expansion": ["Technology", "Consumer Discretionary", "Industrials", "Financials"],
    "slowdown": ["Healthcare", "Utilities", "Consumer Staples"],
    "recession": ["Utilities", "Healthcare", "Consumer Staples"],
    "recovery": ["Financials", "Real Estate", "Industrials", "Materials"],
    "high_volatility": ["Utilities", "Healthcare", "Gold"],
    "liquidity_expansion": ["Technology", "Growth", "Real Estate"],
}


class ConstructionEngine:
    """
    Builds managed portfolios from alpha signals and regime context.

    Usage::

        engine = ConstructionEngine()
        portfolio = engine.construct(
            objective=PortfolioObjective.GROWTH,
            alpha_profiles=profiles,
            regime="expansion",
        )
    """

    def construct(
        self,
        objective: PortfolioObjective,
        alpha_profiles: list[dict] | None = None,
        regime: str = "expansion",
        opportunities: list[dict] | None = None,
    ) -> APMPortfolio:
        """
        Construct a portfolio for the given objective.

        Parameters
        ----------
        objective : PortfolioObjective
            The investment style to target.
        alpha_profiles : list[dict] | None
            SuperAlpha profiles: {ticker, composite_alpha_score, tier, sector, factor_scores}
        regime : str
            Current market regime string.
        opportunities : list[dict] | None
            Detected opportunities from Investment Brain.
        """
        profiles = alpha_profiles or []
        opps = opportunities or []
        config = _OBJECTIVE_CONFIG[objective]

        # ── Filter + score candidates ────────────────────────────────────
        candidates = self._filter_candidates(profiles, config, regime)

        # Boost candidates that also appear in opportunities
        opp_tickers = {o.get("ticker", "") for o in opps}
        for c in candidates:
            if c["ticker"] in opp_tickers:
                c["score"] *= 1.15

        # Sort by score descending and take top N
        candidates.sort(key=lambda c: c["score"], reverse=True)
        selected = candidates[:config["max_positions"]]

        if not selected:
            return APMPortfolio(
                objective=objective,
                allocation_method=config["allocation_method"],
                regime_context=regime,
                rationale=f"No assets met the {objective.value} criteria in {regime} regime.",
            )

        # ── Assign weights ───────────────────────────────────────────────
        positions = self._assign_weights(selected, config, regime)

        # ── Compute portfolio-level metrics ──────────────────────────────
        total_w = sum(p.weight for p in positions)
        avg_alpha = sum(p.alpha_score * p.weight for p in positions) / max(total_w, 0.001)

        return APMPortfolio(
            objective=objective,
            positions=positions,
            allocation_method=config["allocation_method"],
            total_weight=round(total_w, 4),
            expected_return=round(avg_alpha * 0.15 / 100, 4),  # rough mapping
            regime_context=regime,
            rationale=config["description"],
        )

    def construct_all(
        self,
        alpha_profiles: list[dict] | None = None,
        regime: str = "expansion",
        opportunities: list[dict] | None = None,
    ) -> list[APMPortfolio]:
        """Construct all 6 portfolio types."""
        return [
            self.construct(obj, alpha_profiles, regime, opportunities)
            for obj in PortfolioObjective
        ]

    # ── Internal methods ─────────────────────────────────────────────────

    def _filter_candidates(
        self,
        profiles: list[dict],
        config: dict,
        regime: str,
    ) -> list[dict]:
        """Filter profiles by alpha threshold and score them for style fit."""
        min_alpha = config["min_alpha"]
        preferred = config["preferred_factors"]
        favored_sectors = _REGIME_SECTORS.get(regime, [])
        candidates: list[dict] = []

        for p in profiles:
            alpha = _f(p.get("composite_alpha_score")) or 0
            if alpha < min_alpha:
                continue

            ticker = p.get("ticker", "")
            sector = p.get("sector", "Unknown")
            factors = p.get("factor_scores", {})

            # Style-fit scoring
            score = alpha
            for pf in preferred:
                factor_val = _f(factors.get(pf)) or 0
                if factor_val > 50:
                    score += factor_val * 0.1

            # Regime alignment bonus
            if sector in favored_sectors:
                score *= 1.1

            candidates.append({
                "ticker": ticker,
                "alpha": alpha,
                "sector": sector,
                "factors": factors,
                "score": score,
                "tier": p.get("tier", ""),
            })

        return candidates

    def _assign_weights(
        self,
        selected: list[dict],
        config: dict,
        regime: str,
    ) -> list[APMPosition]:
        """Assign score-proportional weights with a 25% single-position cap."""
        total_score = sum(c["score"] for c in selected) or 1.0
        positions: list[APMPosition] = []

        for c in selected:
            raw_w = c["score"] / total_score
            weight = min(round(raw_w, 4), 0.25)

            factor_exposures = {}
            factors = c.get("factors", {})
            for k, v in factors.items():
                fv = _f(v)
                if fv is not None and fv > 0:
                    factor_exposures[k] = round(fv / 100, 3)

            signals = [f"Alpha={c['alpha']:.0f}", f"Tier={c['tier']}"]
            if c["sector"] in _REGIME_SECTORS.get(regime, []):
                signals.append(f"Sector {c['sector']} aligned with {regime}")

            positions.append(APMPosition(
                ticker=c["ticker"],
                weight=weight,
                alpha_score=round(c["alpha"], 1),
                justification=f"Selected for {config['description'].split('.')[0].lower()} — alpha {c['alpha']:.0f}, sector {c['sector']}.",
                factor_exposures=factor_exposures,
                sector=c["sector"],
                signals_used=signals,
            ))

        # Normalize weights to sum to 1.0
        total_w = sum(p.weight for p in positions) or 1.0
        for p in positions:
            p.weight = round(p.weight / total_w, 4)

        return positions


def _f(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
