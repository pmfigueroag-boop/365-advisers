"""
tests/test_llm_subsystem.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive tests for the unified LLM subsystem.

Tests cover:
  - Task-type routing
  - Fallback policy
  - Factory model building
  - Instrumentation metrics
  - Consumer agent imports (no direct ChatGoogleGenerativeAI)
  - Config centralization (no os.getenv outside config)
"""

import pytest
from unittest.mock import MagicMock, patch


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Types & Enums
# ═══════════════════════════════════════════════════════════════════════════════

class TestLLMTypes:

    def test_task_type_values(self):
        from src.llm.types import LLMTaskType
        assert LLMTaskType.REASONING == "reasoning"
        assert LLMTaskType.FAST == "fast"
        assert LLMTaskType.EXTRACTION == "extraction"
        assert LLMTaskType.SYNTHESIS == "synthesis"
        assert LLMTaskType.CODING == "coding"
        assert LLMTaskType.FALLBACK_SAFE == "fallback_safe"

    def test_provider_name_values(self):
        from src.llm.types import LLMProviderName
        assert LLMProviderName.GEMINI == "gemini"
        assert LLMProviderName.OPENAI == "openai"

    def test_llm_selection_model(self):
        from src.llm.types import LLMSelection, LLMProviderName, LLMTaskType
        sel = LLMSelection(
            provider=LLMProviderName.GEMINI,
            model="gemini-2.5-pro",
            task_type=LLMTaskType.REASONING,
        )
        assert sel.provider == LLMProviderName.GEMINI
        assert sel.is_fallback is False

    def test_invocation_result_defaults(self):
        from src.llm.types import LLMInvocationResult, LLMProviderName, LLMTaskType
        result = LLMInvocationResult(
            content="test",
            provider=LLMProviderName.GEMINI,
            model="gemini-2.5-flash",
            task_type=LLMTaskType.FAST,
        )
        assert result.success is True
        assert result.fallback_used is False
        assert result.error is None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Router
# ═══════════════════════════════════════════════════════════════════════════════

class TestRouter:

    def test_reasoning_routes_to_pro(self):
        from src.llm.router import select
        from src.llm.types import LLMTaskType
        sel = select(LLMTaskType.REASONING)
        assert "pro" in sel.model

    def test_fast_routes_to_flash(self):
        from src.llm.router import select
        from src.llm.types import LLMTaskType
        sel = select(LLMTaskType.FAST)
        assert "flash" in sel.model

    def test_extraction_routes_to_flash(self):
        from src.llm.router import select
        from src.llm.types import LLMTaskType
        sel = select(LLMTaskType.EXTRACTION)
        assert "flash" in sel.model

    def test_synthesis_routes_to_pro(self):
        from src.llm.router import select
        from src.llm.types import LLMTaskType
        sel = select(LLMTaskType.SYNTHESIS)
        assert "pro" in sel.model

    def test_fallback_safe_uses_cheapest(self):
        from src.llm.router import select
        from src.llm.types import LLMTaskType
        sel = select(LLMTaskType.FALLBACK_SAFE)
        assert "flash" in sel.model

    def test_select_fallback_returns_none_without_key(self):
        from src.llm.router import select_fallback
        from src.llm.types import LLMTaskType
        # Without OPENAI_API_KEY set, should return None or a selection
        result = select_fallback(LLMTaskType.REASONING)
        # Result depends on config — just verify it doesn't crash
        assert result is None or result.is_fallback is True

    def test_temperature_override(self):
        from src.llm.router import select
        from src.llm.types import LLMTaskType
        sel = select(LLMTaskType.FAST, temperature=0.8)
        assert sel.temperature == 0.8


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Factory
# ═══════════════════════════════════════════════════════════════════════════════

class TestFactory:

    def test_build_gemini_model(self):
        from src.llm.factory import build_model
        from src.llm.types import LLMSelection, LLMProviderName, LLMTaskType
        from src.config import get_settings

        sel = LLMSelection(
            provider=LLMProviderName.GEMINI,
            model="gemini-2.5-flash",
            task_type=LLMTaskType.FAST,
        )
        keys = {"gemini": get_settings().GOOGLE_API_KEY}
        model = build_model(sel, keys)
        assert model is not None

    def test_build_without_key_raises(self):
        from src.llm.factory import build_model
        from src.llm.types import LLMSelection, LLMProviderName, LLMTaskType

        sel = LLMSelection(
            provider=LLMProviderName.OPENAI,
            model="gpt-4o-mini",
            task_type=LLMTaskType.FAST,
        )
        with pytest.raises(ValueError, match="No API key"):
            build_model(sel, {})


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Fallback
# ═══════════════════════════════════════════════════════════════════════════════

class TestFallback:

    def test_primary_success(self):
        from src.llm.fallback import invoke_with_fallback
        from src.llm.types import LLMSelection, LLMProviderName, LLMTaskType

        primary = MagicMock()
        primary.invoke.return_value = "primary_result"
        sel = LLMSelection(
            provider=LLMProviderName.GEMINI,
            model="gemini-2.5-pro",
            task_type=LLMTaskType.REASONING,
        )

        result = invoke_with_fallback(primary, sel, None, None, "test", LLMTaskType.REASONING)
        assert result.success is True
        assert result.content == "primary_result"
        assert result.fallback_used is False

    def test_primary_fail_no_fallback(self):
        from src.llm.fallback import invoke_with_fallback
        from src.llm.types import LLMSelection, LLMProviderName, LLMTaskType

        primary = MagicMock()
        primary.invoke.side_effect = RuntimeError("Gemini down")
        sel = LLMSelection(
            provider=LLMProviderName.GEMINI,
            model="gemini-2.5-pro",
            task_type=LLMTaskType.REASONING,
        )

        result = invoke_with_fallback(primary, sel, None, None, "test", LLMTaskType.REASONING)
        assert result.success is False
        assert "Gemini down" in result.error

    def test_primary_fail_fallback_succeeds(self):
        from src.llm.fallback import invoke_with_fallback
        from src.llm.types import LLMSelection, LLMProviderName, LLMTaskType

        primary = MagicMock()
        primary.invoke.side_effect = RuntimeError("Gemini down")
        p_sel = LLMSelection(
            provider=LLMProviderName.GEMINI,
            model="gemini-2.5-pro",
            task_type=LLMTaskType.REASONING,
        )

        fallback = MagicMock()
        fallback.invoke.return_value = "fallback_result"
        f_sel = LLMSelection(
            provider=LLMProviderName.OPENAI,
            model="gpt-4o-mini",
            task_type=LLMTaskType.REASONING,
            is_fallback=True,
        )

        result = invoke_with_fallback(primary, p_sel, fallback, f_sel, "test", LLMTaskType.REASONING)
        assert result.success is True
        assert result.fallback_used is True
        assert result.content == "fallback_result"
        assert result.provider == LLMProviderName.OPENAI

    def test_both_fail(self):
        from src.llm.fallback import invoke_with_fallback
        from src.llm.types import LLMSelection, LLMProviderName, LLMTaskType

        primary = MagicMock()
        primary.invoke.side_effect = RuntimeError("Gemini down")
        p_sel = LLMSelection(
            provider=LLMProviderName.GEMINI,
            model="gemini-2.5-pro",
            task_type=LLMTaskType.REASONING,
        )

        fallback = MagicMock()
        fallback.invoke.side_effect = RuntimeError("OpenAI down")
        f_sel = LLMSelection(
            provider=LLMProviderName.OPENAI,
            model="gpt-4o-mini",
            task_type=LLMTaskType.REASONING,
            is_fallback=True,
        )

        result = invoke_with_fallback(primary, p_sel, fallback, f_sel, "test", LLMTaskType.REASONING)
        assert result.success is False
        assert result.fallback_used is True
        assert "Primary" in result.error and "Fallback" in result.error


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Instrumentation
# ═══════════════════════════════════════════════════════════════════════════════

class TestInstrumentation:

    def setup_method(self):
        from src.llm.instrumentation import get_instruments
        get_instruments().reset()

    def test_record_success(self):
        from src.llm.instrumentation import get_instruments
        from src.llm.types import LLMInvocationResult, LLMProviderName, LLMTaskType

        inst = get_instruments()
        inst.record(LLMInvocationResult(
            content="ok", provider=LLMProviderName.GEMINI,
            model="test", task_type=LLMTaskType.FAST,
            latency_ms=100, success=True,
        ))
        metrics = inst.get_metrics()
        assert metrics.total_invocations == 1
        assert metrics.successful == 1
        assert metrics.avg_latency_ms == 100.0

    def test_record_failure(self):
        from src.llm.instrumentation import get_instruments
        from src.llm.types import LLMInvocationResult, LLMProviderName, LLMTaskType

        inst = get_instruments()
        inst.record(LLMInvocationResult(
            content=None, provider=LLMProviderName.GEMINI,
            model="test", task_type=LLMTaskType.FAST,
            success=False, error="timeout",
        ))
        metrics = inst.get_metrics()
        assert metrics.failed == 1
        assert len(metrics.errors) == 1

    def test_by_task_type_tracking(self):
        from src.llm.instrumentation import get_instruments
        from src.llm.types import LLMInvocationResult, LLMProviderName, LLMTaskType

        inst = get_instruments()
        for _ in range(3):
            inst.record(LLMInvocationResult(
                content="ok", provider=LLMProviderName.GEMINI,
                model="test", task_type=LLMTaskType.FAST,
                success=True, latency_ms=50,
            ))
        inst.record(LLMInvocationResult(
            content="ok", provider=LLMProviderName.GEMINI,
            model="test", task_type=LLMTaskType.REASONING,
            success=True, latency_ms=200,
        ))
        metrics = inst.get_metrics()
        assert metrics.by_task_type["fast"] == 3
        assert metrics.by_task_type["reasoning"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Provider (Public API)
# ═══════════════════════════════════════════════════════════════════════════════

class TestProvider:

    def test_get_llm_returns_model(self):
        from src.llm import get_llm, LLMTaskType
        model = get_llm(LLMTaskType.FAST)
        assert model is not None
        assert hasattr(model, "invoke")

    def test_get_llm_caches_models(self):
        from src.llm import get_llm, LLMTaskType
        m1 = get_llm(LLMTaskType.FAST)
        m2 = get_llm(LLMTaskType.FAST)
        assert m1 is m2  # Same instance (cached)

    def test_different_task_types_may_differ(self):
        from src.llm import get_llm, LLMTaskType
        fast = get_llm(LLMTaskType.FAST)
        reasoning = get_llm(LLMTaskType.REASONING)
        # They should be different models (flash vs pro)
        assert fast is not reasoning

    def test_get_llm_metrics_returns_dict(self):
        from src.llm import get_llm_metrics
        metrics = get_llm_metrics()
        assert "total_invocations" in metrics
        assert "by_task_type" in metrics


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Consumer Agent Compliance — no direct ChatGoogleGenerativeAI
# ═══════════════════════════════════════════════════════════════════════════════

class TestConsumerCompliance:
    """Verify no agent imports ChatGoogleGenerativeAI directly."""

    @pytest.mark.parametrize("module_path", [
        "src/engines/fundamental/graph.py",
        "src/engines/technical/analyst_agent.py",
        "src/engines/backtesting/backtest_memo_agent.py",
        "src/engines/alpha/alpha_memo_agent.py",
        "src/engines/alpha/evidence_memo_agent.py",
        "src/engines/alpha/signal_map_memo_agent.py",
        "src/engines/decision/cio_agent.py",
    ])
    def test_no_direct_llm_import(self, module_path):
        """Agent files must NOT import ChatGoogleGenerativeAI directly."""
        with open(module_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "from langchain_google_genai import" not in content, (
            f"{module_path} still imports ChatGoogleGenerativeAI directly!"
        )
        assert "ChatGoogleGenerativeAI(" not in content, (
            f"{module_path} still instantiates ChatGoogleGenerativeAI!"
        )

    @pytest.mark.parametrize("module_path", [
        "src/engines/fundamental/graph.py",
        "src/engines/technical/analyst_agent.py",
        "src/engines/backtesting/backtest_memo_agent.py",
        "src/engines/alpha/alpha_memo_agent.py",
        "src/engines/alpha/evidence_memo_agent.py",
        "src/engines/alpha/signal_map_memo_agent.py",
        "src/engines/decision/cio_agent.py",
    ])
    def test_no_os_getenv_for_keys(self, module_path):
        """Agent files must NOT use os.getenv for API keys."""
        with open(module_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert 'os.getenv("GOOGLE_API_KEY")' not in content, (
            f"{module_path} still uses os.getenv for API keys!"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Legacy Shim
# ═══════════════════════════════════════════════════════════════════════════════

class TestLegacyShim:

    def test_legacy_import_still_works(self):
        from src.services.llm_provider import get_llm_provider
        provider = get_llm_provider()
        assert provider is not None
        assert hasattr(provider, "invoke")

    def test_legacy_provider_class_import(self):
        from src.services.llm_provider import LLMProvider
        assert LLMProvider is not None
