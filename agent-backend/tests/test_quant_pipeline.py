"""
tests/test_quant_pipeline.py
--------------------------------------------------------------------------
Tests for the End-to-End Quant Pipeline.
"""

from __future__ import annotations

import pytest
from datetime import date

from src.engines.quant_pipeline import QuantPipeline, PipelineResult


class TestQuantPipeline:

    def test_dry_run_completes(self):
        """Dry run completes all 11 steps (some may be partial in test env)."""
        pipeline = QuantPipeline(universe_name="test", dry_run=True)
        result = pipeline.run()

        assert result.overall_status in ("success", "partial")
        assert result.successful_steps >= 9  # At least 9 of 11
        assert result.total_duration_seconds >= 0

    def test_all_steps_present(self):
        """All 11 steps are executed."""
        pipeline = QuantPipeline(universe_name="test")
        result = pipeline.run()

        assert len(result.steps) == 11
        step_names = [s.step_name for s in result.steps]
        assert "1_universe_selection" in step_names
        assert "11_performance_report" in step_names

    def test_step_timing(self):
        """Each step has timing data."""
        pipeline = QuantPipeline(universe_name="test")
        result = pipeline.run()

        for step in result.steps:
            assert step.duration_ms >= 0

    def test_universe_step_returns_tickers(self):
        """Universe step returns ticker count."""
        pipeline = QuantPipeline(universe_name="test")
        result = pipeline.run()

        universe_step = next(s for s in result.steps if s.step_name == "1_universe_selection")
        assert universe_step.details["tickers"] == 10

    def test_scanning_step_runs(self):
        """Scanning step executes (may succeed or fail gracefully)."""
        pipeline = QuantPipeline(universe_name="test")
        result = pipeline.run()

        scan_step = next(s for s in result.steps if s.step_name == "2_signal_scanning")
        assert scan_step.status in ("success", "failed")  # Isolated, doesn't crash

    def test_audit_step_records(self):
        """Audit step records an entry."""
        pipeline = QuantPipeline(universe_name="test")
        result = pipeline.run()

        audit_step = next(s for s in result.steps if s.step_name == "10_audit_trail")
        assert audit_step.details["entries_recorded"] == 1

    def test_run_id_generated(self):
        """Run ID is generated."""
        pipeline = QuantPipeline()
        result = pipeline.run()

        assert result.run_id.startswith("RUN-")
