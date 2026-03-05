"""
tests/test_phase4_orchestration.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for Phase 4: Orchestration Extraction.

Tests validate:
  1. SSE streamer produces valid event strings
  2. AnalysisPipeline can be instantiated
  3. All route modules export valid APIRouters
  4. Route modules have expected endpoints
"""

import pytest
import json


# ─── SSE Streamer ─────────────────────────────────────────────────────────────

class TestSSEStreamer:
    """Test SSE event formatting."""

    def test_sse_format(self):
        from src.orchestration.sse_streamer import sse
        result = sse("test_event", {"key": "value"})
        assert result.startswith("event: test_event\n")
        assert "data: " in result
        assert result.endswith("\n\n")

        # Data should be valid JSON
        data_line = result.split("\n")[1]
        payload = json.loads(data_line.replace("data: ", ""))
        assert payload == {"key": "value"}

    def test_sse_empty_data(self):
        from src.orchestration.sse_streamer import sse
        result = sse("done", {})
        assert "event: done" in result
        assert '"data": {}' not in result  # json.dumps({}) = "{}"

    def test_replay_cached_events(self):
        import asyncio
        from src.orchestration.sse_streamer import replay_cached_events
        events = [
            {"event": "test1", "data": {"a": 1}},
            {"event": "test2", "data": {"b": 2}},
        ]
        async def _run():
            results = []
            async for line in replay_cached_events(events, delay=0.0):
                results.append(line)
            return results
        results = asyncio.run(_run())
        assert len(results) == 2
        assert "test1" in results[0]
        assert "test2" in results[1]


# ─── AnalysisPipeline ────────────────────────────────────────────────────────

class TestAnalysisPipeline:
    """Test pipeline instantiation."""

    def test_instantiation(self):
        from src.orchestration.analysis_pipeline import AnalysisPipeline

        class MockCache:
            def get(self, k): return None
            def set(self, k, v): pass

        pipeline = AnalysisPipeline(MockCache(), MockCache(), MockCache())
        assert hasattr(pipeline, "run_combined_stream")


# ─── Route Modules ───────────────────────────────────────────────────────────

class TestRouteImports:
    """Verify all route modules export valid APIRouters."""

    def test_analysis_router(self):
        from src.routes.analysis import router
        assert hasattr(router, "routes")
        paths = [r.path for r in router.routes]
        assert "/analysis/combined/stream" in paths
        assert "/analysis/fundamental/stream" in paths
        assert "/analysis/technical" in paths

    def test_cache_router(self):
        from src.routes.cache import router
        assert hasattr(router, "routes")
        paths = [r.path for r in router.routes]
        assert "/score-history" in paths
        assert "/cache/status" in paths

    def test_health_router(self):
        from src.routes.health import router
        assert hasattr(router, "routes")
        paths = [r.path for r in router.routes]
        assert "/" in paths
        assert "/health" in paths
