"""
src/llm/types.py
─────────────────────────────────────────────────────────────────────────────
Enums, contracts, and Pydantic models for the LLM subsystem.

No LLM SDK imports here — pure data definitions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LLMTaskType(str, Enum):
    """Classification of LLM work that determines model selection.

    Agents declare WHAT they need, not WHICH model — the router decides.
    """
    REASONING = "reasoning"          # Deep analysis, CIO memos, committee synthesis
    FAST = "fast"                    # Agent memos, signal interpretation, extraction
    EXTRACTION = "extraction"        # JSON parsing, structured data extraction
    SYNTHESIS = "synthesis"          # Research summaries, narrative generation
    CODING = "coding"               # Code generation / analysis (future)
    FALLBACK_SAFE = "fallback_safe"  # Low-criticality: use cheapest available


class LLMProviderName(str, Enum):
    """Supported LLM provider backends."""
    GEMINI = "gemini"
    OPENAI = "openai"


class LLMSelection(BaseModel):
    """Result of the router's model selection."""
    provider: LLMProviderName
    model: str
    temperature: float = 0.3
    task_type: LLMTaskType
    is_fallback: bool = False


class LLMInvocationResult(BaseModel):
    """Structured result from an LLM invocation."""
    content: Any                                   # Raw LLM response object
    provider: LLMProviderName
    model: str
    task_type: LLMTaskType
    latency_ms: float = 0.0
    success: bool = True
    fallback_used: bool = False
    error: str | None = None
    error_type: str | None = None                  # Exception class name
    tokens_used: int | None = None                 # Total tokens (if available)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LLMMetrics(BaseModel):
    """Aggregated LLM usage metrics."""
    total_invocations: int = 0
    successful: int = 0
    failed: int = 0
    fallback_used: int = 0
    avg_latency_ms: float = 0.0
    total_tokens: int = 0
    by_task_type: dict[str, int] = Field(default_factory=dict)
    by_provider: dict[str, int] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)
