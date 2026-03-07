"""
src/data/external/persistence/repository.py
──────────────────────────────────────────────────────────────────────────────
CRUD operations for EDPL health and coverage persistence.

Provides methods to:
  - Save/load provider health snapshots
  - Log individual fetches
  - Persist analysis coverage reports
  - Log stale data usage
  - Prune old records (retention policy)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.data.external.coverage.models import SourceCoverageReport, SourceStatus
from src.data.external.persistence.models import (
    AnalysisCoverageRecord,
    ProviderFetchLogRecord,
    ProviderHealthSnapshotRecord,
    StaleDataUsageRecord,
)

logger = logging.getLogger("365advisers.external.persistence")


class EDPLRepository:
    """
    CRUD repository for EDPL health and coverage data.

    Usage:
        with SessionLocal() as session:
            repo = EDPLRepository(session)
            repo.save_coverage_report(report)
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Health Snapshots ──────────────────────────────────────────────────

    def save_health_snapshot(
        self,
        provider_name: str,
        domain: str,
        status: str,
        circuit_breaker_state: str = "closed",
        consecutive_failures: int = 0,
        last_success_at: datetime | None = None,
        last_failure_at: datetime | None = None,
        last_error: str | None = None,
        avg_latency_ms: float = 0.0,
        success_rate_24h: float = 0.0,
    ) -> None:
        """Persist a health snapshot for a provider."""
        record = ProviderHealthSnapshotRecord(
            provider_name=provider_name,
            domain=domain,
            status=status,
            circuit_breaker_state=circuit_breaker_state,
            consecutive_failures=consecutive_failures,
            last_success_at=last_success_at,
            last_failure_at=last_failure_at,
            last_error=last_error,
            avg_latency_ms=avg_latency_ms,
            success_rate_24h=success_rate_24h,
        )
        self._session.add(record)
        self._session.commit()

    def get_health_history(
        self,
        provider_name: str,
        hours: int = 24,
    ) -> list[ProviderHealthSnapshotRecord]:
        """Get health snapshots for a provider in the last N hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return (
            self._session.query(ProviderHealthSnapshotRecord)
            .filter(
                ProviderHealthSnapshotRecord.provider_name == provider_name,
                ProviderHealthSnapshotRecord.snapshot_at >= cutoff,
            )
            .order_by(ProviderHealthSnapshotRecord.snapshot_at.desc())
            .all()
        )

    # ── Fetch Logs ────────────────────────────────────────────────────────

    def log_fetch(
        self,
        provider_name: str,
        domain: str,
        ticker: str | None,
        success: bool,
        latency_ms: float = 0.0,
        error_message: str | None = None,
        cached: bool = False,
        fields_populated: int | None = None,
        fields_total: int | None = None,
    ) -> None:
        """Log a single fetch operation."""
        record = ProviderFetchLogRecord(
            provider_name=provider_name,
            domain=domain,
            ticker=ticker,
            success=success,
            latency_ms=latency_ms,
            error_message=error_message,
            cached=cached,
            fields_populated=fields_populated,
            fields_total=fields_total,
        )
        self._session.add(record)
        self._session.commit()

    # ── Coverage Reports ──────────────────────────────────────────────────

    def save_coverage_report(self, report: SourceCoverageReport) -> None:
        """Persist an analysis coverage report."""
        record = AnalysisCoverageRecord(
            analysis_id=report.analysis_id,
            ticker=report.ticker,
            completeness_score=report.completeness_score,
            completeness_label=report.completeness_label,
            sources_json=json.dumps(
                [s.model_dump(mode="json") for s in report.sources],
            ),
            messages_json=json.dumps(report.messages),
            partial_domains_json=json.dumps(report.partial_domains),
            unavailable_domains_json=json.dumps(report.unavailable_domains),
        )
        self._session.add(record)
        self._session.commit()

    def get_coverage_history(
        self,
        ticker: str,
        limit: int = 10,
    ) -> list[AnalysisCoverageRecord]:
        """Get coverage reports for a ticker."""
        return (
            self._session.query(AnalysisCoverageRecord)
            .filter(AnalysisCoverageRecord.ticker == ticker)
            .order_by(AnalysisCoverageRecord.created_at.desc())
            .limit(limit)
            .all()
        )

    # ── Stale Data Logging ────────────────────────────────────────────────

    def log_stale_usage(
        self,
        analysis_id: str,
        domain: str,
        provider_name: str,
        stale_age_seconds: float,
        freshness_label: str,
    ) -> None:
        """Log usage of stale cached data."""
        record = StaleDataUsageRecord(
            analysis_id=analysis_id,
            domain=domain,
            provider_name=provider_name,
            stale_age_seconds=stale_age_seconds,
            freshness_label=freshness_label,
        )
        self._session.add(record)
        self._session.commit()

    # ── Retention Pruning ─────────────────────────────────────────────────

    def prune_old_records(
        self,
        fetch_log_days: int = 7,
        health_snapshot_days: int = 7,
        stale_log_days: int = 30,
    ) -> dict[str, int]:
        """
        Remove records older than retention thresholds.

        Returns count of deleted records per table.
        """
        now = datetime.now(timezone.utc)
        counts: dict[str, int] = {}

        # Fetch logs
        cutoff = now - timedelta(days=fetch_log_days)
        deleted = (
            self._session.query(ProviderFetchLogRecord)
            .filter(ProviderFetchLogRecord.fetched_at < cutoff)
            .delete()
        )
        counts["provider_fetch_logs"] = deleted

        # Health snapshots
        cutoff = now - timedelta(days=health_snapshot_days)
        deleted = (
            self._session.query(ProviderHealthSnapshotRecord)
            .filter(ProviderHealthSnapshotRecord.snapshot_at < cutoff)
            .delete()
        )
        counts["provider_health_snapshots"] = deleted

        # Stale data logs
        cutoff = now - timedelta(days=stale_log_days)
        deleted = (
            self._session.query(StaleDataUsageRecord)
            .filter(StaleDataUsageRecord.used_at < cutoff)
            .delete()
        )
        counts["stale_data_usage"] = deleted

        self._session.commit()
        logger.info(f"EDPL retention pruning: {counts}")
        return counts
