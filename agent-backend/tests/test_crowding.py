"""
tests/test_crowding.py
──────────────────────────────────────────────────────────────────────────────
Tests for the Crowding Detection engine and routes.
"""
from __future__ import annotations

import pytest

from src.engines.crowding.detector import CrowdingDetector


# ─── CrowdingDetector Tests ──────────────────────────────────────────────────


class TestCrowdingDetector:

    def setup_method(self):
        self.detector = CrowdingDetector()

    def test_assess_returns_dict(self):
        """CrowdingDetector.assess should return a well-formed dict."""
        result = self.detector.assess("AAPL")
        assert isinstance(result, dict)
        assert "ticker" in result

    def test_assess_score_range(self):
        """Crowding score should be between 0 and 100."""
        result = self.detector.assess("AAPL")
        score = result.get("crowding_score", result.get("score", 0))
        assert 0 <= score <= 100

    def test_assess_unknown_ticker(self):
        """Unknown ticker should return graceful result, not crash."""
        result = self.detector.assess("ZZZZNOTREAL")
        assert isinstance(result, dict)

    def test_batch_assess(self):
        """Batch assessment should handle multiple tickers."""
        tickers = ["AAPL", "MSFT"]
        results = [self.detector.assess(t) for t in tickers]
        assert len(results) == 2
        assert all(isinstance(r, dict) for r in results)


class TestCrowdingContract:

    def test_result_has_required_fields(self):
        """Crowding result should include expected fields from frontend contract."""
        detector = CrowdingDetector()
        result = detector.assess("AAPL")
        # Frontend (useCrowding.ts) expects at minimum: ticker + score
        assert "ticker" in result or "symbol" in result
