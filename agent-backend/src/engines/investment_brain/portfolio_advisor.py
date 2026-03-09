"""
src/engines/investment_brain/portfolio_advisor.py
──────────────────────────────────────────────────────────────────────────────
Portfolio Advisor — constructs 5 portfolio suggestions (Growth, Value,
Income, Defensive, Opportunistic) from detected opportunities adjusted
by the current market regime.

Consumes: DetectedOpportunity list, RegimeClassification, RiskAlert list.
Output:   list[PortfolioSuggestion]
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.investment_brain.models import (
    DetectedOpportunity,
    MarketRegime,
    OpportunityType,
    PortfolioStyle,
    PortfolioSuggestion,
    RegimeClassification,
    RiskAlert,
    RiskAlertSeverity,
    SuggestedPosition,
)

logger = logging.getLogger("365advisers.investment_brain.portfolio_advisor")


# ── Style filters ────────────────────────────────────────────────────────────

_STYLE_OPPORTUNITY_MAP: dict[PortfolioStyle, list[OpportunityType]] = {
    PortfolioStyle.GROWTH: [OpportunityType.MOMENTUM_BREAKOUT, OpportunityType.MACRO_ALIGNED],
    PortfolioStyle.VALUE: [OpportunityType.UNDERVALUED, OpportunityType.EVENT_CATALYST],
    PortfolioStyle.INCOME: [OpportunityType.UNDERVALUED, OpportunityType.MACRO_ALIGNED],
    PortfolioStyle.DEFENSIVE: [OpportunityType.MACRO_ALIGNED, OpportunityType.UNDERVALUED],
    PortfolioStyle.OPPORTUNISTIC: [OpportunityType.EVENT_CATALYST, OpportunityType.SENTIMENT_DRIVEN],
}

_STYLE_DESCRIPTIONS: dict[PortfolioStyle, str] = {
    PortfolioStyle.GROWTH: "Targets high-momentum, innovative companies with strong alpha scores and growth trajectories.",
    PortfolioStyle.VALUE: "Focuses on undervalued companies with strong fundamentals and margin of safety.",
    PortfolioStyle.INCOME: "Prioritises stable, dividend-paying companies with consistent cash flows.",
    PortfolioStyle.DEFENSIVE: "Low-volatility, high-quality companies designed to preserve capital in adverse conditions.",
    PortfolioStyle.OPPORTUNISTIC: "Event-driven and sentiment-powered plays for higher risk/reward seekers.",
}

# ── Regime suitability ───────────────────────────────────────────────────────

_REGIME_SUITABILITY: dict[MarketRegime, dict[PortfolioStyle, str]] = {
    MarketRegime.EXPANSION: {
        PortfolioStyle.GROWTH: "Highly Suitable",
        PortfolioStyle.VALUE: "Suitable",
        PortfolioStyle.INCOME: "Moderate",
        PortfolioStyle.DEFENSIVE: "Not Recommended",
        PortfolioStyle.OPPORTUNISTIC: "Suitable",
    },
    MarketRegime.SLOWDOWN: {
        PortfolioStyle.GROWTH: "Moderate",
        PortfolioStyle.VALUE: "Highly Suitable",
        PortfolioStyle.INCOME: "Highly Suitable",
        PortfolioStyle.DEFENSIVE: "Suitable",
        PortfolioStyle.OPPORTUNISTIC: "Moderate",
    },
    MarketRegime.RECESSION: {
        PortfolioStyle.GROWTH: "Not Recommended",
        PortfolioStyle.VALUE: "Suitable",
        PortfolioStyle.INCOME: "Highly Suitable",
        PortfolioStyle.DEFENSIVE: "Highly Suitable",
        PortfolioStyle.OPPORTUNISTIC: "Moderate",
    },
    MarketRegime.RECOVERY: {
        PortfolioStyle.GROWTH: "Suitable",
        PortfolioStyle.VALUE: "Highly Suitable",
        PortfolioStyle.INCOME: "Moderate",
        PortfolioStyle.DEFENSIVE: "Moderate",
        PortfolioStyle.OPPORTUNISTIC: "Highly Suitable",
    },
    MarketRegime.HIGH_VOLATILITY: {
        PortfolioStyle.GROWTH: "Not Recommended",
        PortfolioStyle.VALUE: "Moderate",
        PortfolioStyle.INCOME: "Suitable",
        PortfolioStyle.DEFENSIVE: "Highly Suitable",
        PortfolioStyle.OPPORTUNISTIC: "Moderate",
    },
    MarketRegime.LIQUIDITY_EXPANSION: {
        PortfolioStyle.GROWTH: "Highly Suitable",
        PortfolioStyle.VALUE: "Moderate",
        PortfolioStyle.INCOME: "Moderate",
        PortfolioStyle.DEFENSIVE: "Not Recommended",
        PortfolioStyle.OPPORTUNISTIC: "Highly Suitable",
    },
}


class PortfolioAdvisor:
    """
    Constructs 5 portfolio suggestions from opportunities and regime context.

    Usage::

        advisor = PortfolioAdvisor()
        portfolios = advisor.advise(opportunities, regime, risk_alerts)
    """

    MAX_POSITIONS = 10

    def advise(
        self,
        opportunities: list[DetectedOpportunity] | None = None,
        regime: RegimeClassification | None = None,
        risk_alerts: list[RiskAlert] | None = None,
    ) -> list[PortfolioSuggestion]:
        """Build 5 portfolio suggestions."""
        opps = opportunities or []
        current_regime = regime.regime if regime else MarketRegime.EXPANSION
        alerts = risk_alerts or []

        # Assess overall risk level for weighting adjustments
        has_critical_risk = any(a.severity == RiskAlertSeverity.CRITICAL for a in alerts)
        has_high_risk = any(a.severity == RiskAlertSeverity.HIGH for a in alerts)

        portfolios: list[PortfolioSuggestion] = []

        for style in PortfolioStyle:
            positions = self._build_positions(style, opps, current_regime)

            # Apply defensive adjustments if high risk
            risk_level = "low"
            if has_critical_risk:
                risk_level = "elevated" if style in (PortfolioStyle.GROWTH, PortfolioStyle.OPPORTUNISTIC) else "moderate"
            elif has_high_risk:
                risk_level = "moderate"

            suitability_map = _REGIME_SUITABILITY.get(current_regime, {})
            suitability = suitability_map.get(style, "Moderate")

            return_profile = self._expected_return_profile(style, current_regime)

            portfolios.append(PortfolioSuggestion(
                style=style,
                positions=positions,
                rationale=_STYLE_DESCRIPTIONS.get(style, ""),
                expected_return_profile=return_profile,
                risk_level=risk_level,
                regime_suitability=suitability,
            ))

        return portfolios

    def _build_positions(
        self,
        style: PortfolioStyle,
        opportunities: list[DetectedOpportunity],
        regime: MarketRegime,
    ) -> list[SuggestedPosition]:
        """Select and weight positions for a given portfolio style."""
        preferred_types = _STYLE_OPPORTUNITY_MAP.get(style, [])

        # Score each opportunity for this style
        scored: list[tuple[DetectedOpportunity, float]] = []
        for opp in opportunities:
            score = opp.alpha_score
            if opp.opportunity_type in preferred_types:
                score *= 1.3
            if opp.regime_alignment and "Strong" in opp.regime_alignment:
                score *= 1.1

            # Style-specific boosts
            if style == PortfolioStyle.DEFENSIVE and opp.confidence > 0.7:
                score *= 1.2
            if style == PortfolioStyle.GROWTH and opp.opportunity_type == OpportunityType.MOMENTUM_BREAKOUT:
                score *= 1.2
            if style == PortfolioStyle.VALUE and opp.opportunity_type == OpportunityType.UNDERVALUED:
                score *= 1.3

            scored.append((opp, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        # Take top N and assign weights using score-proportional allocation
        selected = scored[:self.MAX_POSITIONS]
        if not selected:
            return []

        total_score = sum(s for _, s in selected) or 1.0
        positions: list[SuggestedPosition] = []
        for opp, score in selected:
            raw_weight = score / total_score
            # Cap any single position at 25%
            weight = min(round(raw_weight, 4), 0.25)

            factor_exposures = {}
            if opp.opportunity_type == OpportunityType.UNDERVALUED:
                factor_exposures = {"value": 0.8, "momentum": 0.2, "quality": 0.5}
            elif opp.opportunity_type == OpportunityType.MOMENTUM_BREAKOUT:
                factor_exposures = {"momentum": 0.9, "value": 0.1, "volatility": 0.4}
            elif opp.opportunity_type == OpportunityType.SENTIMENT_DRIVEN:
                factor_exposures = {"sentiment": 0.8, "momentum": 0.5, "volatility": 0.6}
            elif opp.opportunity_type == OpportunityType.EVENT_CATALYST:
                factor_exposures = {"event": 0.9, "value": 0.3, "momentum": 0.4}
            elif opp.opportunity_type == OpportunityType.MACRO_ALIGNED:
                factor_exposures = {"macro": 0.8, "quality": 0.4, "value": 0.3}

            positions.append(SuggestedPosition(
                ticker=opp.ticker,
                weight=weight,
                justification=opp.justification,
                factor_exposures=factor_exposures,
            ))

        # Normalize weights to sum to 1.0
        total_w = sum(p.weight for p in positions) or 1.0
        for p in positions:
            p.weight = round(p.weight / total_w, 4)

        return positions

    @staticmethod
    def _expected_return_profile(style: PortfolioStyle, regime: MarketRegime) -> str:
        profiles = {
            PortfolioStyle.GROWTH: {
                MarketRegime.EXPANSION: "High growth potential (12-20% expected). Favorable macro conditions amplify momentum.",
                MarketRegime.RECESSION: "Elevated risk. Growth stocks typically underperform in recessionary environments.",
            },
            PortfolioStyle.VALUE: {
                MarketRegime.RECOVERY: "Strong recovery potential (+15-25%). Undervalued assets typically re-rate during recovery.",
                MarketRegime.RECESSION: "Moderate resilience. Deep value provides downside cushion.",
            },
            PortfolioStyle.INCOME: {
                MarketRegime.EXPANSION: "Stable income (4-6% yield) with moderate capital appreciation.",
                MarketRegime.RECESSION: "Defensive yield (5-7%). Income stocks provide stability in downturns.",
            },
            PortfolioStyle.DEFENSIVE: {
                MarketRegime.HIGH_VOLATILITY: "Capital preservation focus. Low-vol approach targets <10% drawdown.",
                MarketRegime.RECESSION: "Best relative performance. Quality + low-vol combination preserves capital.",
            },
            PortfolioStyle.OPPORTUNISTIC: {
                MarketRegime.RECOVERY: "High asymmetry potential (20-40%). Event catalysts accelerate during recovery.",
                MarketRegime.EXPANSION: "Active alpha generation through event-driven plays.",
            },
        }
        style_profiles = profiles.get(style, {})
        return style_profiles.get(regime, f"Moderate risk-adjusted returns expected in {regime.value} conditions.")
