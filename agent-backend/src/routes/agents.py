"""
src/routes/agents.py
─────────────────────────────────────────────────────────────────────────────
Agent Registry API — exposes agent capabilities for external orchestrators.

GET /api/agents/capabilities  — Full capability manifest (MCP-compatible)
GET /api/agents/summary       — Summary statistics
GET /api/agents/{name}/schema — Schema for a specific agent
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.agents.registry import AgentRegistry
from src.agents.tools import TOOL_DECLARATIONS

from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/agents", tags=["Agent Registry"], dependencies=[Depends(get_current_user)])


@router.get("/capabilities")
async def list_capabilities():
    """
    Return the full agent capability manifest.

    This is designed to be consumed by external orchestrators (MCP-compatible)
    to discover what the 365 Advisers platform can do autonomously.
    """
    registry = AgentRegistry()
    return {
        "version": "1.0",
        "protocol": "MCP-compatible",
        "capabilities": registry.list_capabilities(),
        "available_tools": TOOL_DECLARATIONS,
    }


@router.get("/summary")
async def agent_summary():
    """Return summary statistics for the agent registry."""
    registry = AgentRegistry()
    return registry.summary()


@router.get("/{agent_name}/schema")
async def agent_schema(agent_name: str):
    """Return the full schema for a specific agent."""
    registry = AgentRegistry()
    cap = registry.get(agent_name)
    if cap is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_name}' not found. Use /api/agents/capabilities to list all agents.",
        )
    return cap.model_dump()
