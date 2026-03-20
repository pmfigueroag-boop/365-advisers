"""
tests/test_llm_resilience.py
─────────────────────────────────────────────────────────────────────────────
Tests for the ResilientChatModel wrapper, error classification,
thread safety in instrumentation, and token tracking.

Validates:
  - Fallback fires through get_llm().invoke()
  - Non-recoverable errors do NOT trigger fallback
  - Instrumentation records from the live flow
  - Thread safety under concurrent access
  - Token extraction from AIMessage metadata
"""

import pytest
import threading
from unittest.mock import MagicMock, PropertyMock, patch
from src.llm.types import (
    LLMInvocationResult, LLMProviderName, LLMSelection, LLMTaskType,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Error Classification
# ═══════════════════════════════════════════════════════════════════════════════

class TestErrorClassification:

    def test_timeout_is_recoverable(self):
        from src.llm.wrapper import is_recoverable
        assert is_recoverable(TimeoutError("read timed out")) is True

    def test_connection_error_is_recoverable(self):
        from src.llm.wrapper import is_recoverable
        assert is_recoverable(ConnectionError("refused")) is True

    def test_os_error_is_recoverable(self):
        from src.llm.wrapper import is_recoverable
        assert is_recoverable(OSError("network unreachable")) is True

    def test_runtime_error_is_recoverable(self):
        from src.llm.wrapper import is_recoverable
        assert is_recoverable(RuntimeError("transient")) is True

    def test_value_error_is_not_recoverable(self):
        from src.llm.wrapper import is_recoverable
        assert is_recoverable(ValueError("invalid")) is False

    def test_type_error_is_not_recoverable(self):
        from src.llm.wrapper import is_recoverable
        assert is_recoverable(TypeError("wrong type")) is False

    def test_key_error_is_not_recoverable(self):
        from src.llm.wrapper import is_recoverable
        assert is_recoverable(KeyError("missing")) is False

    def test_auth_error_by_name(self):
        """Exception classes named AuthenticationError should not fallback."""
        from src.llm.wrapper import is_recoverable

        class AuthenticationError(Exception):
            pass

        assert is_recoverable(AuthenticationError("bad key")) is False

    def test_bad_request_by_name(self):
        from src.llm.wrapper import is_recoverable

        class BadRequestError(Exception):
            pass

        assert is_recoverable(BadRequestError("invalid prompt")) is False


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ResilientChatModel — Fallback Behavior
# ═══════════════════════════════════════════════════════════════════════════════

def _make_wrapper(primary_side_effect=None, fallback_side_effect=None):
    """Build a ResilientChatModel with mocked primary and fallback."""
    from src.llm.wrapper import ResilientChatModel

    primary = MagicMock()
    if primary_side_effect:
        primary.invoke.side_effect = primary_side_effect
    else:
        primary.invoke.return_value = MagicMock(content="primary_ok")

    fallback = MagicMock()
    if fallback_side_effect:
        fallback.invoke.side_effect = fallback_side_effect
    else:
        fallback.invoke.return_value = MagicMock(content="fallback_ok")

    p_sel = LLMSelection(
        provider=LLMProviderName.GEMINI, model="gemini-test",
        task_type=LLMTaskType.FAST,
    )
    f_sel = LLMSelection(
        provider=LLMProviderName.OPENAI, model="gpt-test",
        task_type=LLMTaskType.FAST, is_fallback=True,
    )

    wrapper = ResilientChatModel(
        primary=primary, primary_selection=p_sel,
        fallback=fallback, fallback_selection=f_sel,
        task_type=LLMTaskType.FAST,
        retry_delay_s=0.01,  # Fast for tests
    )
    return wrapper, primary, fallback


class TestResilientChatModel:

    def setup_method(self):
        from src.llm.instrumentation import get_instruments
        get_instruments().reset()

    def test_primary_succeeds_no_fallback(self):
        wrapper, primary, fallback = _make_wrapper()
        result = wrapper.invoke("hello")
        assert result.content == "primary_ok"
        primary.invoke.assert_called_once()
        fallback.invoke.assert_not_called()

    def test_recoverable_error_triggers_retry_then_fallback(self):
        wrapper, primary, fallback = _make_wrapper(
            primary_side_effect=ConnectionError("refused"),
        )
        result = wrapper.invoke("hello")
        assert result.content == "fallback_ok"
        # Primary called twice (original + retry), then fallback once
        assert primary.invoke.call_count == 2
        fallback.invoke.assert_called_once()

    def test_non_recoverable_error_does_not_fallback(self):
        wrapper, primary, fallback = _make_wrapper(
            primary_side_effect=ValueError("bad prompt"),
        )
        with pytest.raises(ValueError, match="bad prompt"):
            wrapper.invoke("hello")
        primary.invoke.assert_called_once()
        fallback.invoke.assert_not_called()

    def test_retry_success_skips_fallback(self):
        """Primary fails once, succeeds on retry."""
        call_count = [0]

        def _side_effect(prompt, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                raise TimeoutError("transient")
            return MagicMock(content="retry_ok")

        wrapper, primary, fallback = _make_wrapper(
            primary_side_effect=_side_effect,
        )
        result = wrapper.invoke("hello")
        assert result.content == "retry_ok"
        assert primary.invoke.call_count == 2
        fallback.invoke.assert_not_called()

    def test_all_fail_raises_primary_exc(self):
        wrapper, primary, fallback = _make_wrapper(
            primary_side_effect=TimeoutError("gemini down"),
            fallback_side_effect=TimeoutError("openai down"),
        )
        with pytest.raises(TimeoutError, match="gemini down"):
            wrapper.invoke("hello")

    def test_no_fallback_model_raises_on_failure(self):
        from src.llm.wrapper import ResilientChatModel

        primary = MagicMock()
        primary.invoke.side_effect = ConnectionError("down")
        p_sel = LLMSelection(
            provider=LLMProviderName.GEMINI, model="gemini-test",
            task_type=LLMTaskType.FAST,
        )

        wrapper = ResilientChatModel(
            primary=primary, primary_selection=p_sel,
            fallback=None, fallback_selection=None,
            task_type=LLMTaskType.FAST,
            retry_delay_s=0.01,
        )
        with pytest.raises(ConnectionError, match="down"):
            wrapper.invoke("hello")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Instrumentation from Live Flow
# ═══════════════════════════════════════════════════════════════════════════════

class TestInstrumentationFromLiveFlow:

    def setup_method(self):
        from src.llm.instrumentation import get_instruments
        get_instruments().reset()

    def test_success_recorded(self):
        from src.llm.instrumentation import get_instruments
        wrapper, _, _ = _make_wrapper()
        wrapper.invoke("hello")
        metrics = get_instruments().get_metrics()
        assert metrics.total_invocations == 1
        assert metrics.successful == 1
        assert metrics.failed == 0

    def test_fallback_recorded(self):
        from src.llm.instrumentation import get_instruments
        wrapper, _, _ = _make_wrapper(
            primary_side_effect=TimeoutError("down"),
        )
        wrapper.invoke("hello")
        metrics = get_instruments().get_metrics()
        assert metrics.total_invocations == 1
        assert metrics.fallback_used == 1

    def test_failure_recorded(self):
        from src.llm.instrumentation import get_instruments
        wrapper, _, _ = _make_wrapper(
            primary_side_effect=ValueError("bad"),
        )
        with pytest.raises(ValueError):
            wrapper.invoke("hello")
        metrics = get_instruments().get_metrics()
        assert metrics.failed == 1
        assert len(metrics.errors) == 1
        assert metrics.errors[0]["error_type"] == "ValueError"

    def test_by_task_type_tracked(self):
        from src.llm.instrumentation import get_instruments
        wrapper, _, _ = _make_wrapper()
        wrapper.invoke("hello")
        metrics = get_instruments().get_metrics()
        assert "fast" in metrics.by_task_type


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Thread Safety
# ═══════════════════════════════════════════════════════════════════════════════

class TestThreadSafety:

    def test_concurrent_recording(self):
        from src.llm.instrumentation import LLMInstruments

        inst = LLMInstruments()
        n_threads = 20
        n_per_thread = 100

        def _record_n():
            for _ in range(n_per_thread):
                inst.record(LLMInvocationResult(
                    content=None, provider=LLMProviderName.GEMINI,
                    model="test", task_type=LLMTaskType.FAST,
                    success=True, latency_ms=10,
                ))

        threads = [threading.Thread(target=_record_n) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        metrics = inst.get_metrics()
        assert metrics.total_invocations == n_threads * n_per_thread
        assert metrics.successful == n_threads * n_per_thread

    def test_has_lock(self):
        from src.llm.instrumentation import LLMInstruments
        inst = LLMInstruments()
        assert hasattr(inst, "_lock")
        assert isinstance(inst._lock, type(threading.Lock()))


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Token Tracking
# ═══════════════════════════════════════════════════════════════════════════════

class TestTokenTracking:

    def test_extract_tokens_from_usage_metadata(self):
        from src.llm.wrapper import _extract_tokens
        msg = MagicMock()
        msg.usage_metadata = MagicMock(total_tokens=150, input_tokens=100, output_tokens=50)
        assert _extract_tokens(msg) == 150

    def test_extract_tokens_from_response_metadata(self):
        from src.llm.wrapper import _extract_tokens
        msg = MagicMock(spec=[])  # No usage_metadata
        msg.response_metadata = {"token_usage": {"total_tokens": 200}}
        assert _extract_tokens(msg) == 200

    def test_extract_tokens_returns_none_when_missing(self):
        from src.llm.wrapper import _extract_tokens
        msg = MagicMock(spec=[])  # No usage_metadata, no response_metadata
        assert _extract_tokens(msg) is None

    def test_total_tokens_in_metrics(self):
        from src.llm.instrumentation import get_instruments
        get_instruments().reset()

        # Mock a response with tokens
        wrapper, primary, _ = _make_wrapper()
        response = MagicMock(content="ok")
        response.usage_metadata = MagicMock(total_tokens=100, input_tokens=60, output_tokens=40)
        primary.invoke.return_value = response

        wrapper.invoke("hello")
        metrics = get_instruments().get_metrics()
        assert metrics.total_tokens == 100

    def test_tokens_in_invocation_result(self):
        result = LLMInvocationResult(
            content=None, provider=LLMProviderName.GEMINI,
            model="test", task_type=LLMTaskType.FAST,
            tokens_used=250,
        )
        assert result.tokens_used == 250


# ═══════════════════════════════════════════════════════════════════════════════
# 6. get_llm() Returns ResilientChatModel
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetLLMReturnsWrapped:

    def test_returns_resilient_model(self):
        from src.llm import get_llm, LLMTaskType
        from src.llm.wrapper import ResilientChatModel
        model = get_llm(LLMTaskType.FAST)
        assert isinstance(model, ResilientChatModel)

    def test_has_invoke_method(self):
        from src.llm import get_llm, LLMTaskType
        model = get_llm(LLMTaskType.FAST)
        assert hasattr(model, "invoke")
        assert hasattr(model, "ainvoke")

    def test_repr_shows_task_type(self):
        from src.llm import get_llm, LLMTaskType
        model = get_llm(LLMTaskType.FAST)
        r = repr(model)
        assert "fast" in r
        assert "Resilient" in r


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Backward Compatibility
# ═══════════════════════════════════════════════════════════════════════════════

class TestBackwardCompat:

    def test_existing_test_imports_still_work(self):
        from src.llm import get_llm, invoke_llm, LLMTaskType, clear_model_cache
        assert callable(get_llm)
        assert callable(invoke_llm)
        assert callable(clear_model_cache)

    def test_legacy_shim_still_works(self):
        from src.services.llm_provider import get_llm_provider
        provider = get_llm_provider()
        assert hasattr(provider, "invoke")

    def test_llm_metrics_has_total_tokens(self):
        from src.llm import get_llm_metrics
        m = get_llm_metrics()
        assert "total_tokens" in m
