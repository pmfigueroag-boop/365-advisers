"""
src/llm/__init__.py
─────────────────────────────────────────────────────────────────────────────
LLM Subsystem — single entry point for all LLM access.

Usage:
    from src.llm import get_llm, invoke_llm, LLMTaskType

    # Raw model for LangGraph / chains
    model = get_llm(LLMTaskType.FAST)

    # Instrumented invocation with fallback
    result = invoke_llm("Analyze AAPL", LLMTaskType.REASONING)
"""

from src.llm.types import (
    LLMTaskType,
    LLMProviderName,
    LLMSelection,
    LLMInvocationResult,
    LLMMetrics,
)
from src.llm.provider import (
    get_llm,
    invoke_llm,
    get_llm_metrics,
    clear_model_cache,
)
from src.llm.wrapper import ResilientChatModel, is_recoverable

__all__ = [
    "LLMTaskType",
    "LLMProviderName",
    "LLMSelection",
    "LLMInvocationResult",
    "LLMMetrics",
    "ResilientChatModel",
    "is_recoverable",
    "get_llm",
    "invoke_llm",
    "get_llm_metrics",
    "clear_model_cache",
]
