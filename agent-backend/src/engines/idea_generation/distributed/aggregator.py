"""
src/engines/idea_generation/distributed/aggregator.py
──────────────────────────────────────────────────────────────────────────────
Result Aggregator — collects chunk results, deduplicates, and ranks.

Polls Celery task statuses, merges partial results, and updates
the ScanJob lifecycle. Returns an IdeaScanResult compatible with
the existing API contract.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.idea_generation.distributed.dispatcher import _jobs
from src.engines.idea_generation.distributed.models import (
    ChunkResult,
    ScanJob,
    ScanStatus,
)
from src.engines.idea_generation.models import (
    IdeaCandidate,
    IdeaScanResult,
)

logger = logging.getLogger("365advisers.idea_generation.distributed.aggregator")


class ResultAggregator:
    """
    Collects and merges distributed chunk results.

    Usage
    -----
    aggregator = ResultAggregator()
    result = aggregator.collect(scan_id)
    """

    def collect(self, scan_id: str) -> IdeaScanResult | None:
        """
        Poll tasks and aggregate results for a scan.

        Returns
        -------
        IdeaScanResult if results are available, None if scan not found.
        """
        job = _jobs.get(scan_id)
        if not job:
            return None

        all_ideas: list[IdeaCandidate] = []
        all_stats: dict[str, int] = {}
        total_duration = 0.0
        completed = 0
        failed = 0

        if job.task_ids:
            # Celery-based results
            try:
                from celery.result import AsyncResult
                from src.engines.idea_generation.celery_app import celery_app

                for task_id in job.task_ids:
                    result = AsyncResult(task_id, app=celery_app)

                    if result.state == "SUCCESS" and result.result:
                        data = result.result
                        ideas = [
                            IdeaCandidate(**d) for d in data.get("ideas", [])
                        ]
                        all_ideas.extend(ideas)
                        total_duration += data.get("duration_ms", 0)

                        # Merge detector stats
                        for k, v in data.get("detector_stats", {}).items():
                            all_stats[k] = all_stats.get(k, 0) + v

                        completed += 1

                    elif result.state == "FAILURE":
                        failed += 1

                    elif result.state == "PENDING":
                        pass  # Still processing

            except Exception as exc:
                logger.warning(f"AGGREGATE: Cannot poll Celery — {exc}")

        # Update job status
        job.completed_chunks = completed
        job.failed_chunks = failed
        job.progress_pct = round(
            (completed + failed) / max(job.total_chunks, 1) * 100, 1
        )

        if completed + failed >= job.total_chunks:
            if failed == 0:
                job.status = ScanStatus.COMPLETE
            elif completed > 0:
                job.status = ScanStatus.PARTIAL
            else:
                job.status = ScanStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
        else:
            job.status = ScanStatus.PROCESSING

        # Deduplicate by ticker + idea_type
        unique = self._deduplicate(all_ideas)

        # Rank using existing logic
        try:
            from src.engines.idea_generation.ranker import rank_ideas
            ranked = rank_ideas(unique)
        except ImportError:
            ranked = sorted(unique, key=lambda x: x.signal_strength, reverse=True)

        job.total_ideas = len(ranked)

        return IdeaScanResult(
            universe_size=job.total_tickers,
            ideas=ranked,
            scan_duration_ms=round(total_duration, 1),
            detector_stats=all_stats,
        )

    def get_status(self, scan_id: str) -> dict | None:
        """Get job status without aggregating results."""
        job = _jobs.get(scan_id)
        if not job:
            return None

        # Quick task status poll
        if job.task_ids and job.status == ScanStatus.DISPATCHED:
            try:
                from celery.result import AsyncResult
                from src.engines.idea_generation.celery_app import celery_app

                completed = sum(
                    1 for tid in job.task_ids
                    if AsyncResult(tid, app=celery_app).state == "SUCCESS"
                )
                failed = sum(
                    1 for tid in job.task_ids
                    if AsyncResult(tid, app=celery_app).state == "FAILURE"
                )
                job.completed_chunks = completed
                job.failed_chunks = failed
                job.progress_pct = round(
                    (completed + failed) / max(job.total_chunks, 1) * 100, 1
                )

                if completed + failed >= job.total_chunks:
                    job.status = ScanStatus.AGGREGATING
            except Exception:
                pass

        return job.model_dump(mode="json")

    @staticmethod
    def _deduplicate(ideas: list[IdeaCandidate]) -> list[IdeaCandidate]:
        """Remove duplicate ideas (same ticker + idea_type, keep highest strength)."""
        seen: dict[str, IdeaCandidate] = {}
        for idea in ideas:
            key = f"{idea.ticker}:{idea.idea_type.value}"
            existing = seen.get(key)
            if existing is None or idea.signal_strength > existing.signal_strength:
                seen[key] = idea
        return list(seen.values())
