"""src/routes/compliance.py — Compliance Rule Engine API."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from src.engines.compliance.models import ComplianceRule, RuleType
from src.engines.compliance.engine import ComplianceEngine

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/alpha/compliance", tags=["Alpha: Compliance"], dependencies=[Depends(get_current_user)])
_engine = ComplianceEngine()

class ComplianceCheckRequest(BaseModel):
    weights: dict[str, float] | None = None
    positions: dict[str, float] | None = None
    sector_weights: dict[str, float] | None = None
    gross_exposure: float = 1.0
    trades: list[dict] | None = None
    trades_today: int = 0

class AddRuleRequest(BaseModel):
    rule_id: str
    rule_type: RuleType
    description: str = ""
    params: dict = Field(default_factory=dict)

@router.post("/check")
async def run_compliance(req: ComplianceCheckRequest):
    return _engine.run_all(
        req.weights, req.positions, req.sector_weights,
        req.gross_exposure, req.trades, req.trades_today,
    ).model_dump()

@router.get("/rules")
async def list_rules():
    return {"rules": [r.model_dump() for r in _engine.rules]}

@router.post("/rules")
async def add_rule(req: AddRuleRequest):
    rule = ComplianceRule(rule_id=req.rule_id, rule_type=req.rule_type, description=req.description, params=req.params)
    _engine.add_rule(rule)
    return {"status": "added", "rule_id": rule.rule_id}

@router.delete("/rules/{rule_id}")
async def remove_rule(rule_id: str):
    _engine.remove_rule(rule_id)
    return {"status": "removed", "rule_id": rule_id}
