"""
src/data/external/coverage/models.py
──────────────────────────────────────────────────────────────────────────────
Pydantic models for source coverage metadata.

Defines SourceStatus, SourceCoverageReport, SourceFreshness, and
SourceConfidence — used to track which data sources contributed to each
analysis and with what quality.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from src.data.external.base import DataDomain


# ─── Source Freshness Classification ──────────────────────────────────────────

class FreshnessLevel(str, Enum):
    FRESH = "fresh"
    ACCEPTABLE = "acceptable"
    STALE = "stale"
    EXPIRED = "expired"


class SourceFreshness(BaseModel):
    """Freshness classification of a single data point."""
    domain: DataDomain
    fetched_at: datetime | None = None
    age_seconds: float = 0.0
    freshness: FreshnessLevel = FreshnessLevel.FRESH
    ttl_seconds: float = 0.0

    @classmethod
    def classify(
        cls, domain: DataDomain, fetched_at: datetime | None, ttl: float,
    ) -> SourceFreshness:
        """Classify freshness based on age vs TTL."""
        if fetched_at is None:
            return cls(
                domain=domain, freshness=FreshnessLevel.EXPIRED,
                age_seconds=float("inf"), ttl_seconds=ttl,
            )

        age = (datetime.now(timezone.utc) - fetched_at).total_seconds()
        if age < 0.5 * ttl:
            level = FreshnessLevel.FRESH
        elif age < 1.0 * ttl:
            level = FreshnessLevel.ACCEPTABLE
        elif age < 2.0 * ttl:
            level = FreshnessLevel.STALE
        else:
            level = FreshnessLevel.EXPIRED

        return cls(
            domain=domain, fetched_at=fetched_at,
            age_seconds=round(age, 1), freshness=level, ttl_seconds=ttl,
        )


# ─── Per-Source Status ────────────────────────────────────────────────────────

class SourceStatus(BaseModel):
    """Status of a single data source in a specific analysis run."""
    domain: DataDomain
    provider_name: str
    status: Literal["available", "degraded", "unavailable", "stale", "skipped"]
    latency_ms: float | None = None
    cached: bool = False
    stale_age_seconds: float | None = None
    error_message: str | None = None
    fields_populated: int = 0
    fields_total: int = 0
    coverage_ratio: float = 0.0
    freshness: SourceFreshness | None = None


# ─── Aggregate Coverage Report ───────────────────────────────────────────────

class SourceCoverageReport(BaseModel):
    """Aggregate coverage across all domains for one analysis run."""
    analysis_id: str = ""
    ticker: str | None = None
    sources: list[SourceStatus] = Field(default_factory=list)
    completeness_score: float = 0.0       # 0–100 composite
    completeness_label: str = "Unknown"
    partial_domains: list[str] = Field(default_factory=list)
    unavailable_domains: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def is_complete(self) -> bool:
        """All sources available, coverage > 95%."""
        return (
            self.completeness_score >= 95
            and len(self.unavailable_domains) == 0
        )

    def summary_message(self) -> str:
        """Human-readable one-line summary."""
        total = len(self.sources)
        available = sum(1 for s in self.sources if s.status in ("available", "stale"))
        return (
            f"Sources: {available}/{total} available | "
            f"Completeness: {self.completeness_score:.0f}/100"
            + (f" | ⚠ {', '.join(self.unavailable_domains)} unavailable"
               if self.unavailable_domains else "")
        )


# ─── Source Confidence ────────────────────────────────────────────────────────

class SourceConfidence(BaseModel):
    """Per-source confidence level based on historical reliability."""
    provider_name: str
    domain: DataDomain
    success_rate_24h: float = 0.0
    success_rate_7d: float = 0.0
    avg_latency_ms: float = 0.0
    data_completeness: float = 0.0        # avg coverage_ratio
    confidence_level: Literal["high", "medium", "low"] = "low"

    @classmethod
    def from_metrics(
        cls,
        provider_name: str,
        domain: DataDomain,
        success_rate_7d: float,
        data_completeness: float,
        **kwargs,
    ) -> SourceConfidence:
        """Classify confidence level from metrics."""
        if success_rate_7d > 0.95 and data_completeness > 0.8:
            level = "high"
        elif success_rate_7d > 0.80:
            level = "medium"
        else:
            level = "low"

        return cls(
            provider_name=provider_name,
            domain=domain,
            success_rate_7d=success_rate_7d,
            data_completeness=data_completeness,
            confidence_level=level,
            **kwargs,
        )
