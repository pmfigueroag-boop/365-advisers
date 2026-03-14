"""
tests/test_observability.py
─────────────────────────────────────────────────────────────────────────────
Tests for the OpenTelemetry observability layer.
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from src.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("OTEL_ENABLED", "True")
    monkeypatch.setenv("OTEL_EXPORTER", "console")


class TestInitTelemetry:
    def test_init_telemetry_does_not_crash(self, mock_settings):
        from src.observability.tracing import init_telemetry, _initialized
        # Reset state
        import src.observability.tracing as mod
        mod._initialized = False
        init_telemetry("test-service")
        assert mod._initialized is True

    def test_init_telemetry_is_idempotent(self, mock_settings):
        import src.observability.tracing as mod
        mod._initialized = False
        mod.init_telemetry("test-service")
        assert mod._initialized is True
        mod.init_telemetry("test-service")  # Should not crash
        assert mod._initialized is True

    def test_init_disabled(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
        monkeypatch.setenv("OTEL_ENABLED", "False")
        import src.observability.tracing as mod
        mod._initialized = False
        mod.init_telemetry()
        assert mod._initialized is True


class TestGetTracer:
    def test_get_tracer_returns_object(self, mock_settings):
        from src.observability.tracing import get_tracer
        tracer = get_tracer("test")
        assert tracer is not None

    def test_get_tracer_with_different_names(self, mock_settings):
        from src.observability.tracing import get_tracer
        t1 = get_tracer("test1")
        t2 = get_tracer("test2")
        assert t1 is not None
        assert t2 is not None


class TestTracedLLMCall:
    def test_traced_call_executes_function(self, mock_settings):
        from src.observability.tracing import traced_llm_call
        import src.observability.tracing as mod
        mod._initialized = False
        mod.init_telemetry("test")

        mock_result = MagicMock()
        mock_result.content = '{"test": true}'

        def mock_invoke(prompt):
            return mock_result

        result = traced_llm_call("gemini-2.5-flash", "test prompt", mock_invoke)
        assert result.content == '{"test": true}'

    def test_traced_call_with_long_prompt(self, mock_settings):
        from src.observability.tracing import traced_llm_call
        import src.observability.tracing as mod
        mod._initialized = False
        mod.init_telemetry("test")

        mock_result = MagicMock()
        mock_result.content = "response " * 100

        result = traced_llm_call(
            "gemini-2.5-pro",
            "prompt " * 500,
            lambda p: mock_result,
        )
        assert result.content.startswith("response")

    def test_traced_call_handles_exception(self, mock_settings):
        from src.observability.tracing import traced_llm_call
        import src.observability.tracing as mod
        mod._initialized = False
        mod.init_telemetry("test")

        def failing_invoke(prompt):
            raise ValueError("LLM error")

        with pytest.raises(ValueError, match="LLM error"):
            traced_llm_call("gemini-2.5-flash", "test", failing_invoke)


class TestCostEstimation:
    def test_cost_estimation_values(self):
        from src.observability.tracing import _COST_PER_1K_TOKENS
        assert "gemini-2.5-flash" in _COST_PER_1K_TOKENS
        assert "gemini-2.5-pro" in _COST_PER_1K_TOKENS
        assert _COST_PER_1K_TOKENS["gemini-2.5-flash"]["input"] < _COST_PER_1K_TOKENS["gemini-2.5-pro"]["input"]


class TestNoOpFallbacks:
    def test_noop_tracer(self):
        from src.observability.tracing import _NoOpTracer, _NoOpSpan
        tracer = _NoOpTracer()
        span = tracer.start_as_current_span("test")
        assert isinstance(span, _NoOpSpan)
        span.set_attribute("key", "value")  # Should not crash
        with span:
            pass  # Context manager should work

    def test_noop_meter(self):
        from src.observability.tracing import _NoOpMeter
        meter = _NoOpMeter()
        counter = meter.create_counter("test")
        counter.add(1, {"key": "value"})  # Should not crash
        histogram = meter.create_histogram("test")
        histogram.record(42.0)  # Should not crash
