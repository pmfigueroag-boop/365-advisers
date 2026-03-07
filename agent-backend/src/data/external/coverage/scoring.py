"""
src/data/external/coverage/scoring.py
──────────────────────────────────────────────────────────────────────────────
Analysis Completeness Scorer — computes a composite 0–100 score.

Formula:
    ACS = Σ (weight_d × availability_d × freshness_d × coverage_d) / Σ weight_d × 100

Where:
  - weight_d:       relevance of domain to the current analysis type
  - availability_d: 1 if source responded, 0 if unavailable
  - freshness_d:    1.0=fresh, 0.7=acceptable, 0.4=stale, 0.1=expired
  - coverage_d:     fields_populated / fields_total
"""

from __future__ import annotations

from src.data.external.base import DataDomain
from src.data.external.coverage.models import FreshnessLevel, SourceStatus

# Default domain weights for single-ticker analysis
DEFAULT_WEIGHTS: dict[DataDomain, float] = {
    DataDomain.MARKET_DATA: 1.0,       # Core — always needed
    DataDomain.MACRO: 0.8,             # Essential for regime context
    DataDomain.INSTITUTIONAL: 0.7,     # Important for flow analysis
    DataDomain.SENTIMENT: 0.6,         # Valuable but supplementary
    DataDomain.OPTIONS: 0.5,           # Additive for volatility context
    DataDomain.ETF_FLOWS: 0.5,         # Sector rotation context
    DataDomain.FILING_EVENTS: 0.6,     # Material event detection
    DataDomain.GEOPOLITICAL: 0.3,      # Additive macro color
}

# Freshness → multiplier
FRESHNESS_MULTIPLIER: dict[FreshnessLevel, float] = {
    FreshnessLevel.FRESH: 1.0,
    FreshnessLevel.ACCEPTABLE: 0.7,
    FreshnessLevel.STALE: 0.4,
    FreshnessLevel.EXPIRED: 0.1,
}


class AnalysisCompletenessScorer:
    """
    Computes the Analysis Completeness Score (0–100).

    Usage:
        scorer = AnalysisCompletenessScorer()
        score = scorer.score(source_statuses)
    """

    def __init__(
        self,
        weights: dict[DataDomain, float] | None = None,
    ) -> None:
        self._weights = weights or DEFAULT_WEIGHTS

    def score(self, sources: list[SourceStatus]) -> float:
        """
        Compute the composite completeness score.

        For each source:
          ACS += weight × availability × freshness × coverage
        Then normalise by sum of weights × 100.
        """
        if not sources:
            return 0.0

        total_weighted = 0.0
        total_weight = 0.0

        for src in sources:
            weight = self._weights.get(src.domain, 0.3)
            total_weight += weight

            # Availability: 1 if responded, 0 if unavailable/skipped
            if src.status in ("available", "degraded", "stale"):
                availability = 1.0
            else:
                availability = 0.0
                total_weighted += 0.0
                continue

            # Freshness multiplier
            freshness_mult = 1.0
            if src.freshness is not None:
                freshness_mult = FRESHNESS_MULTIPLIER.get(
                    src.freshness.freshness, 0.5,
                )

            # Coverage ratio
            coverage = src.coverage_ratio if src.coverage_ratio > 0 else 0.5  # default 50% if unknown

            total_weighted += weight * availability * freshness_mult * coverage

        if total_weight == 0:
            return 0.0

        return round((total_weighted / total_weight) * 100, 1)
