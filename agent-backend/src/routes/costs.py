"""
src/routes/costs.py
─────────────────────────────────────────────────────────────────────────────
LLM Cost monitoring API.

GET /api/costs          — Full cost report with budget status
GET /api/costs/budget   — Budget status only (for dashboards)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.services.cost_tracker import get_cost_report, should_downgrade_model

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/costs", tags=["Cost Management"], dependencies=[Depends(get_current_user)])


@router.get("/")
async def cost_report():
    """Full LLM cost report with model breakdown and budget status."""
    return get_cost_report()


@router.get("/budget")
async def budget_status():
    """Quick budget status check (for dashboard widgets)."""
    report = get_cost_report()
    return {
        "budget": report["budget"],
        "should_downgrade": should_downgrade_model(),
        "total_calls_today": report["summary"]["total_calls"],
    }
