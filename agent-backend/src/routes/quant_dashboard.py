"""
src/routes/quant_dashboard.py
--------------------------------------------------------------------------
API endpoint for the Quant Dashboard — serves institutional metrics.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends

from pydantic import BaseModel, Field

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/quant", tags=["quant-dashboard"], dependencies=[Depends(get_current_user)])


class SignalHealthRow(BaseModel):
    signal_id: str
    health: str = "healthy"
    rolling_ic: float = 0.0
    half_life_days: float = 0.0
    weight_multiplier: float = 1.0
    events_count: int = 0


class PipelineStatusRow(BaseModel):
    step_name: str
    status: str = "success"
    duration_ms: float = 0.0


class QuantDashboardData(BaseModel):
    # Scorecard
    institutional_score: int = 92
    signal_validation: int = 100
    portfolio_construction: int = 93
    risk_management: int = 80
    execution: int = 65
    compliance: int = 65

    # Signal Health
    signals: list[SignalHealthRow] = Field(default_factory=list)
    active_kills: int = 0

    # Pipeline
    last_run: str = ""
    pipeline_steps: list[PipelineStatusRow] = Field(default_factory=list)

    # Portfolio
    portfolio_beta: float = 0.0
    portfolio_sharpe: float = 0.0
    total_positions: int = 0
    recent_turnover: float = 0.0

    # Providers
    providers_healthy: int = 0
    providers_total: int = 0


@router.get("/dashboard", response_model=QuantDashboardData)
async def get_quant_dashboard() -> QuantDashboardData:
    """Get all quant dashboard data in a single call."""
    # In production, this aggregates from live engines.
    # For now, return sensible defaults for the demo.
    return QuantDashboardData(
        signals=[
            SignalHealthRow(
                signal_id="sig.momentum",
                health="healthy",
                rolling_ic=0.08,
                half_life_days=12.5,
                events_count=347,
            ),
            SignalHealthRow(
                signal_id="sig.value",
                health="healthy",
                rolling_ic=0.05,
                half_life_days=28.0,
                events_count=215,
            ),
            SignalHealthRow(
                signal_id="sig.quality",
                health="flagged",
                rolling_ic=0.02,
                half_life_days=45.0,
                weight_multiplier=0.5,
                events_count=163,
            ),
        ],
        active_kills=0,
        last_run=datetime.now(timezone.utc).isoformat(),
        pipeline_steps=[
            PipelineStatusRow(step_name="Universe Selection", status="success", duration_ms=12),
            PipelineStatusRow(step_name="Signal Scanning", status="success", duration_ms=245),
            PipelineStatusRow(step_name="Validation", status="success", duration_ms=180),
            PipelineStatusRow(step_name="Kill Switch", status="success", duration_ms=8),
            PipelineStatusRow(step_name="Bridge", status="success", duration_ms=55),
            PipelineStatusRow(step_name="Shrinkage", status="success", duration_ms=22),
            PipelineStatusRow(step_name="Optimization", status="success", duration_ms=340),
            PipelineStatusRow(step_name="Neutralization", status="success", duration_ms=15),
            PipelineStatusRow(step_name="Rebalancing", status="success", duration_ms=28),
            PipelineStatusRow(step_name="Audit Trail", status="success", duration_ms=5),
            PipelineStatusRow(step_name="Report", status="success", duration_ms=95),
        ],
        portfolio_beta=0.02,
        portfolio_sharpe=1.45,
        total_positions=12,
        recent_turnover=0.08,
        providers_healthy=3,
        providers_total=3,
    )
