"""
src/engines/alt_data/adapters.py — Alternative data source adapters.

Simulated adapters for development. For production, each adapter
connects to its respective API (Orbital Insight, SimilarWeb, etc.).
"""
from __future__ import annotations
import numpy as np
import logging
from src.engines.alt_data.models import AltDataType, AltDataSignal

logger = logging.getLogger("365advisers.alt_data.adapters")


class _BaseAltAdapter:
    """Base class for alternative data adapters."""
    data_type: AltDataType = AltDataType.SATELLITE

    def fetch(self, ticker: str, seed: int | None = None) -> AltDataSignal:
        raise NotImplementedError


class SatelliteAdapter(_BaseAltAdapter):
    """Satellite imagery analysis (parking lot counts, oil storage, shipping)."""
    data_type = AltDataType.SATELLITE

    def fetch(self, ticker: str, seed: int | None = None) -> AltDataSignal:
        rng = np.random.RandomState(seed)
        value = rng.uniform(60, 100)  # occupancy %
        change = rng.normal(0, 5)  # vs prior
        z = change / 5
        signal = float(np.tanh(z))
        return AltDataSignal(
            ticker=ticker, source_type=self.data_type,
            signal=round(signal, 4), confidence=round(abs(signal) * 0.8, 4),
            value=round(value, 1), change_pct=round(change, 2), z_score=round(z, 4),
            description=f"Parking/facility occupancy: {value:.1f}% (Δ{change:+.1f}%)",
        )


class WebTrafficAdapter(_BaseAltAdapter):
    """Website traffic and engagement metrics."""
    data_type = AltDataType.WEB_TRAFFIC

    def fetch(self, ticker: str, seed: int | None = None) -> AltDataSignal:
        rng = np.random.RandomState(seed)
        visits = rng.uniform(1e6, 50e6)
        change = rng.normal(2, 8)
        z = change / 8
        signal = float(np.tanh(z))
        return AltDataSignal(
            ticker=ticker, source_type=self.data_type,
            signal=round(signal, 4), confidence=round(min(abs(signal) * 0.9, 1.0), 4),
            value=round(visits, 0), change_pct=round(change, 2), z_score=round(z, 4),
            description=f"Monthly visits: {visits/1e6:.1f}M (Δ{change:+.1f}%)",
        )


class SocialSentimentAdapter(_BaseAltAdapter):
    """Social media sentiment and mention volume."""
    data_type = AltDataType.SOCIAL_SENTIMENT

    def fetch(self, ticker: str, seed: int | None = None) -> AltDataSignal:
        rng = np.random.RandomState(seed)
        mentions = rng.uniform(100, 10000)
        sentiment = rng.normal(0, 0.3)
        signal = float(np.tanh(sentiment * 2))
        return AltDataSignal(
            ticker=ticker, source_type=self.data_type,
            signal=round(signal, 4), confidence=round(min(mentions / 10000, 1.0), 4),
            value=round(mentions, 0), change_pct=round(sentiment * 100, 2),
            z_score=round(sentiment / 0.3, 4),
            description=f"Social mentions: {mentions:.0f}, sentiment: {sentiment:+.2f}",
        )


class CreditCardAdapter(_BaseAltAdapter):
    """Consumer spending via credit card transaction data."""
    data_type = AltDataType.CREDIT_CARD

    def fetch(self, ticker: str, seed: int | None = None) -> AltDataSignal:
        rng = np.random.RandomState(seed)
        spending_change = rng.normal(3, 6)
        z = spending_change / 6
        signal = float(np.tanh(z))
        return AltDataSignal(
            ticker=ticker, source_type=self.data_type,
            signal=round(signal, 4), confidence=0.75,
            value=round(spending_change, 2), change_pct=round(spending_change, 2),
            z_score=round(z, 4),
            description=f"Consumer spending Δ{spending_change:+.1f}% vs prior period",
        )


class JobPostingsAdapter(_BaseAltAdapter):
    """Job posting volume as proxy for growth/contraction."""
    data_type = AltDataType.JOB_POSTINGS

    def fetch(self, ticker: str, seed: int | None = None) -> AltDataSignal:
        rng = np.random.RandomState(seed)
        postings = rng.uniform(50, 2000)
        change = rng.normal(5, 15)
        z = change / 15
        signal = float(np.tanh(z * 0.5))
        return AltDataSignal(
            ticker=ticker, source_type=self.data_type,
            signal=round(signal, 4), confidence=0.6,
            value=round(postings, 0), change_pct=round(change, 2),
            z_score=round(z, 4),
            description=f"Active postings: {postings:.0f} (Δ{change:+.1f}%)",
        )


class PatentAdapter(_BaseAltAdapter):
    """Patent filing activity as innovation signal."""
    data_type = AltDataType.PATENT_FILINGS

    def fetch(self, ticker: str, seed: int | None = None) -> AltDataSignal:
        rng = np.random.RandomState(seed)
        filings = rng.uniform(5, 200)
        change = rng.normal(0, 20)
        z = change / 20
        signal = float(np.tanh(z * 0.3))
        return AltDataSignal(
            ticker=ticker, source_type=self.data_type,
            signal=round(signal, 4), confidence=0.5,
            value=round(filings, 0), change_pct=round(change, 2),
            z_score=round(z, 4),
            description=f"Patent filings: {filings:.0f} (Δ{change:+.1f}%)",
        )


ALL_ADAPTERS = [
    SatelliteAdapter(), WebTrafficAdapter(), SocialSentimentAdapter(),
    CreditCardAdapter(), JobPostingsAdapter(), PatentAdapter(),
]
