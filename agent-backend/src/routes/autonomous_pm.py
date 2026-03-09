"""
src/routes/autonomous_pm.py
──────────────────────────────────────────────────────────────────────────────
REST API for the Autonomous Portfolio Manager (APM).

Endpoints:
  POST /apm/manage        — Full APM pipeline
  POST /apm/construct     — Portfolio construction only
  POST /apm/allocate      — Asset allocation only
  POST /apm/rebalance     — Rebalancing evaluation only
  POST /apm/risk          — Risk management only
  POST /apm/performance   — Performance analysis only
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.engines.autonomous_pm.engine import AutonomousPortfolioManager
from src.engines.autonomous_pm.construction_engine import ConstructionEngine
from src.engines.autonomous_pm.allocation_engine import AllocationEngine
from src.engines.autonomous_pm.rebalancing_engine import RebalancingEngine
from src.engines.autonomous_pm.risk_management_engine import RiskManagementEngine
from src.engines.autonomous_pm.performance_engine import PerformanceEngine
from src.engines.autonomous_pm.models import (
    APMPortfolio,
    PortfolioObjective,
    AllocationMethodAPM,
)

logger = logging.getLogger("365advisers.routes.autonomous_pm")

router = APIRouter(prefix="/apm", tags=["Autonomous Portfolio Manager"])


# ── Request models ───────────────────────────────────────────────────────────

class ManageRequest(BaseModel):
    alpha_profiles: list[dict] = Field(default_factory=list)
    regime: str = "expansion"
    previous_regime: str | None = None
    opportunities: list[dict] = Field(default_factory=list)
    risk_alerts: list[dict] = Field(default_factory=list)
    asset_volatilities: dict[str, float] = Field(default_factory=dict)
    correlations: dict[str, dict[str, float]] = Field(default_factory=dict)
    portfolio_returns: list[float] = Field(default_factory=list)
    benchmark_returns: list[float] = Field(default_factory=list)
    market_events: list[dict] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list, description="List of objective names, e.g. ['growth', 'value']")


class ConstructRequest(BaseModel):
    objective: str = "growth"
    alpha_profiles: list[dict] = Field(default_factory=list)
    regime: str = "expansion"
    opportunities: list[dict] = Field(default_factory=list)


class AllocateRequest(BaseModel):
    portfolio: dict = Field(default_factory=dict)
    asset_volatilities: dict[str, float] = Field(default_factory=dict)
    correlations: dict[str, dict[str, float]] = Field(default_factory=dict)
    regime: str = "expansion"
    method: str | None = None


class RebalanceRequest(BaseModel):
    current_portfolio: dict = Field(default_factory=dict)
    new_alpha_profiles: list[dict] = Field(default_factory=list)
    current_regime: str = "expansion"
    previous_regime: str | None = None
    risk_report: dict | None = None
    market_events: list[dict] = Field(default_factory=list)


class RiskRequest(BaseModel):
    portfolio: dict = Field(default_factory=dict)
    asset_volatilities: dict[str, float] = Field(default_factory=dict)
    correlations: dict[str, dict[str, float]] = Field(default_factory=dict)
    returns_history: list[float] = Field(default_factory=list)


class PerformanceRequest(BaseModel):
    portfolio_returns: list[float] = Field(default_factory=list)
    benchmark_returns: list[float] = Field(default_factory=list)
    benchmark_name: str = "S&P 500"
    risk_free_rate: float = 0.05


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/manage")
async def full_manage(request: ManageRequest):
    """Run the complete APM pipeline."""
    apm = AutonomousPortfolioManager()

    objectives = None
    if request.objectives:
        objectives = []
        for o in request.objectives:
            try:
                objectives.append(PortfolioObjective(o))
            except ValueError:
                pass

    dashboard = apm.manage(
        alpha_profiles=request.alpha_profiles,
        regime=request.regime,
        previous_regime=request.previous_regime,
        opportunities=request.opportunities,
        risk_alerts=request.risk_alerts,
        asset_volatilities=request.asset_volatilities,
        correlations=request.correlations,
        portfolio_returns=request.portfolio_returns,
        benchmark_returns=request.benchmark_returns,
        market_events=request.market_events,
        objectives=objectives,
    )
    return dashboard.model_dump(mode="json")


@router.post("/construct")
async def construct_portfolio(request: ConstructRequest):
    """Construct a single portfolio."""
    try:
        objective = PortfolioObjective(request.objective)
    except ValueError:
        objective = PortfolioObjective.GROWTH

    engine = ConstructionEngine()
    portfolio = engine.construct(
        objective=objective,
        alpha_profiles=request.alpha_profiles,
        regime=request.regime,
        opportunities=request.opportunities,
    )
    return portfolio.model_dump(mode="json")


@router.post("/allocate")
async def allocate_portfolio(request: AllocateRequest):
    """Optimise portfolio weights."""
    try:
        portfolio = APMPortfolio(**request.portfolio)
    except Exception:
        return {"error": "Invalid portfolio data"}

    method = None
    if request.method:
        try:
            method = AllocationMethodAPM(request.method)
        except ValueError:
            pass

    engine = AllocationEngine()
    result = engine.optimise(
        portfolio=portfolio,
        asset_volatilities=request.asset_volatilities,
        correlations=request.correlations,
        regime=request.regime,
        method=method,
    )
    return result.model_dump(mode="json")


@router.post("/rebalance")
async def evaluate_rebalance(request: RebalanceRequest):
    """Evaluate rebalancing triggers."""
    from src.engines.autonomous_pm.models import PortfolioRiskReport

    portfolio = None
    if request.current_portfolio:
        try:
            portfolio = APMPortfolio(**request.current_portfolio)
        except Exception:
            pass

    risk_report = None
    if request.risk_report:
        try:
            risk_report = PortfolioRiskReport(**request.risk_report)
        except Exception:
            pass

    engine = RebalancingEngine()
    rec = engine.evaluate(
        current_portfolio=portfolio,
        new_alpha_profiles=request.new_alpha_profiles,
        current_regime=request.current_regime,
        previous_regime=request.previous_regime,
        risk_report=risk_report,
        market_events=request.market_events,
    )
    return rec.model_dump(mode="json")


@router.post("/risk")
async def assess_risk(request: RiskRequest):
    """Assess portfolio risk."""
    portfolio = None
    if request.portfolio:
        try:
            portfolio = APMPortfolio(**request.portfolio)
        except Exception:
            return {"error": "Invalid portfolio data"}

    engine = RiskManagementEngine()
    report = engine.assess(
        portfolio=portfolio,
        asset_volatilities=request.asset_volatilities,
        correlations=request.correlations,
        returns_history=request.returns_history if request.returns_history else None,
    )
    return report.model_dump(mode="json")


@router.post("/performance")
async def analyse_performance(request: PerformanceRequest):
    """Evaluate portfolio performance."""
    engine = PerformanceEngine()
    snapshot = engine.evaluate(
        portfolio_returns=request.portfolio_returns,
        benchmark_returns=request.benchmark_returns,
        benchmark_name=request.benchmark_name,
        risk_free_rate=request.risk_free_rate,
    )
    return snapshot.model_dump(mode="json")
