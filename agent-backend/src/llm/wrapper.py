"""
src/llm/wrapper.py
─────────────────────────────────────────────────────────────────────────────
ResilientChatModel — drop-in proxy that adds fallback + instrumentation
to any LangChain BaseChatModel, transparently.

Agents call:
    model = get_llm(LLMTaskType.FAST)
    result = model.invoke(prompt)          # ← returns AIMessage as before

Internally, the wrapper:
  1. Classifies errors as recoverable vs non-recoverable
  2. Retries once on transient errors (timeout, rate limit)
  3. Falls back to secondary provider on persistent recoverable errors
  4. Instruments every invocation (latency, provider, tokens, fallback)
  5. Returns the raw AIMessage to the caller — fully transparent

Zero consumer code changes required.
"""

from __future__ import annotations

import asyncio
import logging
import time
import threading
from typing import Any

from src.llm.types import LLMInvocationResult, LLMSelection, LLMTaskType

logger = logging.getLogger("365advisers.llm.wrapper")


# ── Error Classification ─────────────────────────────────────────────────────

# Exception class names / substrings that signal non-recoverable errors.
# These should NEVER trigger fallback — they indicate config or code bugs.
_NON_RECOVERABLE_MARKERS = frozenset({
    "AuthenticationError",
    "PermissionDeniedError",
    "InvalidRequestError",
    "BadRequestError",
    "NotFoundError",
    "ValueError",
    "TypeError",
    "KeyError",
    "ValidationError",
    "JSONDecodeError",
    "SyntaxError",
})

# HTTP status codes that are non-recoverable
_NON_RECOVERABLE_STATUS = frozenset({400, 401, 403, 404})

# HTTP status codes that ARE recoverable (should retry then fallback)
_RECOVERABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


def is_recoverable(exc: Exception) -> bool:
    """
    Classify an exception as recoverable (should fallback) or not.

    Recoverable:
      - TimeoutError, ConnectionError, OSError (network)
      - HTTP 429 (rate limit), 500/502/503/504 (server errors)
      - Generic RuntimeError (unknown — assume transient)

    Non-recoverable:
      - AuthenticationError, PermissionDenied (config bugs)
      - BadRequest, InvalidRequest (prompt/schema bugs)
      - ValueError, TypeError, KeyError (programming errors)
    """
    exc_type_name = type(exc).__name__

    # Check by exception type name
    if exc_type_name in _NON_RECOVERABLE_MARKERS:
        return False

    # Check by base class
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return False

    # Network errors are always recoverable
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True

    # Check for HTTP status code in exception message or attributes
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status:
        if status in _NON_RECOVERABLE_STATUS:
            return False
        if status in _RECOVERABLE_STATUS:
            return True

    # Check exception message for status codes
    exc_str = str(exc)
    for code in _NON_RECOVERABLE_STATUS:
        if f"{code}" in exc_str and any(
            marker in exc_str.lower()
            for marker in ("bad request", "unauthorized", "forbidden", "not found")
        ):
            return False

    # Default: assume recoverable (safer — try fallback rather than crash)
    return True


def _extract_tokens(response: Any) -> int | None:
    """Extract token count from a LangChain AIMessage response."""
    if response is None:
        return None

    # LangChain >= 0.2: usage_metadata
    usage = getattr(response, "usage_metadata", None)
    if usage:
        total = getattr(usage, "total_tokens", None)
        if total is not None:
            return int(total)
        # Fallback: sum input + output
        inp = getattr(usage, "input_tokens", 0) or 0
        out = getattr(usage, "output_tokens", 0) or 0
        if inp or out:
            return inp + out

    # OpenAI-style: response_metadata.token_usage
    resp_meta = getattr(response, "response_metadata", None)
    if resp_meta and isinstance(resp_meta, dict):
        token_usage = resp_meta.get("token_usage") or resp_meta.get("usage")
        if token_usage and isinstance(token_usage, dict):
            total = token_usage.get("total_tokens")
            if total is not None:
                return int(total)

    return None


class ResilientChatModel:
    """
    Drop-in proxy for LangChain BaseChatModel with built-in resilience.

    Agents use this exactly like a normal model:
        result = model.invoke(prompt)  # returns AIMessage

    Internally adds:
      - Error classification (recoverable vs non-recoverable)
      - One retry on transient errors before fallback
      - Provider fallback on persistent recoverable errors
      - Per-invocation instrumentation (latency, tokens, fallback)
    """

    def __init__(
        self,
        primary: Any,
        primary_selection: LLMSelection,
        fallback: Any | None = None,
        fallback_selection: LLMSelection | None = None,
        task_type: LLMTaskType = LLMTaskType.FAST,
        retry_delay_s: float = 1.0,
    ):
        self._primary = primary
        self._primary_sel = primary_selection
        self._fallback = fallback
        self._fallback_sel = fallback_selection
        self._task_type = task_type
        self._retry_delay = retry_delay_s

    def invoke(self, prompt: str | Any, **kwargs) -> Any:
        """
        Invoke with resilience. Returns AIMessage (same as BaseChatModel).

        Flow:
          1. Try primary
          2. On recoverable error: retry once after delay
          3. On second failure: try fallback (if available)
          4. On non-recoverable error: raise immediately
          5. Record instrumentation as side-effect
        """
        from src.llm.instrumentation import get_instruments

        start = time.perf_counter()
        _saved_exc: Exception | None = None  # Persists across except blocks

        # ── Attempt 1: Primary ───────────────────────────────────────────
        try:
            result = self._primary.invoke(prompt, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            self._record(result, elapsed, fallback_used=False)
            return result
        except Exception as first_exc:
            _saved_exc = first_exc  # Save before Python 3 deletes it
            elapsed = (time.perf_counter() - start) * 1000

            if not is_recoverable(first_exc):
                logger.warning(
                    "LLM non-recoverable error [%s/%s]: %s — NOT falling back",
                    self._primary_sel.provider.value,
                    self._primary_sel.model,
                    type(first_exc).__name__,
                )
                self._record_failure(elapsed, first_exc, fallback_used=False)
                raise

            logger.warning(
                "LLM recoverable error [%s/%s] after %.0fms: %s — retrying",
                self._primary_sel.provider.value,
                self._primary_sel.model,
                elapsed,
                first_exc,
            )

        # ── Attempt 2: Retry primary after delay ─────────────────────────
        time.sleep(self._retry_delay)
        retry_start = time.perf_counter()
        try:
            result = self._primary.invoke(prompt, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000
            self._record(result, elapsed, fallback_used=False)
            return result
        except Exception as retry_exc:
            retry_elapsed = (time.perf_counter() - retry_start) * 1000
            logger.warning(
                "LLM retry failed [%s/%s] after %.0fms: %s",
                self._primary_sel.provider.value,
                self._primary_sel.model,
                retry_elapsed,
                retry_exc,
            )

        # ── Attempt 3: Fallback provider ─────────────────────────────────
        if self._fallback is None:
            total = (time.perf_counter() - start) * 1000
            self._record_failure(total, _saved_exc, fallback_used=False)
            raise _saved_exc

        fb_start = time.perf_counter()
        try:
            result = self._fallback.invoke(prompt, **kwargs)
            fb_elapsed = (time.perf_counter() - fb_start) * 1000
            total = (time.perf_counter() - start) * 1000
            logger.info(
                "LLM fallback succeeded [%s/%s] in %.0fms (total %.0fms)",
                self._fallback_sel.provider.value,
                self._fallback_sel.model,
                fb_elapsed,
                total,
            )
            self._record(
                result, total, fallback_used=True,
                actual_provider=self._fallback_sel.provider,
                actual_model=self._fallback_sel.model,
            )
            return result
        except Exception as fb_exc:
            total = (time.perf_counter() - start) * 1000
            logger.error(
                "LLM all attempts exhausted: primary(%s) + retry + fallback(%s) — total %.0fms",
                self._primary_sel.model,
                self._fallback_sel.model if self._fallback_sel else "none",
                total,
            )
            self._record_failure(
                total, _saved_exc, fallback_used=True,
                fallback_error=str(fb_exc),
            )
            raise _saved_exc from fb_exc

    async def ainvoke(self, prompt: str | Any, **kwargs) -> Any:
        """Async version — delegates to invoke via thread pool."""
        return await asyncio.to_thread(self.invoke, prompt, **kwargs)

    # ── Instrumentation helpers ──────────────────────────────────────────

    def _record(
        self,
        response: Any,
        latency_ms: float,
        fallback_used: bool,
        actual_provider=None,
        actual_model=None,
    ) -> None:
        from src.llm.instrumentation import get_instruments
        tokens = _extract_tokens(response)
        get_instruments().record(LLMInvocationResult(
            content=None,  # Don't store full response in metrics
            provider=actual_provider or self._primary_sel.provider,
            model=actual_model or self._primary_sel.model,
            task_type=self._task_type,
            latency_ms=round(latency_ms, 1),
            success=True,
            fallback_used=fallback_used,
            tokens_used=tokens,
        ))

    def _record_failure(
        self,
        latency_ms: float,
        error: Exception,
        fallback_used: bool,
        fallback_error: str | None = None,
    ) -> None:
        from src.llm.instrumentation import get_instruments
        error_str = str(error)
        if fallback_error:
            error_str = f"Primary: {error} | Fallback: {fallback_error}"
        get_instruments().record(LLMInvocationResult(
            content=None,
            provider=self._primary_sel.provider,
            model=self._primary_sel.model,
            task_type=self._task_type,
            latency_ms=round(latency_ms, 1),
            success=False,
            fallback_used=fallback_used,
            error=error_str,
            error_type=type(error).__name__,
        ))

    # ── Transparency for LangGraph/LangChain ─────────────────────────────

    def __getattr__(self, name: str) -> Any:
        """Proxy any unknown attribute to the primary model.

        This ensures compatibility with LangGraph/LangChain internals
        that may inspect model attributes like `model_name`, `_llm_type`, etc.
        """
        return getattr(self._primary, name)

    def __repr__(self) -> str:
        fb = f" + {self._fallback_sel.model}" if self._fallback_sel else ""
        return (
            f"ResilientChatModel("
            f"{self._primary_sel.provider.value}/{self._primary_sel.model}"
            f"{fb}, task={self._task_type.value})"
        )
