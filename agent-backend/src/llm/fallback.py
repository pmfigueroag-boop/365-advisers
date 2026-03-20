"""
src/llm/fallback.py
─────────────────────────────────────────────────────────────────────────────
Retry and provider failover policy.

Handles the try-primary → catch → try-fallback → catch → raise pattern
with structured error reporting.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.llm.types import LLMInvocationResult, LLMProviderName, LLMSelection, LLMTaskType

logger = logging.getLogger("365advisers.llm.fallback")


def invoke_with_fallback(
    primary_model: Any,
    primary_selection: LLMSelection,
    fallback_model: Any | None,
    fallback_selection: LLMSelection | None,
    prompt: str | Any,
    task_type: LLMTaskType,
    **kwargs,
) -> LLMInvocationResult:
    """
    Invoke primary model, fall back to secondary on failure.

    Parameters
    ----------
    primary_model : BaseChatModel
        The primary LLM instance.
    primary_selection : LLMSelection
        Metadata about the primary model.
    fallback_model : BaseChatModel | None
        Optional fallback LLM instance.
    fallback_selection : LLMSelection | None
        Metadata about the fallback model.
    prompt : str | Any
        The prompt to send to the LLM.
    task_type : LLMTaskType
        Task classification for instrumentation.
    **kwargs
        Extra arguments passed to model.invoke().

    Returns
    -------
    LLMInvocationResult
        Structured result with content, latency, and fallback metadata.

    Raises
    ------
    Exception
        The primary exception if both primary and fallback fail.
    """
    # ── Try primary ──────────────────────────────────────────────────────
    start = time.perf_counter()
    try:
        result = primary_model.invoke(prompt, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        return LLMInvocationResult(
            content=result,
            provider=primary_selection.provider,
            model=primary_selection.model,
            task_type=task_type,
            latency_ms=round(elapsed, 1),
            success=True,
            fallback_used=False,
        )
    except Exception as primary_exc:
        elapsed = (time.perf_counter() - start) * 1000
        logger.warning(
            "LLM primary failed [%s/%s] after %.0fms: %s",
            primary_selection.provider.value,
            primary_selection.model,
            elapsed,
            primary_exc,
        )

        if fallback_model is None or fallback_selection is None:
            return LLMInvocationResult(
                content=None,
                provider=primary_selection.provider,
                model=primary_selection.model,
                task_type=task_type,
                latency_ms=round(elapsed, 1),
                success=False,
                error=str(primary_exc),
            )

        # ── Try fallback ─────────────────────────────────────────────────
        fb_start = time.perf_counter()
        try:
            result = fallback_model.invoke(prompt, **kwargs)
            fb_elapsed = (time.perf_counter() - fb_start) * 1000
            logger.info(
                "LLM fallback succeeded [%s/%s] in %.0fms",
                fallback_selection.provider.value,
                fallback_selection.model,
                fb_elapsed,
            )
            return LLMInvocationResult(
                content=result,
                provider=fallback_selection.provider,
                model=fallback_selection.model,
                task_type=task_type,
                latency_ms=round(fb_elapsed, 1),
                success=True,
                fallback_used=True,
            )
        except Exception as fallback_exc:
            fb_elapsed = (time.perf_counter() - fb_start) * 1000
            logger.error(
                "LLM fallback also failed [%s/%s] after %.0fms: %s",
                fallback_selection.provider.value,
                fallback_selection.model,
                fb_elapsed,
                fallback_exc,
            )
            # Return failure result — caller decides whether to raise
            return LLMInvocationResult(
                content=None,
                provider=primary_selection.provider,
                model=primary_selection.model,
                task_type=task_type,
                latency_ms=round(elapsed + fb_elapsed, 1),
                success=False,
                fallback_used=True,
                error=f"Primary: {primary_exc} | Fallback: {fallback_exc}",
            )
