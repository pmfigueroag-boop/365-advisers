"""
src/engines/investment_brain/engine.py
──────────────────────────────────────────────────────────────────────────────
InvestmentBrain — the master facade that orchestrates all 5 sub-modules
into a unified Financial Decision Intelligence pipeline.

Pipeline:
  macro → volatility → regime detection → alpha scoring →
  opportunity detection → risk detection → portfolio advisory →
  insights generation → alert compilation → dashboard

Consumes: AlphaMacroEngine, AlphaVolatilityEngine, AlphaSentimentEngine,
          AlphaEventEngine, SuperAlphaEngine
Output:   InvestmentBrainDashboard
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.alpha_event.engine import AlphaEventEngine
from src.engines.alpha_macro.engine import AlphaMacroEngine
from src.engines.alpha_sentiment.engine import AlphaSentimentEngine
from src.engines.alpha_volatility.engine import AlphaVolatilityEngine
from src.engines.super_alpha.engine import SuperAlphaEngine

from src.engines.investment_brain.insights_engine import InsightsEngine
from src.engines.investment_brain.models import (
    BrainAlert,
    BrainAlertType,
    InvestmentBrainDashboard,
    MarketRegime,
    RegimeClassification,
    RiskAlertSeverity,
)
from src.engines.investment_brain.opportunity_detector import OpportunityDetector
from src.engines.investment_brain.portfolio_advisor import PortfolioAdvisor
from src.engines.investment_brain.regime_detector import RegimeDetector
from src.engines.investment_brain.risk_detector import RiskDetector

logger = logging.getLogger("365advisers.investment_brain")


class InvestmentBrain:
    """
    Financial Decision Intelligence facade.

    Integrates all Alpha engines into a single interpretation layer
    that produces a comprehensive InvestmentBrainDashboard.

    Usage::

        brain = InvestmentBrain()
        dashboard = brain.analyze(
            macro_data={"gdp_growth": 2.8, "inflation": 3.1, ...},
            vol_data={"vix_current": 18.5, "iv_rank": 45, ...},
            universe_data=[("AAPL", {...}), ("MSFT", {...}), ...],
            sentiment_data=[{"ticker": "AAPL", "bullish_pct": 72, ...}, ...],
            event_data=[{"ticker": "AAPL", "events": [...]}, ...],
        )
    """

    def __init__(self) -> None:
        self.macro_engine = AlphaMacroEngine()
        self.vol_engine = AlphaVolatilityEngine()
        self.sentiment_engine = AlphaSentimentEngine()
        self.event_engine = AlphaEventEngine()
        self.super_alpha = SuperAlphaEngine()

        self.regime_detector = RegimeDetector()
        self.opportunity_detector = OpportunityDetector()
        self.portfolio_advisor = PortfolioAdvisor()
        self.risk_detector = RiskDetector()
        self.insights_engine = InsightsEngine()

    # ── Full pipeline ────────────────────────────────────────────────────

    def analyze(
        self,
        macro_data: dict | None = None,
        vol_data: dict | None = None,
        universe_data: list[tuple[str, dict]] | None = None,
        sentiment_data: list[dict] | None = None,
        event_data: list[dict] | None = None,
        index_data: dict | None = None,
    ) -> InvestmentBrainDashboard:
        """
        Run the complete Investment Brain pipeline.

        Parameters
        ----------
        macro_data : dict | None
            Macro indicators for regime detection.
        vol_data : dict | None
            Volatility data for regime & risk detection.
        universe_data : list[tuple[str, dict]] | None
            List of (ticker, data_dict) for alpha scoring.
        sentiment_data : list[dict] | None
            List of sentiment data dicts per ticker.
        event_data : list[dict] | None
            List of event data dicts per ticker: {ticker, events: [...]}
        index_data : dict | None
            Index-level behaviour data (S&P 500 returns, etc.)
        """
        macro = macro_data or {}
        vol = vol_data or {}
        universe = universe_data or []
        sentiments = sentiment_data or []
        events = event_data or []
        idx = index_data or {}

        logger.info("Investment Brain pipeline starting — %d assets", len(universe))

        # ── Stage 1: Macro analysis ──────────────────────────────────────
        macro_dashboard = None
        try:
            macro_dashboard = self.macro_engine.analyze(macro)
        except Exception as e:
            logger.warning("Macro engine error: %s", e)

        # ── Stage 2: Volatility analysis ─────────────────────────────────
        vol_dashboard = None
        try:
            vol_dashboard = self.vol_engine.analyze(vol)
        except Exception as e:
            logger.warning("Volatility engine error: %s", e)

        # ── Stage 3: Market regime detection ─────────────────────────────
        regime = self.regime_detector.detect(
            macro_data=macro,
            vol_data=vol,
            index_data=idx,
        )
        logger.info("Regime: %s (confidence=%.2f)", regime.regime.value, regime.confidence)

        # ── Stage 4: Alpha scoring (SuperAlpha) ──────────────────────────
        alpha_profiles: list[dict] = []
        if universe:
            try:
                ranking = self.super_alpha.rank_universe(universe)
                alpha_profiles = [
                    {
                        "ticker": p.ticker,
                        "composite_alpha_score": p.composite_alpha_score,
                        "tier": p.tier.value if hasattr(p.tier, "value") else str(p.tier),
                        "sector": p.sector,
                        "top_drivers": [d.dict() if hasattr(d, "dict") else d for d in (p.top_drivers or [])],
                        "factor_scores": {
                            name.value if hasattr(name, "value") else str(name): fs.score
                            for name, fs in (p.factor_scores or {}).items()
                        },
                    }
                    for p in ranking.profiles
                ]
            except Exception as e:
                logger.warning("SuperAlpha engine error: %s", e)

        # ── Stage 5: Sentiment analysis ──────────────────────────────────
        sentiment_scores: list[dict] = []
        for s_data in sentiments:
            ticker = s_data.get("ticker", "")
            if not ticker:
                continue
            try:
                result = self.sentiment_engine.analyze(ticker, s_data)
                sentiment_scores.append({
                    "ticker": ticker,
                    "composite_score": result.composite_score,
                    "regime": result.regime.value,
                    "polarity": result.polarity,
                    "momentum_of_attention": result.momentum_of_attention,
                })
            except Exception as e:
                logger.warning("Sentiment engine error for %s: %s", ticker, e)

        # ── Stage 6: Event analysis ──────────────────────────────────────
        event_scores: list[dict] = []
        for e_data in events:
            ticker = e_data.get("ticker", "")
            raw_events = e_data.get("events", [])
            if not ticker or not raw_events:
                continue
            try:
                detected = self.event_engine.detect_events(ticker, raw_events)
                score = self.event_engine.score_ticker(ticker, detected)
                event_scores.append({
                    "ticker": ticker,
                    "composite_score": score.composite_score,
                    "bullish_events": score.bullish_events,
                    "bearish_events": score.bearish_events,
                    "most_significant_headline": score.most_significant.headline if score.most_significant else "",
                    "signals": score.signals,
                })
            except Exception as e:
                logger.warning("Event engine error for %s: %s", ticker, e)

        # ── Stage 7: Opportunity detection ───────────────────────────────
        opportunities = self.opportunity_detector.detect(
            alpha_profiles=alpha_profiles,
            sentiment_scores=sentiment_scores,
            vol_data=vol,
            event_scores=event_scores,
            regime=regime,
        )
        logger.info("Detected %d opportunities", len(opportunities))

        # ── Stage 8: Risk detection ──────────────────────────────────────
        risk_alerts = self.risk_detector.detect(
            vol_data=vol,
            macro_data=macro,
            alpha_profiles=alpha_profiles,
            sentiment_scores=sentiment_scores,
        )
        logger.info("Detected %d risk alerts", len(risk_alerts))

        # ── Stage 9: Portfolio advisory ──────────────────────────────────
        portfolios = self.portfolio_advisor.advise(
            opportunities=opportunities,
            regime=regime,
            risk_alerts=risk_alerts,
        )

        # ── Stage 10: Insights generation ────────────────────────────────
        insights = self.insights_engine.generate(
            regime=regime,
            opportunities=opportunities,
            risk_alerts=risk_alerts,
            sentiment_scores=sentiment_scores,
            macro_data=macro,
        )
        logger.info("Generated %d insights", len(insights))

        # ── Build dashboard ──────────────────────────────────────────────
        return InvestmentBrainDashboard(
            regime=regime,
            opportunities=opportunities,
            portfolios=portfolios,
            risk_alerts=risk_alerts,
            insights=insights,
            alerts=[],
            asset_count=len(universe),
        )

    # ── Alert generation (diff-based) ────────────────────────────────────

    @staticmethod
    def generate_alerts(
        prev: InvestmentBrainDashboard | None,
        current: InvestmentBrainDashboard,
    ) -> list[BrainAlert]:
        """
        Compare two dashboard snapshots and generate transition alerts.

        Parameters
        ----------
        prev : InvestmentBrainDashboard | None
            Previous dashboard (None = first run, no alerts).
        current : InvestmentBrainDashboard
            Current dashboard.
        """
        if prev is None:
            return []

        alerts: list[BrainAlert] = []

        # Regime change
        if prev.regime.regime != current.regime.regime:
            alerts.append(BrainAlert(
                alert_type=BrainAlertType.REGIME_CHANGE,
                severity=RiskAlertSeverity.HIGH,
                title=f"Regime Change: {prev.regime.regime.value} → {current.regime.regime.value}",
                description=f"Market regime has shifted from {prev.regime.regime.value} to {current.regime.regime.value}. Portfolio review recommended.",
            ))

        # New opportunities
        prev_tickers = {o.ticker for o in prev.opportunities}
        for opp in current.opportunities[:5]:
            if opp.ticker not in prev_tickers:
                alerts.append(BrainAlert(
                    alert_type=BrainAlertType.NEW_OPPORTUNITY,
                    severity=RiskAlertSeverity.MODERATE,
                    title=f"New Opportunity: {opp.ticker}",
                    description=f"{opp.ticker} entered opportunity list ({opp.opportunity_type.value}, alpha={opp.alpha_score:.0f}).",
                    related_tickers=[opp.ticker],
                ))

        # New risk alerts
        prev_risk_titles = {a.title for a in prev.risk_alerts}
        for alert in current.risk_alerts:
            if alert.title not in prev_risk_titles and alert.severity in (
                RiskAlertSeverity.HIGH,
                RiskAlertSeverity.CRITICAL,
            ):
                alerts.append(BrainAlert(
                    alert_type=BrainAlertType.NEW_RISK,
                    severity=alert.severity,
                    title=f"New Risk: {alert.title}",
                    description=alert.description,
                    related_tickers=alert.affected_tickers,
                ))

        # Top alpha entries
        prev_top = {o.ticker for o in prev.opportunities[:3]}
        for opp in current.opportunities[:3]:
            if opp.ticker not in prev_top and opp.alpha_score > 75:
                alerts.append(BrainAlert(
                    alert_type=BrainAlertType.TOP_ALPHA_ENTRY,
                    severity=RiskAlertSeverity.MODERATE,
                    title=f"Top Alpha: {opp.ticker}",
                    description=f"{opp.ticker} entered top-3 alpha ranking with score {opp.alpha_score:.0f}.",
                    related_tickers=[opp.ticker],
                ))

        return alerts
