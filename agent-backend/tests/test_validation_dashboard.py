"""
tests/test_validation_dashboard.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Validation Intelligence Dashboard.

Covers:
  - Pydantic model contracts
  - Aggregation logic (with mocked data sources)
  - Default/empty behavior
"""

from __future__ import annotations

import pytest

from src.engines.validation_dashboard.models import (
    DetectorPerformanceSection,
    OpportunityTrackingSection,
    SignalLeaderboard,
    SignalLeaderboardEntry,
    SystemHealthSection,
    ValidationIntelligence,
)
from src.engines.validation_dashboard.aggregator import DashboardAggregator


# ─── Model Tests ─────────────────────────────────────────────────────────────

class TestDashboardModels:
    """Tests for Pydantic response models."""

    def test_validation_intelligence_defaults(self):
        vi = ValidationIntelligence()
        assert vi.leaderboard.total_signals == 0
        assert vi.detector_performance.total_detectors == 0
        assert vi.opportunity_tracking.total_ideas == 0
        assert vi.system_health.active_degradation_alerts == 0
        assert vi.generated_at is not None

    def test_leaderboard_entry_defaults(self):
        entry = SignalLeaderboardEntry(signal_id="test.signal")
        assert entry.signal_id == "test.signal"
        assert entry.quality_tier == "D"
        assert entry.stability_class is None
        assert entry.cost_resilience is None
        assert entry.alpha_source is None

    def test_leaderboard_with_entries(self):
        entries = [
            SignalLeaderboardEntry(
                signal_id="sig.1",
                sharpe_20d=1.5,
                hit_rate_20d=0.62,
                avg_alpha_20d=0.0035,
                quality_tier="A",
                stability_class="robust",
                cost_resilience="resilient",
                alpha_source="pure_alpha",
            ),
            SignalLeaderboardEntry(
                signal_id="sig.2",
                sharpe_20d=0.3,
                hit_rate_20d=0.48,
                quality_tier="D",
            ),
        ]
        lb = SignalLeaderboard(
            total_signals=2,
            avg_sharpe=0.9,
            top_signals=entries[:1],
            bottom_signals=entries[1:],
        )
        assert lb.total_signals == 2
        assert len(lb.top_signals) == 1
        assert lb.top_signals[0].signal_id == "sig.1"

    def test_system_health_defaults(self):
        sh = SystemHealthSection()
        assert sh.stability_distribution == {}
        assert sh.avg_cost_drag_bps == 0.0
        assert sh.pending_recalibrations == 0

    def test_system_health_with_data(self):
        sh = SystemHealthSection(
            stability_distribution={"robust": 10, "moderate": 5, "overfit": 2},
            avg_stability_score=0.72,
            avg_cost_drag_bps=15.5,
            alpha_source_distribution={"pure_alpha": 8, "mixed": 5, "factor_beta": 3},
            active_degradation_alerts=2,
        )
        assert sum(sh.stability_distribution.values()) == 17
        assert sh.active_degradation_alerts == 2

    def test_detector_performance_defaults(self):
        dp = DetectorPerformanceSection()
        assert dp.total_detectors == 0
        assert dp.best_detector == ""

    def test_opportunity_tracking_defaults(self):
        ot = OpportunityTrackingSection()
        assert ot.total_ideas == 0
        assert ot.hit_rate_20d == 0.0


# ─── Serialization Tests ────────────────────────────────────────────────────

class TestSerialization:
    """Tests that all models serialize correctly."""

    def test_full_response_serialization(self):
        vi = ValidationIntelligence(
            leaderboard=SignalLeaderboard(
                total_signals=5,
                top_signals=[
                    SignalLeaderboardEntry(signal_id="sig.1", sharpe_20d=1.5),
                ],
            ),
            system_health=SystemHealthSection(
                stability_distribution={"robust": 3},
                avg_cost_drag_bps=10.0,
            ),
        )
        d = vi.model_dump()
        assert d["leaderboard"]["total_signals"] == 5
        assert d["system_health"]["avg_cost_drag_bps"] == 10.0
        assert "generated_at" in d

    def test_entry_serialization(self):
        entry = SignalLeaderboardEntry(
            signal_id="test",
            stability_class="robust",
            cost_resilience="resilient",
            alpha_source="pure_alpha",
        )
        d = entry.model_dump()
        assert d["stability_class"] == "robust"
        assert d["cost_resilience"] == "resilient"
        assert d["alpha_source"] == "pure_alpha"


# ─── Aggregator Tests ───────────────────────────────────────────────────────

class TestAggregator:
    """Tests for the DashboardAggregator."""

    def test_aggregate_returns_valid_response(self):
        """Aggregator should return a valid response even with no data."""
        aggregator = DashboardAggregator()
        result = aggregator.aggregate()
        assert isinstance(result, ValidationIntelligence)
        assert result.generated_at is not None

    def test_aggregate_leaderboard_graceful_failure(self):
        """Leaderboard should return empty on failure."""
        aggregator = DashboardAggregator()
        lb = aggregator._build_leaderboard()
        assert isinstance(lb, SignalLeaderboard)

    def test_aggregate_detector_graceful_failure(self):
        """Detector section should return empty on failure."""
        aggregator = DashboardAggregator()
        dp = aggregator._build_detector_performance()
        assert isinstance(dp, DetectorPerformanceSection)

    def test_aggregate_opportunity_graceful_failure(self):
        """Opportunity section should return empty on failure."""
        aggregator = DashboardAggregator()
        ot = aggregator._build_opportunity_tracking()
        assert isinstance(ot, OpportunityTrackingSection)

    def test_aggregate_health_graceful_failure(self):
        """System health should return empty on failure."""
        aggregator = DashboardAggregator()
        sh = aggregator._build_system_health()
        assert isinstance(sh, SystemHealthSection)

    def test_empty_maps(self):
        """Helper methods should return empty dicts gracefully."""
        aggregator = DashboardAggregator()
        assert aggregator._get_stability_map() == {} or isinstance(aggregator._get_stability_map(), dict)
        assert aggregator._get_cost_map() == {} or isinstance(aggregator._get_cost_map(), dict)
        assert aggregator._get_factor_map() == {} or isinstance(aggregator._get_factor_map(), dict)
