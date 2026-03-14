"""
src/observability/tracing.py
─────────────────────────────────────────────────────────────────────────────
OpenTelemetry instrumentation for 365 Advisers.

Provides:
  - Auto-instrumentation for FastAPI HTTP requests
  - Traced LLM call wrapper with cost estimation
  - Named tracer/meter access
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from src.config import get_settings

logger = logging.getLogger("365advisers.observability")

# ── Lazy globals (initialised by init_telemetry) ────────────────────────────

_tracer_provider = None
_meter_provider = None
_initialized = False


def init_telemetry(service_name: str | None = None) -> None:
    """
    Initialise OpenTelemetry tracing and metrics.

    Call once during app lifespan startup.
    Safe to call multiple times (idempotent).
    """
    global _tracer_provider, _meter_provider, _initialized

    if _initialized:
        return

    settings = get_settings()
    if not settings.OTEL_ENABLED:
        logger.info("OpenTelemetry disabled (OTEL_ENABLED=False)")
        _initialized = True
        return

    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import (
            PeriodicExportingMetricReader,
            ConsoleMetricExporter,
        )
        from opentelemetry.sdk.resources import Resource

        svc_name = service_name or settings.OTEL_SERVICE_NAME
        resource = Resource.create({"service.name": svc_name})

        # ── Tracing ──────────────────────────────────────────────────────
        if settings.OTEL_EXPORTER == "otlp":
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )
                span_exporter = OTLPSpanExporter(endpoint=f"{settings.OTEL_ENDPOINT}/v1/traces")
            except ImportError:
                logger.warning("OTLP exporter not installed, falling back to console")
                span_exporter = ConsoleSpanExporter()
        else:
            span_exporter = ConsoleSpanExporter()

        _tracer_provider = TracerProvider(resource=resource)
        _tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
        trace.set_tracer_provider(_tracer_provider)

        # ── Metrics ──────────────────────────────────────────────────────
        metric_reader = PeriodicExportingMetricReader(
            ConsoleMetricExporter(),
            export_interval_millis=60000,  # 1 min
        )
        _meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader],
        )
        metrics.set_meter_provider(_meter_provider)

        _initialized = True
        logger.info(f"OpenTelemetry initialised: service={svc_name}, exporter={settings.OTEL_EXPORTER}")

    except ImportError as exc:
        logger.warning(f"OpenTelemetry SDK not installed — tracing disabled: {exc}")
        _initialized = True
    except Exception as exc:
        logger.error(f"OpenTelemetry init failed: {exc}")
        _initialized = True


def get_tracer(name: str = "365advisers"):
    """Return a named tracer (no-op if OTEL is disabled)."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        return _NoOpTracer()


def get_meter(name: str = "365advisers"):
    """Return a named meter (no-op if OTEL is disabled)."""
    try:
        from opentelemetry import metrics
        return metrics.get_meter(name)
    except ImportError:
        return _NoOpMeter()


# ── LLM Call Tracing ─────────────────────────────────────────────────────────

# Cost estimates per 1K tokens (USD) — Gemini 2.5 pricing as of 2026-Q1
_COST_PER_1K_TOKENS = {
    "gemini-2.5-flash": {"input": 0.00015, "output": 0.0006},
    "gemini-2.5-pro": {"input": 0.00125, "output": 0.005},
}


def traced_llm_call(
    model: str,
    prompt: str,
    invoke_fn: Callable[..., Any],
    *args,
    **kwargs,
) -> Any:
    """
    Execute an LLM call with OpenTelemetry tracing.

    Creates a span with attributes:
      - llm.model, llm.prompt_chars, llm.response_chars
      - llm.duration_ms, llm.estimated_cost_usd

    Parameters
    ----------
    model : str
        Model name (e.g. "gemini-2.5-pro")
    prompt : str
        The prompt text (for length measurement, not stored in span)
    invoke_fn : Callable
        The LLM invoke function to call
    """
    tracer = get_tracer("365advisers.llm")

    try:
        from opentelemetry import trace as otel_trace
        with tracer.start_as_current_span(
            f"llm.invoke.{model}",
            kind=otel_trace.SpanKind.CLIENT,
        ) as span:
            span.set_attribute("llm.model", model)
            span.set_attribute("llm.prompt_chars", len(prompt))

            t0 = time.perf_counter()
            result = invoke_fn(prompt, *args, **kwargs)
            duration_ms = (time.perf_counter() - t0) * 1000

            response_text = result.content if hasattr(result, "content") else str(result)
            response_chars = len(response_text)

            # Estimate cost (rough: 4 chars ≈ 1 token)
            input_tokens = len(prompt) / 4
            output_tokens = response_chars / 4
            pricing = _COST_PER_1K_TOKENS.get(model, {"input": 0.001, "output": 0.003})
            estimated_cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1000

            span.set_attribute("llm.response_chars", response_chars)
            span.set_attribute("llm.duration_ms", round(duration_ms, 1))
            span.set_attribute("llm.estimated_cost_usd", round(estimated_cost, 6))
            span.set_attribute("llm.input_tokens_est", int(input_tokens))
            span.set_attribute("llm.output_tokens_est", int(output_tokens))

            # Record metrics
            _record_llm_metrics(model, duration_ms, input_tokens, output_tokens, estimated_cost)

            return result

    except ImportError:
        # OTEL not available — execute without tracing
        return invoke_fn(prompt, *args, **kwargs)


def _record_llm_metrics(
    model: str,
    duration_ms: float,
    input_tokens: float,
    output_tokens: float,
    cost_usd: float,
) -> None:
    """Record LLM call metrics."""
    try:
        meter = get_meter("365advisers.llm")
        counter = meter.create_counter("llm.calls", description="Total LLM invocations")
        histogram = meter.create_histogram("llm.duration", unit="ms", description="LLM call duration")
        cost_counter = meter.create_counter("llm.cost.usd", description="Estimated LLM cost in USD")

        attrs = {"llm.model": model}
        counter.add(1, attrs)
        histogram.record(duration_ms, attrs)
        cost_counter.add(cost_usd, attrs)
    except Exception:
        pass  # Metrics are best-effort


# ── No-Op Fallbacks ──────────────────────────────────────────────────────────

class _NoOpSpan:
    def set_attribute(self, *a, **kw): pass
    def __enter__(self): return self
    def __exit__(self, *a): pass

class _NoOpTracer:
    def start_as_current_span(self, *a, **kw): return _NoOpSpan()

class _NoOpMeter:
    def create_counter(self, *a, **kw): return _NoOpCounter()
    def create_histogram(self, *a, **kw): return _NoOpCounter()

class _NoOpCounter:
    def add(self, *a, **kw): pass
    def record(self, *a, **kw): pass
