"""
src/engines/idea_generation/distributed/dispatcher.py
──────────────────────────────────────────────────────────────────────────────
Scan Dispatcher — splits the universe into chunks and submits them
to the Celery task queue for parallel processing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.engines.idea_generation.distributed.models import (
    DistributedScanConfig,
    ScanJob,
    ScanStatus,
)

logger = logging.getLogger("365advisers.idea_generation.distributed.dispatcher")

# In-memory job registry (production would use Redis/DB)
_jobs: dict[str, ScanJob] = {}


class ScanDispatcher:
    """
    Splits a ticker universe into chunks and dispatches to Celery workers.

    Usage
    -----
    dispatcher = ScanDispatcher()
    job = dispatcher.dispatch(tickers=["AAPL", "MSFT", ...])
    """

    def __init__(self, config: DistributedScanConfig | None = None) -> None:
        self.config = config or DistributedScanConfig()

    def dispatch(
        self,
        tickers: list[str],
        score_history: dict[str, float] | None = None,
        current_scores: dict[str, float] | None = None,
    ) -> ScanJob:
        """
        Split universe and submit chunks to the task queue.

        Falls back to local single-process scan if Celery/Redis
        is unavailable and fallback_to_local is True.
        """
        score_history = score_history or {}
        current_scores = current_scores or {}

        job = ScanJob(
            total_tickers=len(tickers),
            status=ScanStatus.PENDING,
        )

        # Chunk the universe
        chunks = self._chunk(tickers, self.config.chunk_size)
        job.total_chunks = len(chunks)

        logger.info(
            f"DISPATCH: scan_id={job.scan_id}, "
            f"{len(tickers)} tickers → {len(chunks)} chunks "
            f"(size={self.config.chunk_size})"
        )

        # Try to submit to Celery
        try:
            from src.engines.idea_generation.distributed.worker import (
                scan_chunk_task,
            )

            task_ids: list[str] = []
            for i, chunk in enumerate(chunks):
                # Build per-chunk score dicts
                chunk_hist = {t: score_history[t] for t in chunk if t in score_history}
                chunk_curr = {t: current_scores[t] for t in chunk if t in current_scores}

                task = scan_chunk_task.apply_async(
                    args=[job.scan_id, i, chunk, chunk_hist, chunk_curr],
                    queue="idea_scan",
                )
                task_ids.append(task.id)

            job.task_ids = task_ids
            job.status = ScanStatus.DISPATCHED

            logger.info(
                f"DISPATCH: Submitted {len(task_ids)} tasks to queue"
            )

        except Exception as exc:
            logger.warning(
                f"DISPATCH: Celery unavailable ({exc}), "
                f"{'falling back to local' if self.config.fallback_to_local else 'failing'}"
            )

            if self.config.fallback_to_local:
                job.status = ScanStatus.PROCESSING
                job.error = f"fallback_local: {exc}"
                # Mark for local processing
                job.task_ids = []
            else:
                job.status = ScanStatus.FAILED
                job.error = str(exc)

        # Register job
        _jobs[job.scan_id] = job
        return job

    def get_job(self, scan_id: str) -> ScanJob | None:
        """Retrieve a scan job by ID."""
        return _jobs.get(scan_id)

    def cancel_job(self, scan_id: str) -> bool:
        """Cancel a running scan."""
        job = _jobs.get(scan_id)
        if not job:
            return False

        if job.status in (ScanStatus.COMPLETE, ScanStatus.FAILED):
            return False

        # Revoke Celery tasks
        try:
            from src.engines.idea_generation.celery_app import celery_app
            for task_id in job.task_ids:
                celery_app.control.revoke(task_id, terminate=True)
        except Exception as exc:
            logger.warning(f"DISPATCH: Could not revoke tasks — {exc}")

        job.status = ScanStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        return True

    def list_jobs(self, limit: int = 20) -> list[ScanJob]:
        """List recent scan jobs."""
        sorted_jobs = sorted(
            _jobs.values(),
            key=lambda j: j.started_at,
            reverse=True,
        )
        return sorted_jobs[:limit]

    @staticmethod
    def _chunk(items: list[str], size: int) -> list[list[str]]:
        """Split a list into chunks of the given size."""
        return [items[i:i + size] for i in range(0, len(items), size)]
