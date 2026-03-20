"""
src/llm/provider.py
─────────────────────────────────────────────────────────────────────────────
Single entry point for all LLM access in the platform.

Public API:
    from src.llm import get_llm, LLMTaskType

    # Get a resilient model (fallback + instrumentation built-in)
    model = get_llm(LLMTaskType.FAST)
    result = model.invoke(prompt)     # ← returns AIMessage, just like before

    # Or use the structured invoke for programmatic access
    from src.llm import invoke_llm
    invocation = invoke_llm(prompt, LLMTaskType.REASONING)
    if invocation.success:
        print(invocation.content)
"""

from __future__ import annotations

import logging
from typing import Any

from src.config import get_settings
from src.llm.types import LLMInvocationResult, LLMProviderName, LLMTaskType

logger = logging.getLogger("365advisers.llm.provider")


def _get_api_keys() -> dict[str, str]:
    """Collect all API keys from centralized config."""
    settings = get_settings()
    keys: dict[str, str] = {}
    if settings.GOOGLE_API_KEY:
        keys[LLMProviderName.GEMINI.value] = settings.GOOGLE_API_KEY
    if settings.OPENAI_API_KEY:
        keys[LLMProviderName.OPENAI.value] = settings.OPENAI_API_KEY
    return keys


# ── Model cache ──────────────────────────────────────────────────────────────
# Each (task_type, temperature) combo is cached as a ResilientChatModel.
_model_cache: dict[str, Any] = {}


def _cache_key(task_type: str, temp: float) -> str:
    return f"{task_type}:{temp}"


def get_llm(task_type: LLMTaskType, temperature: float = 0.3) -> Any:
    """
    Get a ResilientChatModel for the given task type.

    Returns a drop-in replacement for BaseChatModel with built-in:
      - Error classification (recoverable vs non-recoverable)
      - One retry on transient errors before fallback
      - Automatic provider fallback (Gemini → OpenAI)
      - Per-invocation instrumentation (latency, tokens, fallback)

    Agents use this exactly like a normal LangChain model:
        model = get_llm(LLMTaskType.FAST)
        result = model.invoke(prompt)  # returns AIMessage

    Parameters
    ----------
    task_type : LLMTaskType
        What kind of work the agent needs to do.
    temperature : float
        Model temperature (default 0.3).

    Returns
    -------
    ResilientChatModel
        A resilient, instrumented wrapper around the selected model.
    """
    key = _cache_key(task_type.value, temperature)

    if key not in _model_cache:
        from src.llm.router import select, select_fallback
        from src.llm.factory import build_model
        from src.llm.wrapper import ResilientChatModel

        api_keys = _get_api_keys()

        # Primary model
        primary_sel = select(task_type, temperature)
        primary_model = build_model(primary_sel, api_keys)

        # Fallback model (optional)
        fallback_model = None
        fallback_sel = select_fallback(task_type)
        if fallback_sel:
            try:
                fallback_model = build_model(fallback_sel, api_keys)
            except (ValueError, ImportError) as exc:
                logger.warning("Fallback model unavailable: %s", exc)
                fallback_sel = None

        # Wrap in resilient proxy
        _model_cache[key] = ResilientChatModel(
            primary=primary_model,
            primary_selection=primary_sel,
            fallback=fallback_model,
            fallback_selection=fallback_sel,
            task_type=task_type,
        )

        fb_info = f" + fallback={fallback_sel.model}" if fallback_sel else ""
        logger.info(
            "LLM model created: %s/%s for task=%s%s",
            primary_sel.provider.value, primary_sel.model,
            task_type.value, fb_info,
        )

    return _model_cache[key]


def invoke_llm(
    prompt: str | Any,
    task_type: LLMTaskType,
    temperature: float = 0.3,
    raise_on_failure: bool = True,
    **kwargs,
) -> LLMInvocationResult:
    """
    Invoke an LLM with automatic routing, fallback, and instrumentation.

    Higher-level API that returns a structured LLMInvocationResult
    instead of a raw AIMessage.

    Parameters
    ----------
    prompt : str | Any
        The prompt to send to the LLM.
    task_type : LLMTaskType
        Task classification for model selection.
    temperature : float
        Model temperature.
    raise_on_failure : bool
        If True, raises the original exception when all models fail.
        If False, returns an LLMInvocationResult with success=False.
    **kwargs
        Extra arguments forwarded to model.invoke().

    Returns
    -------
    LLMInvocationResult
        Structured result with content, latency, provider, and fallback info.
    """
    import time
    from src.llm.wrapper import _extract_tokens

    model = get_llm(task_type, temperature)
    start = time.perf_counter()

    try:
        result = model.invoke(prompt, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        tokens = _extract_tokens(result)
        return LLMInvocationResult(
            content=result,
            provider=model._primary_sel.provider,
            model=model._primary_sel.model,
            task_type=task_type,
            latency_ms=round(elapsed, 1),
            success=True,
            tokens_used=tokens,
        )
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        if raise_on_failure:
            raise
        return LLMInvocationResult(
            content=None,
            provider=model._primary_sel.provider,
            model=model._primary_sel.model,
            task_type=task_type,
            latency_ms=round(elapsed, 1),
            success=False,
            error=str(exc),
            error_type=type(exc).__name__,
        )


def get_llm_metrics() -> dict:
    """Get aggregated LLM usage metrics (for monitoring endpoints)."""
    from src.llm.instrumentation import get_instruments
    return get_instruments().get_metrics().model_dump()


def clear_model_cache() -> None:
    """Clear the model cache (for testing)."""
    _model_cache.clear()
