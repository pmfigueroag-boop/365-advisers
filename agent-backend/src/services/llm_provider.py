"""
src/services/llm_provider.py
─────────────────────────────────────────────────────────────────────────────
BACKWARD-COMPATIBILITY SHIM — redirects to src.llm.

All new code should import from src.llm directly:
    from src.llm import get_llm, LLMTaskType

This shim exists so existing imports don't break:
    from src.services.llm_provider import get_llm_provider  # still works
"""

from src.llm import get_llm, LLMTaskType
from src.llm.provider import get_llm_metrics


class LLMProvider:
    """Backward-compatible wrapper — delegates to src.llm."""

    def __init__(self):
        self._model = get_llm(LLMTaskType.REASONING)
        self._primary_name = f"gemini/{LLMTaskType.REASONING.value}"

    def invoke(self, prompt, **kwargs):
        return self._model.invoke(prompt, **kwargs)

    @property
    def primary_name(self) -> str:
        return self._primary_name

    @property
    def fallback_name(self):
        return None

    @property
    def has_fallback(self) -> bool:
        return False


def get_llm_provider() -> LLMProvider:
    """Legacy entry point — use src.llm.get_llm() instead."""
    return LLMProvider()
