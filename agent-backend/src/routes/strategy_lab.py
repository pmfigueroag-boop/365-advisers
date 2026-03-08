"""
src/routes/strategy_lab.py
─────────────────────────────────────────────────────────────────────────────
Strategy Research Lab API — unified endpoints for the strategy lifecycle.

Enhanced with:
  - Lifecycle state transitions
  - Category/tag filtering
  - YAML import/export
  - Execution mode routing (research/backtest/simulation/monitoring)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.engines.strategy.definition import (
    StrategyConfig,
    StrategyCategory,
    LifecycleState,
)
from src.engines.strategy.registry import StrategyRegistry
from src.engines.strategy.version_history import StrategyVersionHistory
from src.engines.strategy_research.orchestrator import StrategyOrchestrator
from src.engines.strategy_research.scorecard import StrategyScorecard
from src.engines.strategy_research.monitor import StrategyMonitor
from src.engines.strategy_research.learner import StrategyLearner
from src.engines.strategy_research.rules import RuleEngine
from src.engines.strategy_backtest.full_engine import StrategyBacktestEngine
from src.engines.strategy_backtest.comparator import StrategyComparator
from src.engines.strategy_backtest.walk_forward_strategy import WalkForwardStrategyValidator
from src.engines.strategy_backtest.benchmark import BenchmarkComparison

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/strategy-lab", tags=["Strategy Lab"])

# Shared instances
_registry = StrategyRegistry()
_orchestrator = StrategyOrchestrator()
_learner = StrategyLearner()


# ── Request Models ───────────────────────────────────────────────────────────

class CreateStrategyRequest(BaseModel):
    name: str
    description: str = ""
    config: dict | None = None
    version: str = "1.0.0"


class ResearchRequest(BaseModel):
    strategy_id: str | None = None
    strategy_config: dict | None = None
    opportunities: list[dict] = Field(default_factory=list)
    current_regime: str = "unknown"
    mode: str = "research"       # research | backtest | simulation
    run_backtest: bool = False   # Kept for backward compat
    initial_capital: float = 1_000_000.0


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


class TransitionRequest(BaseModel):
    target_state: str


# ── Strategy CRUD ────────────────────────────────────────────────────────────

@router.post("/strategies")
async def create_strategy(req: CreateStrategyRequest):
    """Create a new strategy."""
    strategy_id = _registry.create_strategy(
        req.name, req.description, req.config, req.version,
    )
    return {"strategy_id": strategy_id, "status": "created"}


@router.get("/strategies")
async def list_strategies(
    active_only: bool = Query(True),
    category: str | None = Query(None),
    lifecycle_state: str | None = Query(None),
    tags: str | None = Query(None, description="Comma-separated tags"),
):
    """List all strategies with optional filters."""
    tag_list = tags.split(",") if tags else None
    return _registry.list_strategies(
        active_only=active_only,
        category=category,
        lifecycle_state=lifecycle_state,
        tags=tag_list,
    )


@router.get("/strategies/templates/predefined")
async def get_predefined_templates():
    """Get predefined strategy templates (7 categories)."""
    return _registry.get_predefined()


@router.get("/strategies/categories")
async def get_categories():
    """Get available strategy categories."""
    return {
        "categories": [c.value for c in StrategyCategory],
        "lifecycle_states": [s.value for s in LifecycleState],
    }


@router.get("/strategies/{strategy_id}")
async def get_strategy(strategy_id: str):
    """Get strategy details."""
    result = _registry.get_strategy(strategy_id)
    if not result:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return result


@router.put("/strategies/{strategy_id}")
async def update_strategy(strategy_id: str, config: dict):
    """Update strategy configuration."""
    ok = _registry.update_strategy(strategy_id, config)
    if not ok:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"status": "updated"}


@router.post("/strategies/{strategy_id}/clone")
async def clone_strategy(strategy_id: str, new_name: str):
    """Clone a strategy."""
    new_id = _registry.clone_strategy(strategy_id, new_name)
    if not new_id:
        raise HTTPException(status_code=404, detail="Source strategy not found")
    return {"strategy_id": new_id, "status": "cloned"}


@router.delete("/strategies/{strategy_id}")
async def deactivate_strategy(strategy_id: str):
    """Deactivate a strategy."""
    ok = _registry.deactivate(strategy_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {"status": "deactivated"}


# ── Lifecycle ────────────────────────────────────────────────────────────────

@router.post("/strategies/{strategy_id}/transition")
async def transition_strategy(strategy_id: str, req: TransitionRequest):
    """Transition a strategy to a new lifecycle state."""
    result = _registry.transition(strategy_id, req.target_state)
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Transition failed"),
        )
    return result


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
    """Run the strategy research pipeline.

    Modes:
      - research: Signal/score filtering only (fast)
      - backtest: Full historical simulation
      - simulation: Connect to shadow portfolio
    """
    # Determine if backtest should run based on mode or explicit flag
    should_backtest = req.run_backtest or req.mode == "backtest"

    result = _orchestrator.research(
        strategy_id=req.strategy_id,
        strategy_config=req.strategy_config,
        opportunities=req.opportunities,
        current_regime=req.current_regime,
        run_backtest=should_backtest,
        initial_capital=req.initial_capital,
    )
    result["mode"] = req.mode
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


# ── Strategy Backtesting ─────────────────────────────────────────────────────

class FullBacktestRequest(BaseModel):
    strategy_config: dict
    data: dict  # BacktestDataBundle
    initial_capital: float = 1_000_000.0
    use_full_cost_model: bool = True
    cost_per_trade_bps: float = 5.0
    run_walk_forward: bool = False
    walk_forward_folds: int = 5


class CompareBacktestRequest(BaseModel):
    strategy_configs: list[dict]
    data: dict  # Shared BacktestDataBundle
    initial_capital: float = 1_000_000.0
    use_full_cost_model: bool = True


@router.post("/backtest")
async def run_full_backtest(req: FullBacktestRequest):
    """Run a full 8-stage strategy backtest.

    The pipeline: Signal Replay → Entry/Exit → Sizing → Portfolio →
    Cost Model → Metrics → Regime Analysis → Benchmark Comparison.
    """
    result = StrategyBacktestEngine.run(
        strategy_config=req.strategy_config,
        data=req.data,
        initial_capital=req.initial_capital,
        use_full_cost_model=req.use_full_cost_model,
        cost_per_trade_bps=req.cost_per_trade_bps,
    )

    if req.run_walk_forward and "error" not in result:
        try:
            # Build positions_by_date from result for walk-forward
            ec = result.get("equity_curve", [])
            ph = result.get("positions_history", [])
            if ph:
                positions_by_date = {}
                for snap in ph:
                    positions_by_date[snap["date"]] = snap.get("positions", [])
                wf = WalkForwardStrategyValidator.validate(
                    strategy_config=req.strategy_config,
                    positions_by_date=positions_by_date,
                    prices=req.data.get("prices", {}),
                    n_folds=req.walk_forward_folds,
                )
                result["walk_forward"] = wf
        except Exception as e:
            result["walk_forward"] = {"error": str(e)}

    return result


@router.post("/backtest/compare")
async def compare_backtests(req: CompareBacktestRequest):
    """Run backtests for multiple strategies and compare results."""
    results = []
    for config in req.strategy_configs:
        r = StrategyBacktestEngine.run(
            strategy_config=config,
            data=req.data,
            initial_capital=req.initial_capital,
            use_full_cost_model=req.use_full_cost_model,
        )
        results.append(r)

    comparison = StrategyComparator.compare(results)
    return comparison


@router.get("/backtest/benchmarks")
async def list_benchmarks():
    """List available benchmark definitions."""
    return BenchmarkComparison.list_benchmarks()


# ── Strategy Portfolio Lab ───────────────────────────────────────────────────

from src.engines.strategy_portfolio.engine import StrategyPortfolioEngine
from src.engines.strategy_portfolio.monitor import PortfolioMonitor


class PortfolioSimRequest(BaseModel):
    portfolio_config: dict  # StrategyPortfolio dict
    data: dict              # BacktestDataBundle
    initial_capital: float = 1_000_000.0
    use_full_cost_model: bool = True


class PortfolioCompareRequest(BaseModel):
    portfolio_configs: list[dict]
    data: dict
    initial_capital: float = 1_000_000.0


@router.post("/portfolio")
async def run_portfolio_simulation(req: PortfolioSimRequest):
    """Run a multi-strategy portfolio simulation (7-stage pipeline).

    Pipeline: Per-Strategy Backtest → Allocation → Position Merge →
    Constraints → Costs → Analytics → Diversification + Contribution.
    """
    result = StrategyPortfolioEngine.run(
        portfolio_config=req.portfolio_config,
        data=req.data,
        initial_capital=req.initial_capital,
        use_full_cost_model=req.use_full_cost_model,
    )
    return result


@router.post("/portfolio/compare")
async def compare_portfolios(req: PortfolioCompareRequest):
    """Compare multiple strategy portfolios side by side."""
    results = []
    for cfg in req.portfolio_configs:
        r = StrategyPortfolioEngine.run(
            portfolio_config=cfg,
            data=req.data,
            initial_capital=req.initial_capital,
        )
        results.append(r)

    # Build comparison table
    comparison = []
    for r in results:
        m = r.get("metrics", {})
        comparison.append({
            "name": r.get("portfolio_name", "unnamed"),
            "portfolio_id": r.get("portfolio_id"),
            "total_return": r.get("total_return", 0),
            "sharpe": m.get("sharpe_ratio", 0),
            "sortino": m.get("sortino_ratio", 0),
            "max_drawdown": m.get("max_drawdown", 0),
            "diversification_ratio": m.get("diversification_ratio", 0),
            "strategy_count": m.get("strategy_count", 0),
            "allocation_method": r.get("allocation_method"),
        })

    comparison.sort(key=lambda x: x.get("sharpe", 0), reverse=True)
    return {"portfolios": comparison, "count": len(comparison)}


@router.post("/portfolio/monitor")
async def monitor_portfolio(req: PortfolioSimRequest):
    """Run portfolio simulation and check health."""
    result = StrategyPortfolioEngine.run(
        portfolio_config=req.portfolio_config,
        data=req.data,
        initial_capital=req.initial_capital,
    )
    monitor_state = PortfolioMonitor.check(result)
    return monitor_state


@router.get("/portfolio/allocation-methods")
async def list_allocation_methods():
    """List available allocation methods."""
    return {
        "methods": [
            {"id": "equal", "name": "Equal Weight", "description": "1/N across strategies"},
            {"id": "risk_parity", "name": "Risk Parity", "description": "Inverse volatility weighting"},
            {"id": "mean_variance", "name": "Mean-Variance", "description": "Minimize variance (Markowitz)"},
            {"id": "sharpe_optimal", "name": "Sharpe Optimal", "description": "Maximize Sharpe ratio"},
            {"id": "regime_adaptive", "name": "Regime Adaptive", "description": "Weight by regime-specific Sharpe"},
            {"id": "momentum", "name": "Momentum", "description": "Overweight recent outperformers"},
        ]
    }


# ── Strategy AI Assistant ────────────────────────────────────────────────────

from src.engines.strategy_assistant.agent import StrategyAssistant

_assistant = StrategyAssistant()


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    context: dict | None = None


@router.post("/assistant/chat")
async def assistant_chat(req: ChatRequest):
    """Chat with the Strategy AI Assistant."""
    try:
        result = _assistant.chat(
            message=req.message,
            session_id=req.session_id,
            context=req.context,
        )
        return result
    except Exception as e:
        logger.error("Assistant chat failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/assistant/sessions")
async def list_sessions():
    """List active assistant chat sessions."""
    return {"sessions": _assistant.list_sessions()}


@router.delete("/assistant/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear a chat session."""
    _assistant.clear_session(session_id)
    return {"status": "cleared"}

