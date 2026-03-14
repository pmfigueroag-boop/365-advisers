"""
src/agents/mcp_server.py
─────────────────────────────────────────────────────────────────────────────
Model Context Protocol (MCP) server adapter.

Exposes 365 Advisers agent capabilities in a format compatible with
external AI orchestrators (Claude Desktop, Cursor, custom agents).

MCP Protocol Implementation:
  - Tool discovery via /mcp/tools/list
  - Tool execution via /mcp/tools/call
  - Resource listing via /mcp/resources/list
  - SSE transport for streaming responses
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.agents.registry import AgentRegistry
from src.agents.tools import TOOL_DECLARATIONS, execute_tool

logger = logging.getLogger("365advisers.mcp")

router = APIRouter(prefix="/mcp", tags=["MCP Server"])


# ── MCP Protocol Models ──────────────────────────────────────────────────────

class MCPToolCallRequest(BaseModel):
    """MCP tool/call request body."""
    name: str
    arguments: dict[str, Any] = {}


class MCPToolResult(BaseModel):
    """MCP tool/call response."""
    content: list[dict[str, Any]]
    isError: bool = False


# ── Server Info ───────────────────────────────────────────────────────────────

@router.get("/")
async def server_info():
    """MCP server capabilities advertisement."""
    return {
        "name": "365-advisers-mcp",
        "version": "1.0.0",
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {"listChanged": False},
            "resources": {"subscribe": False, "listChanged": False},
        },
        "serverInfo": {
            "name": "365 Advisers Investment Intelligence",
            "version": "3.5.0",
        },
    }


# ── Tool Discovery ───────────────────────────────────────────────────────────

@router.get("/tools/list")
async def list_tools():
    """
    List available tools (MCP protocol).

    Returns tool schemas in the MCP-compatible format so external
    orchestrators can discover what operations are available.
    """
    tools = []
    for decl in TOOL_DECLARATIONS:
        tools.append({
            "name": decl["name"],
            "description": decl["description"],
            "inputSchema": {
                "type": "object",
                "properties": decl["parameters"].get("properties", {}),
                "required": decl["parameters"].get("required", []),
            },
        })

    # Add agent invocation tools
    registry = AgentRegistry()
    for cap_dict in registry.list_capabilities():
        if cap_dict.get("is_autonomous"):
            tools.append({
                "name": f"invoke_{cap_dict['name']}",
                "description": f"Invoke the {cap_dict['name']} agent: {cap_dict['description']}",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Stock ticker symbol"},
                        "context": {"type": "string", "description": "Additional context"},
                    },
                    "required": ["ticker"],
                },
            })

    return {"tools": tools}


# ── Tool Execution ────────────────────────────────────────────────────────────

@router.post("/tools/call")
async def call_tool(request: MCPToolCallRequest):
    """
    Execute a tool call (MCP protocol).

    Supports both data tools (fetch_peer_comparison, etc.) and
    agent invocation tools (invoke_value_agent, etc.).
    """
    logger.info(f"MCP tool call: {request.name}({request.arguments})")

    # Check if it's an agent invocation
    if request.name.startswith("invoke_"):
        agent_name = request.name[7:]  # Remove "invoke_" prefix
        return await _invoke_agent(agent_name, request.arguments)

    # Execute data tool
    try:
        result = execute_tool(request.name, request.arguments)
        is_error = "error" in result

        return MCPToolResult(
            content=[{
                "type": "text",
                "text": json.dumps(result, default=str, indent=2),
            }],
            isError=is_error,
        )
    except Exception as exc:
        return MCPToolResult(
            content=[{"type": "text", "text": f"Error: {exc}"}],
            isError=True,
        )


async def _invoke_agent(agent_name: str, arguments: dict) -> MCPToolResult:
    """Invoke a registered agent via MCP."""
    registry = AgentRegistry()
    cap = registry.get(agent_name)

    if cap is None:
        return MCPToolResult(
            content=[{"type": "text", "text": f"Agent '{agent_name}' not found"}],
            isError=True,
        )

    ticker = arguments.get("ticker", "")
    if not ticker:
        return MCPToolResult(
            content=[{"type": "text", "text": "Missing required argument: ticker"}],
            isError=True,
        )

    # Return agent capability info (actual invocation requires full pipeline)
    return MCPToolResult(
        content=[{
            "type": "text",
            "text": json.dumps({
                "agent": agent_name,
                "ticker": ticker,
                "status": "capability_registered",
                "model": cap.model,
                "tools_available": cap.tools,
                "note": "Full agent invocation requires the analysis pipeline. "
                        "Use POST /api/analysis/stream?ticker=<ticker> for full analysis.",
            }, indent=2),
        }],
        isError=False,
    )


# ── Resource Discovery ────────────────────────────────────────────────────────

@router.get("/resources/list")
async def list_resources():
    """List available resources (MCP protocol)."""
    return {
        "resources": [
            {
                "uri": "365advisers://agents/registry",
                "name": "Agent Registry",
                "description": "Full list of AI agent capabilities",
                "mimeType": "application/json",
            },
            {
                "uri": "365advisers://system/health",
                "name": "System Health",
                "description": "Current system health status",
                "mimeType": "application/json",
            },
            {
                "uri": "365advisers://costs/current",
                "name": "LLM Cost Report",
                "description": "Current LLM usage costs and budget status",
                "mimeType": "application/json",
            },
        ],
    }


@router.get("/resources/read/{resource_path:path}")
async def read_resource(resource_path: str):
    """Read a specific resource (MCP protocol)."""
    if resource_path == "agents/registry":
        registry = AgentRegistry()
        return {
            "contents": [{
                "uri": "365advisers://agents/registry",
                "mimeType": "application/json",
                "text": json.dumps(registry.list_capabilities(), default=str),
            }],
        }
    elif resource_path == "system/health":
        from src.routes.health import health_check
        return {
            "contents": [{
                "uri": "365advisers://system/health",
                "mimeType": "application/json",
                "text": json.dumps(health_check(), default=str),
            }],
        }
    elif resource_path == "costs/current":
        from src.services.cost_tracker import get_cost_report
        return {
            "contents": [{
                "uri": "365advisers://costs/current",
                "mimeType": "application/json",
                "text": json.dumps(get_cost_report(), default=str),
            }],
        }
    else:
        raise HTTPException(404, f"Resource not found: {resource_path}")
