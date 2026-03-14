"""
src/agents — Agent Capability Registry & Tools

Public API:
    AgentRegistry      — Singleton registry of all agent capabilities
    AgentCapability    — Data model for agent capabilities
    TOOL_DECLARATIONS  — Gemini function-calling tool schemas
    execute_tool       — Execute a tool call by name
"""

from src.agents.registry import AgentRegistry, AgentCapability
from src.agents.tools import TOOL_DECLARATIONS, execute_tool

__all__ = [
    "AgentRegistry",
    "AgentCapability",
    "TOOL_DECLARATIONS",
    "execute_tool",
]
