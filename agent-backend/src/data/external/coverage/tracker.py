"""
src/data/external/coverage/tracker.py
──────────────────────────────────────────────────────────────────────────────
CoverageTracker — builds per-analysis SourceCoverageReport.

Called by the FallbackRouter or orchestration pipeline after each domain
fetch completes.  Accumulates SourceStatus entries and generates the
final coverage report.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel

from src.config import get_settings
from src.data.external.base import DataDomain, ProviderResponse, ProviderStatus
from src.data.external.coverage.models import (
    FreshnessLevel,
    SourceCoverageReport,
    SourceFreshness,
    SourceStatus,
)
from src.data.external.coverage.scoring import AnalysisCompletenessScorer

logger = logging.getLogger("365advisers.external.coverage")

# Domain → config cache TTL key mapping
_DOMAIN_TTL_KEYS: dict[DataDomain, str] = {
    DataDomain.MARKET_DATA: "EDPL_CACHE_TTL_MARKET",
    DataDomain.ETF_FLOWS: "EDPL_CACHE_TTL_ETF_FLOWS",
    DataDomain.OPTIONS: "EDPL_CACHE_TTL_OPTIONS",
    DataDomain.INSTITUTIONAL: "EDPL_CACHE_TTL_INSTITUTIONAL",
    DataDomain.SENTIMENT: "EDPL_CACHE_TTL_SENTIMENT",
    DataDomain.MACRO: "EDPL_CACHE_TTL_MACRO",
    DataDomain.FILING_EVENTS: "EDPL_CACHE_TTL_FILING_EVENTS",
    DataDomain.GEOPOLITICAL: "EDPL_CACHE_TTL_GEOPOLITICAL",
}


class CoverageTracker:
    """
    Tracks source coverage during a single analysis run.

    Usage:
        tracker = CoverageTracker(ticker="AAPL")
        tracker.record(DataDomain.MARKET_DATA, response)
        tracker.record(DataDomain.MACRO, response)
        report = tracker.build_report()
    """

    def __init__(self, ticker: str | None = None) -> None:
        self._ticker = ticker
        self._analysis_id = str(uuid.uuid4())
        self._entries: list[SourceStatus] = []
        self._scorer = AnalysisCompletenessScorer()

    @property
    def analysis_id(self) -> str:
        return self._analysis_id

    def record(
        self,
        domain: DataDomain,
        response: ProviderResponse,
        data_contract: BaseModel | None = None,
    ) -> SourceStatus:
        """
        Record the result of a domain fetch.

        Parameters
        ----------
        domain : DataDomain
        response : ProviderResponse from the FallbackRouter
        data_contract : The typed contract object (for field coverage counting)
        """
        settings = get_settings()
        ttl_key = _DOMAIN_TTL_KEYS.get(domain, "EDPL_CACHE_TTL_MARKET")
        ttl = getattr(settings, ttl_key, 900)

        # Determine status
        if response.ok:
            if response.cached:
                status_label = "stale" if response.status == ProviderStatus.STALE else "available"
            else:
                status_label = "available"
        elif response.status == ProviderStatus.DISABLED:
            status_label = "skipped"
        elif response.data is not None:
            status_label = "degraded"
        else:
            status_label = "unavailable"

        # Count field coverage
        fields_populated, fields_total = 0, 0
        if data_contract is not None:
            fields_total = len(data_contract.model_fields)
            for name, field_info in data_contract.model_fields.items():
                value = getattr(data_contract, name, None)
                if value is not None and value != [] and value != {} and value != "":
                    fields_populated += 1

        coverage_ratio = fields_populated / fields_total if fields_total > 0 else 0.0

        # Freshness
        fetched_at_val = getattr(data_contract, "fetched_at", None) if data_contract else None
        freshness = SourceFreshness.classify(domain, fetched_at_val, ttl)

        # Stale age
        stale_age = None
        if freshness.freshness in (FreshnessLevel.STALE, FreshnessLevel.EXPIRED):
            stale_age = freshness.age_seconds

        entry = SourceStatus(
            domain=domain,
            provider_name=response.provider_name,
            status=status_label,
            latency_ms=response.latency_ms,
            cached=response.cached,
            stale_age_seconds=stale_age,
            error_message=response.error,
            fields_populated=fields_populated,
            fields_total=fields_total,
            coverage_ratio=round(coverage_ratio, 3),
            freshness=freshness,
        )

        self._entries.append(entry)
        return entry

    def record_skipped(self, domain: DataDomain, reason: str = "disabled") -> None:
        """Record a domain that was intentionally skipped."""
        self._entries.append(SourceStatus(
            domain=domain,
            provider_name="none",
            status="skipped",
            error_message=reason,
        ))

    def build_report(self) -> SourceCoverageReport:
        """Build the final coverage report for this analysis."""
        # Compute completeness score
        completeness = self._scorer.score(self._entries)

        # Classify
        if completeness >= 90:
            label = "Full Coverage"
        elif completeness >= 70:
            label = "High Coverage"
        elif completeness >= 50:
            label = "Moderate Coverage"
        elif completeness >= 30:
            label = "Partial Coverage"
        else:
            label = "Minimal Coverage"

        # Identify partial and unavailable domains
        partial: list[str] = []
        unavailable: list[str] = []
        for entry in self._entries:
            if entry.status == "unavailable":
                unavailable.append(entry.domain.value)
            elif entry.status in ("degraded", "stale") or entry.coverage_ratio < 1.0:
                partial.append(entry.domain.value)

        # Generate messages
        messages = self._generate_messages(partial, unavailable)

        return SourceCoverageReport(
            analysis_id=self._analysis_id,
            ticker=self._ticker,
            sources=self._entries,
            completeness_score=completeness,
            completeness_label=label,
            partial_domains=partial,
            unavailable_domains=unavailable,
            messages=messages,
        )

    @staticmethod
    def _generate_messages(
        partial: list[str], unavailable: list[str],
    ) -> list[str]:
        """Generate human-readable coverage messages."""
        messages: list[str] = []

        domain_messages = {
            "macro": "Macro context unavailable — regime detection using fallback heuristics.",
            "filing_events": "SEC filing data unavailable — material event detection skipped.",
            "geopolitical": "Geopolitical intelligence unavailable.",
            "sentiment": "News sentiment data unavailable.",
            "institutional": "Institutional flow data unavailable.",
            "options": "Options intelligence unavailable.",
            "etf_flows": "ETF flow data unavailable.",
            "market_data": "Core market data unavailable — analysis quality significantly reduced.",
        }

        for domain in unavailable:
            msg = domain_messages.get(domain, f"{domain} data unavailable.")
            messages.append(msg)

        stale_messages = {
            "geopolitical": "Geopolitical intelligence delayed; using cached data.",
            "macro": "Macro context delayed; using cached data.",
            "sentiment": "News sentiment delayed; using cached data.",
        }

        for domain in partial:
            msg = stale_messages.get(domain)
            if msg:
                messages.append(msg)

        return messages
