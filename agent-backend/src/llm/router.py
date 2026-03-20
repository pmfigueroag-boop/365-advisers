"""
src/llm/router.py
─────────────────────────────────────────────────────────────────────────────
Task-type routing — maps what an agent NEEDS to which model serves it.

The router reads model names from centralized config, so changing the
default model for all "fast" tasks is a single env var change.
"""

from __future__ import annotations

import logging

from src.config import get_settings
from src.llm.types import LLMProviderName, LLMSelection, LLMTaskType

logger = logging.getLogger("365advisers.llm.router")


# ── Default routing table ────────────────────────────────────────────────────
# Maps each task type to (provider, config_attr_for_model)
# The actual model name comes from Settings at runtime.

_TASK_ROUTING: dict[LLMTaskType, tuple[LLMProviderName, str]] = {
    LLMTaskType.REASONING:     (LLMProviderName.GEMINI, "LLM_REASONING_MODEL"),
    LLMTaskType.FAST:          (LLMProviderName.GEMINI, "LLM_FAST_MODEL"),
    LLMTaskType.EXTRACTION:    (LLMProviderName.GEMINI, "LLM_FAST_MODEL"),
    LLMTaskType.SYNTHESIS:     (LLMProviderName.GEMINI, "LLM_REASONING_MODEL"),
    LLMTaskType.CODING:        (LLMProviderName.GEMINI, "LLM_REASONING_MODEL"),
    LLMTaskType.FALLBACK_SAFE: (LLMProviderName.GEMINI, "LLM_FAST_MODEL"),
}


def select(task_type: LLMTaskType, temperature: float = 0.3) -> LLMSelection:
    """
    Select the best model for a given task type.

    Parameters
    ----------
    task_type : LLMTaskType
        The kind of work the agent needs to do.
    temperature : float
        LLM temperature override (default 0.3).

    Returns
    -------
    LLMSelection
        Provider + model + config to build the model.
    """
    settings = get_settings()
    provider, model_attr = _TASK_ROUTING[task_type]
    model_name = getattr(settings, model_attr)

    return LLMSelection(
        provider=provider,
        model=model_name,
        temperature=temperature,
        task_type=task_type,
    )


def select_fallback(task_type: LLMTaskType) -> LLMSelection | None:
    """
    Select the fallback model for a given task type.

    Returns None if fallback is disabled or no OpenAI key is configured.
    """
    settings = get_settings()

    if not settings.LLM_FALLBACK_ENABLED or not settings.OPENAI_API_KEY:
        return None

    return LLMSelection(
        provider=LLMProviderName.OPENAI,
        model=settings.LLM_FALLBACK_MODEL,
        temperature=0.3,
        task_type=task_type,
        is_fallback=True,
    )
