"""src/routes/risk.py — VaR/CVaR Risk API."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from src.engines.risk.models import VaRMethod, StressScenario
from src.engines.risk.engine import RiskEngine
from src.engines.risk.var import VaRCalculator
from src.engines.risk.cvar import CVaRCalculator
from src.engines.risk.stress import StressTester

router = APIRouter(prefix="/alpha/risk", tags=["Alpha: Risk"])

class VaRRequest(BaseModel):
    returns: list[float]
    confidence: float = 0.95
    horizon_days: int = 1
    portfolio_value: float = 1_000_000.0
    method: VaRMethod = VaRMethod.HISTORICAL

class StressRequest(BaseModel):
    portfolio_weights: dict[str, float]
    portfolio_value: float = 1_000_000.0
    custom_scenarios: list[StressScenario] = Field(default_factory=list)

class ReportRequest(BaseModel):
    returns: list[float]
    portfolio_value: float = 1_000_000.0
    confidence: float = 0.95
    horizon_days: int = 1
    portfolio_weights: dict[str, float] = Field(default_factory=dict)
    var_method: VaRMethod = VaRMethod.HISTORICAL

@router.post("/var")
async def compute_var(req: VaRRequest):
    try:
        if req.method == VaRMethod.HISTORICAL:
            return VaRCalculator.historical(req.returns, req.confidence, req.portfolio_value, req.horizon_days).model_dump()
        elif req.method == VaRMethod.MONTE_CARLO:
            return VaRCalculator.monte_carlo(req.returns, req.confidence, req.portfolio_value, req.horizon_days).model_dump()
        else:
            import numpy as np
            arr = np.array(req.returns)
            return VaRCalculator.parametric(float(np.mean(arr)), float(np.std(arr)),
                                            req.confidence, req.portfolio_value, req.horizon_days).model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/cvar")
async def compute_cvar(req: VaRRequest):
    try:
        return CVaRCalculator.historical(req.returns, req.confidence, req.portfolio_value).model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/stress")
async def stress_test(req: StressRequest):
    try:
        results = StressTester.run_all_builtin(req.portfolio_weights, req.portfolio_value)
        for s in req.custom_scenarios:
            results.append(StressTester.apply_scenario(req.portfolio_weights, s, req.portfolio_value))
        return {"results": [r.model_dump() for r in results]}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/report")
async def risk_report(req: ReportRequest):
    try:
        return RiskEngine.full_report(
            req.returns, req.portfolio_value, req.confidence, req.horizon_days,
            req.portfolio_weights or None, req.var_method,
        ).model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))
