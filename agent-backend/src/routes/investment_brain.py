"""
src/routes/investment_brain.py
──────────────────────────────────────────────────────────────────────────────
REST API for the Investment Brain — Financial Decision Intelligence.

Endpoints:
  POST /brain/analyze       — Full Investment Brain analysis
  POST /brain/regime        — Market Regime Detection only
  POST /brain/opportunities — Opportunity Detection only
  POST /brain/portfolios    — Portfolio Advisory only
  POST /brain/risks         — Risk Detection only
  POST /brain/insights      — Investment Insights only
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.engines.investment_brain.engine import InvestmentBrain
from src.engines.investment_brain.insights_engine import InsightsEngine
from src.engines.investment_brain.opportunity_detector import OpportunityDetector
from src.engines.investment_brain.portfolio_advisor import PortfolioAdvisor
from src.engines.investment_brain.regime_detector import RegimeDetector
from src.engines.investment_brain.risk_detector import RiskDetector

logger = logging.getLogger("365advisers.routes.investment_brain")

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/brain", tags=["Investment Brain"], dependencies=[Depends(get_current_user)])


# ── Request models ───────────────────────────────────────────────────────────

class FullAnalysisRequest(BaseModel):
    """Request body for the full Investment Brain analysis."""
    macro_data: dict = Field(default_factory=dict)
    vol_data: dict = Field(default_factory=dict)
    universe_data: list[list] = Field(
        default_factory=list,
        description="List of [ticker, data_dict] pairs",
    )
    sentiment_data: list[dict] = Field(default_factory=list)
    event_data: list[dict] = Field(default_factory=list)
    index_data: dict = Field(default_factory=dict)


class RegimeRequest(BaseModel):
    macro_data: dict = Field(default_factory=dict)
    vol_data: dict = Field(default_factory=dict)
    index_data: dict = Field(default_factory=dict)


class OpportunityRequest(BaseModel):
    alpha_profiles: list[dict] = Field(default_factory=list)
    sentiment_scores: list[dict] = Field(default_factory=list)
    vol_data: dict = Field(default_factory=dict)
    event_scores: list[dict] = Field(default_factory=list)
    regime_data: dict = Field(
        default_factory=dict,
        description="Regime override: {regime, confidence}",
    )


class PortfolioRequest(BaseModel):
    opportunities: list[dict] = Field(default_factory=list)
    regime_data: dict = Field(default_factory=dict)
    risk_alerts: list[dict] = Field(default_factory=list)


class RiskRequest(BaseModel):
    vol_data: dict = Field(default_factory=dict)
    macro_data: dict = Field(default_factory=dict)
    alpha_profiles: list[dict] = Field(default_factory=list)
    sentiment_scores: list[dict] = Field(default_factory=list)


class InsightRequest(BaseModel):
    regime_data: dict = Field(default_factory=dict)
    opportunities: list[dict] = Field(default_factory=list)
    risk_alerts: list[dict] = Field(default_factory=list)
    sentiment_scores: list[dict] = Field(default_factory=list)
    macro_data: dict = Field(default_factory=dict)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/analyze")
async def full_analysis(request: FullAnalysisRequest):
    """Run the complete Investment Brain analysis pipeline."""
    brain = InvestmentBrain()

    # Convert list[list] → list[tuple[str, dict]]
    universe = []
    for item in request.universe_data:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            universe.append((str(item[0]), item[1] if isinstance(item[1], dict) else {}))

    dashboard = brain.analyze(
        macro_data=request.macro_data,
        vol_data=request.vol_data,
        universe_data=universe,
        sentiment_data=request.sentiment_data,
        event_data=request.event_data,
        index_data=request.index_data,
    )

    return dashboard.model_dump(mode="json")


@router.post("/regime")
async def detect_regime(request: RegimeRequest):
    """Detect the current market regime."""
    detector = RegimeDetector()
    classification = detector.detect(
        macro_data=request.macro_data,
        vol_data=request.vol_data,
        index_data=request.index_data,
    )
    return classification.model_dump(mode="json")


@router.post("/opportunities")
async def detect_opportunities(request: OpportunityRequest):
    """Detect investment opportunities."""
    from src.engines.investment_brain.models import RegimeClassification, MarketRegime

    regime = None
    if request.regime_data:
        regime_str = request.regime_data.get("regime", "expansion")
        try:
            regime_enum = MarketRegime(regime_str)
        except ValueError:
            regime_enum = MarketRegime.EXPANSION
        regime = RegimeClassification(
            regime=regime_enum,
            confidence=request.regime_data.get("confidence", 0.5),
        )

    detector = OpportunityDetector()
    opportunities = detector.detect(
        alpha_profiles=request.alpha_profiles,
        sentiment_scores=request.sentiment_scores,
        vol_data=request.vol_data,
        event_scores=request.event_scores,
        regime=regime,
    )
    return [o.model_dump(mode="json") for o in opportunities]


@router.post("/portfolios")
async def suggest_portfolios(request: PortfolioRequest):
    """Generate portfolio suggestions."""
    from src.engines.investment_brain.models import (
        DetectedOpportunity,
        RegimeClassification,
        RiskAlert,
        MarketRegime,
        OpportunityType,
        RiskAlertType,
        RiskAlertSeverity,
    )

    # Reconstruct opportunities from dicts
    opportunities = []
    for o in request.opportunities:
        try:
            opportunities.append(DetectedOpportunity(**o))
        except Exception:
            pass

    # Reconstruct regime
    regime = None
    if request.regime_data:
        regime_str = request.regime_data.get("regime", "expansion")
        try:
            regime_enum = MarketRegime(regime_str)
        except ValueError:
            regime_enum = MarketRegime.EXPANSION
        regime = RegimeClassification(
            regime=regime_enum,
            confidence=request.regime_data.get("confidence", 0.5),
        )

    # Reconstruct risk alerts
    alerts = []
    for a in request.risk_alerts:
        try:
            alerts.append(RiskAlert(**a))
        except Exception:
            pass

    advisor = PortfolioAdvisor()
    portfolios = advisor.advise(
        opportunities=opportunities,
        regime=regime,
        risk_alerts=alerts,
    )
    return [p.model_dump(mode="json") for p in portfolios]


@router.post("/risks")
async def detect_risks(request: RiskRequest):
    """Detect market risks."""
    detector = RiskDetector()
    alerts = detector.detect(
        vol_data=request.vol_data,
        macro_data=request.macro_data,
        alpha_profiles=request.alpha_profiles,
        sentiment_scores=request.sentiment_scores,
    )
    return [a.model_dump(mode="json") for a in alerts]


@router.post("/insights")
async def generate_insights(request: InsightRequest):
    """Generate investment insights."""
    from src.engines.investment_brain.models import (
        DetectedOpportunity,
        RegimeClassification,
        RiskAlert,
        MarketRegime,
    )

    regime = None
    if request.regime_data:
        regime_str = request.regime_data.get("regime", "expansion")
        try:
            regime_enum = MarketRegime(regime_str)
        except ValueError:
            regime_enum = MarketRegime.EXPANSION
        regime = RegimeClassification(
            regime=regime_enum,
            confidence=request.regime_data.get("confidence", 0.5),
        )

    opportunities = []
    for o in request.opportunities:
        try:
            opportunities.append(DetectedOpportunity(**o))
        except Exception:
            pass

    risk_alerts = []
    for a in request.risk_alerts:
        try:
            risk_alerts.append(RiskAlert(**a))
        except Exception:
            pass

    engine = InsightsEngine()
    insights = engine.generate(
        regime=regime,
        opportunities=opportunities,
        risk_alerts=risk_alerts,
        sentiment_scores=request.sentiment_scores,
        macro_data=request.macro_data,
    )
    return [i.model_dump(mode="json") for i in insights]
