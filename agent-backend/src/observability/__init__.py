"""
src/observability — 365 Advisers OpenTelemetry Instrumentation

Public API:
    init_telemetry     — Initialise tracing + metrics (call in lifespan)
    get_tracer         — Get a named tracer
    get_meter          — Get a named meter
    traced_llm_call    — Wrapper for LLM calls with tracing and cost estimation
"""

from src.observability.tracing import (
    init_telemetry,
    get_tracer,
    get_meter,
    traced_llm_call,
)

__all__ = [
    "init_telemetry",
    "get_tracer",
    "get_meter",
    "traced_llm_call",
]
