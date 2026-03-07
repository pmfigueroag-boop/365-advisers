"""
src/routes/strategy_lab.py
─────────────────────────────────────────────────────────────────────────────
Strategy Research Lab API — unified endpoints for the strategy lifecycle.
"""

from __future__ import annotations

import logging
from typing import Optional, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.engines.strategy.definition import StrategyDefinition, StrategyConfig, StrategyCreate
from src.engines.strategy.registry import StrategyRegistry
from src.engines.strategy.version_history import StrategyVersionHistory
from src.engines.strategy_research.orchestrator import StrategyOrchestrator
from src.engines.strategy_research.scorecard import StrategyScorecard
from src.engines.strategy_research.monitor import StrategyMonitor
from src.engines.strategy_research.learner import StrategyLearner
from src.engines.strategy_research.rules import RuleEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/strategy-lab", tags=["Strategy Lab"])

# Shared instances
_registry = StrategyRegistry()
_orchestrator = StrategyOrchestrator()
_learner = StrategyLearner()


# ── Request Models ───────────────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    strategy_id: str | None = None
    strategy_config: dict | None = None
    opportunities: list[dict] = Field(default_factory=list)
    current_regime: str = "unknown"
    run_backtest: bool = False


class CompareRequest(BaseModel):
    strategy_configs: list[dict]
    opportunities: list[dict] = Field(default_factory=list)
    current_regime: str = "unknown"


class EntryRuleTestRequest(BaseModel):
    opportunity: dict
    entry_rules: list[dict]


class ExitRuleTestRequest(BaseModel):
    position: dict
    exit_rules: list[dict]


class ScorecardRequest(BaseModel):
    backtest_result: dict | None = None
    signal_lab_report: dict | None = None
    stability_data: dict | None = None


# ── Strategy CRUD ────────────────────────────────────────────────────────────

@router.post("/strategies")
async def create_strategy(name: str, description: str = "", config: dict | None = None):
    """Create a new strategy."""
    strategy_id = _registry.create_strategy(name, description, config)
    return {"strategy_id": strategy_id, "status": "created"}


@router.get("/strategies")
async def list_strategies(active_only: bool = Query(True)):
    """List all strategies."""
    return _registry.list_strategies(active_only)


@router.get("/strategies/{strategy_id}")
async def get_strategy(strategy_id: str):
    """Get strategy details."""
    result = _registry.get_strategy(strategy_id)
    if not result:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return result


@router.post("/strategies/{strategy_id}/clone")
async def clone_strategy(strategy_id: str, new_name: str):
    """Clone a strategy."""
    new_id = _registry.clone_strategy(strategy_id, new_name)
    if not new_id:
        raise HTTPException(status_code=404, detail="Source strategy not found")
    return {"strategy_id": new_id, "status": "cloned"}


@router.get("/strategies/templates/predefined")
async def get_predefined_templates():
    """Get predefined strategy templates."""
    return _registry.get_predefined()


# ── Version History ──────────────────────────────────────────────────────────

@router.get("/strategies/{strategy_id}/versions")
async def get_version_history(strategy_id: str):
    """Get strategy version history."""
    return StrategyVersionHistory.get_version_history(strategy_id)


@router.get("/strategies/{strategy_id}/versions/{version}/compare/{version2}")
async def compare_versions(strategy_id: str, version: int, version2: int):
    """Compare two strategy versions."""
    return StrategyVersionHistory.compare_versions(strategy_id, version, version2)


# ── Research Pipeline ────────────────────────────────────────────────────────

@router.post("/research")
async def run_research(req: ResearchRequest):
    """Run the full strategy research pipeline."""
    result = _orchestrator.research(
        strategy_id=req.strategy_id,
        strategy_config=req.strategy_config,
        opportunities=req.opportunities,
        current_regime=req.current_regime,
        run_backtest=req.run_backtest,
    )
    return result


@router.post("/compare")
async def compare_strategies(req: CompareRequest):
    """Compare multiple strategies."""
    result = _orchestrator.compare_strategies(
        strategy_configs=req.strategy_configs,
        opportunities=req.opportunities,
        current_regime=req.current_regime,
    )
    return result


# ── Rule Engine ──────────────────────────────────────────────────────────────

@router.post("/rules/test-entry")
async def test_entry_rules(req: EntryRuleTestRequest):
    """Test entry rules against an opportunity."""
    return RuleEngine.evaluate_entry(req.opportunity, req.entry_rules)


@router.post("/rules/test-exit")
async def test_exit_rules(req: ExitRuleTestRequest):
    """Test exit rules against a position."""
    return RuleEngine.evaluate_exit(req.position, req.exit_rules)


@router.post("/rules/test-regime")
async def test_regime_rules(current_regime: str, regime_rules: list[dict]):
    """Test regime action for a given regime."""
    return RuleEngine.evaluate_regime(current_regime, regime_rules)


# ── Scorecard ────────────────────────────────────────────────────────────────

@router.post("/scorecard")
async def compute_scorecard(req: ScorecardRequest):
    """Compute strategy quality scorecard (0–100)."""
    return StrategyScorecard.compute(
        backtest_result=req.backtest_result,
        signal_lab_report=req.signal_lab_report,
        stability_data=req.stability_data,
    )


# ── Monitoring ───────────────────────────────────────────────────────────────

@router.get("/monitor/{strategy_id}")
async def get_strategy_status(strategy_id: str):
    """Get live strategy monitoring status."""
    return StrategyMonitor.get_status(strategy_id)


# ── Learning ─────────────────────────────────────────────────────────────────

@router.get("/learner/recommend")
async def get_recommendations(
    current_regime: str = Query("unknown"),
    top_n: int = Query(3, ge=1, le=10),
):
    """Get strategy recommendations for current regime."""
    return _learner.recommend(current_regime, top_n)


@router.get("/learner/regime-map")
async def get_regime_map():
    """Get learned regime → strategy mapping."""
    return _learner.get_regime_map()
