"""
src/engines/strategy_assistant/__init__.py
─────────────────────────────────────────────────────────────────────────────
Strategy AI Assistant — tool-calling agent for quantitative research.
"""

from .agent import StrategyAssistant, SYSTEM_PROMPT
from .tools import TOOL_REGISTRY, get_tool_descriptions

__all__ = [
    "StrategyAssistant",
    "SYSTEM_PROMPT",
    "TOOL_REGISTRY",
    "get_tool_descriptions",
]
