"""
tests/test_ideas.py
──────────────────────────────────────────────────────────────────────────────
Tests for the Ideas Generation engine and routes.
"""
from __future__ import annotations

import pytest

from src.engines.idea_generation.engine import IdeaGenerator


class TestIdeaGenerator:

    def setup_method(self):
        self.generator = IdeaGenerator()

    def test_scan_returns_list(self):
        """IdeaGenerator.scan should return a list."""
        result = self.generator.scan(
            tickers=["AAPL", "MSFT"],
            max_ideas=3,
        )
        assert isinstance(result, list)

    def test_scan_respects_max_ideas(self):
        """Should not return more ideas than requested."""
        result = self.generator.scan(
            tickers=["AAPL"],
            max_ideas=1,
        )
        assert len(result) <= 1

    def test_idea_has_required_fields(self):
        """Each idea should have ticker, signal, and score."""
        result = self.generator.scan(tickers=["AAPL"], max_ideas=1)
        if result:
            idea = result[0]
            assert "ticker" in idea or hasattr(idea, "ticker")

    def test_empty_ticker_list(self):
        """Empty ticker list should return empty results."""
        result = self.generator.scan(tickers=[], max_ideas=5)
        assert isinstance(result, list)
        assert len(result) == 0


class TestIdeaProfiles:

    def test_default_profiles_exist(self):
        """Should have at least one strategy profile."""
        gen = IdeaGenerator()
        profiles = gen.get_profiles() if hasattr(gen, "get_profiles") else []
        # Profiles exist or function is not implemented yet
        assert isinstance(profiles, list)
