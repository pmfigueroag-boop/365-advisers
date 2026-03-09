"""
src/engines/investment_brain/insights_engine.py
──────────────────────────────────────────────────────────────────────────────
Investment Insights Engine — converts raw signals into human-readable
narratives with what/why/implication structure.

Each insight clearly states what happened, why it happened, and what it
means for investors. All recommendations show factors used and source signals.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.investment_brain.models import (
    DetectedOpportunity,
    InsightCategory,
    InvestmentInsight,
    MarketRegime,
    RegimeClassification,
    RiskAlert,
    RiskAlertSeverity,
)

logger = logging.getLogger("365advisers.investment_brain.insights")


class InsightsEngine:
    """
    Translates engine signals into plain-language investment insights.

    Usage::

        engine = InsightsEngine()
        insights = engine.generate(
            regime=regime_classification,
            opportunities=opportunity_list,
            risk_alerts=risk_list,
            sentiment_scores=sentiments,
            macro_data=macro_dict,
        )
    """

    def generate(
        self,
        regime: RegimeClassification | None = None,
        opportunities: list[DetectedOpportunity] | None = None,
        risk_alerts: list[RiskAlert] | None = None,
        sentiment_scores: list[dict] | None = None,
        macro_data: dict | None = None,
    ) -> list[InvestmentInsight]:
        """Generate a list of investment insights from all available signals."""
        insights: list[InvestmentInsight] = []

        if regime:
            insights.extend(self._regime_insights(regime))

        if opportunities:
            insights.extend(self._opportunity_insights(opportunities, regime))

        if risk_alerts:
            insights.extend(self._risk_insights(risk_alerts))

        if sentiment_scores:
            insights.extend(self._sentiment_insights(sentiment_scores))

        if macro_data:
            insights.extend(self._macro_insights(macro_data, regime))

        return insights

    # ── Regime insights ──────────────────────────────────────────────────

    def _regime_insights(self, regime: RegimeClassification) -> list[InvestmentInsight]:
        insights: list[InvestmentInsight] = []

        regime_implications: dict[MarketRegime, tuple[str, str]] = {
            MarketRegime.EXPANSION: (
                "Strong economic growth supports risk assets and cyclical sectors.",
                "Consider overweighting equities, particularly technology and industrials. Reduce defensive allocations.",
            ),
            MarketRegime.SLOWDOWN: (
                "Decelerating growth and tightening conditions pressure risk assets.",
                "Shift toward quality and defensive sectors. Consider increasing fixed-income exposure.",
            ),
            MarketRegime.RECESSION: (
                "Contracting economy with deteriorating fundamentals.",
                "Prioritise capital preservation. Overweight cash, treasuries, and defensive equities. Avoid cyclicals.",
            ),
            MarketRegime.RECOVERY: (
                "Economy rebounding from trough with improving leading indicators.",
                "Re-enter risk assets selectively. Early-cycle sectors (financials, industrials) historically outperform.",
            ),
            MarketRegime.HIGH_VOLATILITY: (
                "Elevated market stress creates both risk and opportunity.",
                "Reduce position sizes, increase hedging, and focus on high-quality names with strong balance sheets.",
            ),
            MarketRegime.LIQUIDITY_EXPANSION: (
                "Accommodative monetary policy fueling asset price inflation.",
                "Growth and speculative assets benefit most. Monitor for bubble formation in risk assets.",
            ),
        }

        why, implication = regime_implications.get(
            regime.regime,
            ("Regime conditions are evolving.", "Monitor key indicators for direction."),
        )

        key_factors = [f.name for f in regime.contributing_factors if f.signal != "neutral"]

        insights.append(InvestmentInsight(
            what_happened=f"Market regime classified as {regime.regime.value} with {regime.confidence:.0%} confidence.",
            why_it_happened=why,
            what_it_means=implication,
            category=InsightCategory.REGIME,
            confidence=regime.confidence,
            factors_used=key_factors[:5],
        ))

        if regime.regime_changed and regime.previous_regime:
            insights.append(InvestmentInsight(
                what_happened=f"Regime has shifted from {regime.previous_regime.value} to {regime.regime.value}.",
                why_it_happened="Key macroeconomic indicators have crossed regime thresholds.",
                what_it_means="Portfolio rebalancing may be warranted. Historical regime transitions take 2-4 months to stabilize.",
                category=InsightCategory.REGIME,
                confidence=regime.confidence,
                factors_used=["Regime transition detection"],
            ))

        return insights

    # ── Opportunity insights ─────────────────────────────────────────────

    def _opportunity_insights(
        self,
        opportunities: list[DetectedOpportunity],
        regime: RegimeClassification | None,
    ) -> list[InvestmentInsight]:
        insights: list[InvestmentInsight] = []
        if not opportunities:
            return insights

        # Top opportunity summary
        top = opportunities[0]
        insights.append(InvestmentInsight(
            what_happened=f"{top.ticker} identified as top opportunity (Alpha Score: {top.alpha_score:.0f}, Type: {top.opportunity_type.value}).",
            why_it_happened=" | ".join(top.signals[:3]),
            what_it_means=top.justification,
            category=InsightCategory.OPPORTUNITY,
            confidence=top.confidence,
            related_tickers=[top.ticker],
            factors_used=top.signals[:5],
        ))

        # Opportunity type distribution
        from collections import Counter
        type_counts = Counter(o.opportunity_type.value for o in opportunities)
        most_common = type_counts.most_common(1)[0] if type_counts else None
        if most_common and len(opportunities) > 3:
            opp_type, count = most_common
            tickers = [o.ticker for o in opportunities if o.opportunity_type.value == opp_type][:5]
            regime_str = regime.regime.value if regime else "current"
            insights.append(InvestmentInsight(
                what_happened=f"{count} {opp_type.replace('_', ' ')} opportunities detected across {len(opportunities)} total opportunities.",
                why_it_happened=f"The {regime_str} regime creates favorable conditions for {opp_type.replace('_', ' ')} plays.",
                what_it_means=f"The market is presenting a cluster of {opp_type.replace('_', ' ')} setups — consider thematic exposure.",
                category=InsightCategory.OPPORTUNITY,
                confidence=0.7,
                related_tickers=tickers,
                factors_used=[f"{opp_type} detection"],
            ))

        return insights

    # ── Risk insights ────────────────────────────────────────────────────

    def _risk_insights(self, risk_alerts: list[RiskAlert]) -> list[InvestmentInsight]:
        insights: list[InvestmentInsight] = []

        critical = [a for a in risk_alerts if a.severity == RiskAlertSeverity.CRITICAL]
        high = [a for a in risk_alerts if a.severity == RiskAlertSeverity.HIGH]

        if critical:
            alert = critical[0]
            insights.append(InvestmentInsight(
                what_happened=f"CRITICAL: {alert.title}",
                why_it_happened=alert.description,
                what_it_means="Immediate portfolio review recommended. Consider de-risking positions and increasing hedges.",
                category=InsightCategory.RISK,
                confidence=0.9,
                related_tickers=alert.affected_tickers[:5],
                factors_used=alert.source_signals[:5],
            ))

        if high:
            titles = [a.title for a in high[:3]]
            insights.append(InvestmentInsight(
                what_happened=f"{len(high)} high-severity risk alerts active: {', '.join(titles)}.",
                why_it_happened="Multiple risk factors are converging across volatility, macro, and market structure dimensions.",
                what_it_means="Elevated caution warranted. Review position sizing and ensure adequate portfolio hedging.",
                category=InsightCategory.RISK,
                confidence=0.8,
                related_tickers=[t for a in high for t in a.affected_tickers[:2]],
                factors_used=[s for a in high for s in a.source_signals[:2]],
            ))

        return insights

    # ── Sentiment insights ───────────────────────────────────────────────

    def _sentiment_insights(self, sentiments: list[dict]) -> list[InvestmentInsight]:
        insights: list[InvestmentInsight] = []
        if not sentiments:
            return insights

        scores = [_f(s.get("composite_score")) or 0 for s in sentiments]
        avg_sentiment = sum(scores) / max(len(scores), 1)

        if avg_sentiment > 50:
            mood = "euphoric"
            implication = "Extreme bullish sentiment often precedes short-term pullbacks. Consider taking profits on extended positions."
        elif avg_sentiment > 20:
            mood = "optimistic"
            implication = "Positive sentiment supports current trends but monitor for signs of excess."
        elif avg_sentiment > -20:
            mood = "neutral"
            implication = "Balanced sentiment suggests the market lacks conviction — wait for clearer signals."
        elif avg_sentiment > -50:
            mood = "fearful"
            implication = "Elevated fear often creates buying opportunities in quality assets. Consider selective accumulation."
        else:
            mood = "panicked"
            implication = "Extreme bearish sentiment historically correlates with market bottoms. Contrarian opportunities may emerge."

        bullish_count = sum(1 for s in scores if s > 20)
        bearish_count = sum(1 for s in scores if s < -20)

        insights.append(InvestmentInsight(
            what_happened=f"Overall market sentiment is {mood} (average score: {avg_sentiment:.0f}). {bullish_count} bullish, {bearish_count} bearish.",
            why_it_happened=f"Composite sentiment across {len(sentiments)} assets reflects current market psychology.",
            what_it_means=implication,
            category=InsightCategory.SENTIMENT,
            confidence=0.65,
            factors_used=["Sentiment composite score", "Polarity analysis"],
        ))

        return insights

    # ── Macro insights ───────────────────────────────────────────────────

    def _macro_insights(
        self,
        macro: dict,
        regime: RegimeClassification | None,
    ) -> list[InvestmentInsight]:
        insights: list[InvestmentInsight] = []

        gdp = _f(macro.get("gdp_growth"))
        inflation = _f(macro.get("inflation"))
        interest_rate = _f(macro.get("interest_rate"))

        if gdp is not None and inflation is not None:
            real_rate = (interest_rate or 0) - inflation
            factors = [f"GDP={gdp:.1f}%", f"CPI={inflation:.1f}%"]
            if interest_rate is not None:
                factors.append(f"Rate={interest_rate:.1f}%")

            if gdp > 2.5 and inflation < 3.0:
                what = f"Goldilocks conditions: GDP at {gdp:.1f}% with controlled inflation at {inflation:.1f}%."
                why = "Strong growth with stable prices supports corporate earnings and risk appetite."
                means = "Favorable for equities. Growth and quality factors typically outperform in this environment."
            elif gdp > 2.0 and inflation > 4.0:
                what = f"Growth-inflation divergence: GDP at {gdp:.1f}% but inflation elevated at {inflation:.1f}%."
                why = "Monetary tightening may be needed to control prices, creating a headwind for growth."
                means = "Consider inflation-hedged positions (commodities, TIPS, real assets). Reduce duration exposure."
            elif gdp < 1.0:
                what = f"Growth weakness: GDP at {gdp:.1f}% approaching stall speed."
                why = "Leading indicators suggest economic momentum is fading."
                means = "Rotate toward defensive sectors and increase fixed-income allocation."
            else:
                what = f"Macro indicators: GDP at {gdp:.1f}%, inflation at {inflation:.1f}%."
                why = "Mixed economic signals create an uncertain outlook."
                means = "Maintain balanced positioning with diversified sector exposure."

            insights.append(InvestmentInsight(
                what_happened=what,
                why_it_happened=why,
                what_it_means=means,
                category=InsightCategory.MACRO,
                confidence=0.7,
                factors_used=factors,
            ))

        return insights


def _f(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
