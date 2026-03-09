"""
tests/test_alt_data.py — Alternative data integration tests.
"""
import pytest
from src.engines.alt_data.models import AltDataType
from src.engines.alt_data.adapters import (
    SatelliteAdapter, WebTrafficAdapter, SocialSentimentAdapter,
    CreditCardAdapter, JobPostingsAdapter, PatentAdapter,
)
from src.engines.alt_data.engine import AltDataEngine


class TestAdapters:
    def test_satellite(self):
        sig = SatelliteAdapter().fetch("AAPL", seed=42)
        assert sig.source_type == AltDataType.SATELLITE
        assert -1 <= sig.signal <= 1
        assert sig.value > 0

    def test_web_traffic(self):
        sig = WebTrafficAdapter().fetch("MSFT", seed=42)
        assert sig.source_type == AltDataType.WEB_TRAFFIC
        assert sig.value > 0

    def test_social(self):
        sig = SocialSentimentAdapter().fetch("TSLA", seed=42)
        assert sig.source_type == AltDataType.SOCIAL_SENTIMENT
        assert -1 <= sig.signal <= 1

    def test_credit_card(self):
        sig = CreditCardAdapter().fetch("WMT", seed=42)
        assert sig.source_type == AltDataType.CREDIT_CARD
        assert sig.confidence > 0

    def test_job_postings(self):
        sig = JobPostingsAdapter().fetch("AMZN", seed=42)
        assert sig.source_type == AltDataType.JOB_POSTINGS

    def test_patents(self):
        sig = PatentAdapter().fetch("GOOGL", seed=42)
        assert sig.source_type == AltDataType.PATENT_FILINGS

    def test_deterministic(self):
        a = SatelliteAdapter().fetch("AAPL", seed=42)
        b = SatelliteAdapter().fetch("AAPL", seed=42)
        assert a.signal == b.signal


class TestAltDataEngine:
    def test_analyse(self):
        report = AltDataEngine.analyse("AAPL", seed=42)
        assert report.ticker == "AAPL"
        assert report.sources_used == 6
        assert len(report.signals) == 6
        assert -1 <= report.composite_signal <= 1

    def test_batch(self):
        reports = AltDataEngine.batch_analyse(["AAPL", "MSFT"], seed=42)
        assert "AAPL" in reports
        assert "MSFT" in reports

    def test_single_source(self):
        sig = AltDataEngine.get_source_signal("AAPL", AltDataType.SATELLITE, seed=42)
        assert sig is not None
        assert sig.source_type == AltDataType.SATELLITE

    def test_unknown_source(self):
        sig = AltDataEngine.get_source_signal("AAPL", AltDataType.APP_DOWNLOADS)
        assert sig is None
