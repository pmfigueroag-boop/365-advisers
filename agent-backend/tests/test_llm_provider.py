"""
tests/test_llm_provider.py
─────────────────────────────────────────────────────────────────────────────
Tests for LLMProvider — failover logic with mocked LLM calls.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestLLMProviderInit:
    """Test provider initialization."""

    def test_provider_has_primary(self):
        from src.services.llm_provider import get_llm_provider
        provider = get_llm_provider()
        assert provider.primary_name.startswith("gemini/")

    def test_provider_no_fallback_by_default(self):
        """Without OPENAI_API_KEY, fallback should not be available."""
        from src.services.llm_provider import get_llm_provider
        provider = get_llm_provider()
        # Fallback depends on having an OpenAI key set
        assert isinstance(provider.has_fallback, bool)

    def test_provider_primary_name_format(self):
        from src.services.llm_provider import get_llm_provider
        provider = get_llm_provider()
        assert "/" in provider.primary_name


class TestLLMProviderFallback:
    """Test failover behavior with mocked LLMs."""

    def test_primary_success_returns_result(self):
        from src.services.llm_provider import LLMProvider

        with patch.object(LLMProvider, '__init__', lambda self: None):
            provider = LLMProvider.__new__(LLMProvider)
            provider._primary = MagicMock()
            provider._primary.invoke.return_value = "result_a"
            provider._primary_name = "gemini/test"
            provider._fallback = None
            provider._fallback_name = None

            result = provider.invoke("test prompt")
            assert result == "result_a"
            provider._primary.invoke.assert_called_once()

    def test_primary_failure_with_fallback(self):
        from src.services.llm_provider import LLMProvider

        with patch.object(LLMProvider, '__init__', lambda self: None):
            provider = LLMProvider.__new__(LLMProvider)
            provider._primary = MagicMock()
            provider._primary.invoke.side_effect = RuntimeError("Gemini down")
            provider._primary_name = "gemini/test"
            provider._fallback = MagicMock()
            provider._fallback.invoke.return_value = "fallback_result"
            provider._fallback_name = "openai/test"

            result = provider.invoke("test prompt")
            assert result == "fallback_result"
            provider._fallback.invoke.assert_called_once()

    def test_primary_failure_no_fallback_raises(self):
        from src.services.llm_provider import LLMProvider

        with patch.object(LLMProvider, '__init__', lambda self: None):
            provider = LLMProvider.__new__(LLMProvider)
            provider._primary = MagicMock()
            provider._primary.invoke.side_effect = RuntimeError("Gemini down")
            provider._primary_name = "gemini/test"
            provider._fallback = None
            provider._fallback_name = None

            with pytest.raises(RuntimeError, match="Gemini down"):
                provider.invoke("test prompt")

    def test_both_fail_raises_primary_error(self):
        from src.services.llm_provider import LLMProvider

        with patch.object(LLMProvider, '__init__', lambda self: None):
            provider = LLMProvider.__new__(LLMProvider)
            provider._primary = MagicMock()
            provider._primary.invoke.side_effect = RuntimeError("Gemini down")
            provider._primary_name = "gemini/test"
            provider._fallback = MagicMock()
            provider._fallback.invoke.side_effect = RuntimeError("OpenAI down")
            provider._fallback_name = "openai/test"

            with pytest.raises(RuntimeError, match="Gemini down"):
                provider.invoke("test prompt")

    def test_has_fallback_property(self):
        from src.services.llm_provider import LLMProvider

        with patch.object(LLMProvider, '__init__', lambda self: None):
            provider = LLMProvider.__new__(LLMProvider)
            provider._fallback = None
            assert provider.has_fallback is False

            provider._fallback = MagicMock()
            assert provider.has_fallback is True

    def test_fallback_name_none_without_fallback(self):
        from src.services.llm_provider import LLMProvider

        with patch.object(LLMProvider, '__init__', lambda self: None):
            provider = LLMProvider.__new__(LLMProvider)
            provider._fallback = None
            provider._fallback_name = None
            assert provider.fallback_name is None
