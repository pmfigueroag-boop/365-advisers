"""
src/engines/idea_generation/distributed/worker.py
──────────────────────────────────────────────────────────────────────────────
Celery task definitions for distributed idea scanning.

Each task processes a single chunk of tickers using the existing
IdeaGenerationEngine, then returns serialised results for aggregation.
"""

from __future__ import annotations

import asyncio
import logging

from src.engines.idea_generation.celery_app import celery_app

logger = logging.getLogger("365advisers.idea_generation.distributed.worker")


@celery_app.task(
    bind=True,
    name="src.engines.idea_generation.distributed.worker.scan_chunk_task",
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=120,
    time_limit=180,
    acks_late=True,
)
def scan_chunk_task(
    self,
    scan_id: str,
    chunk_id: int,
    tickers: list[str],
    score_history: dict,
    current_scores: dict,
) -> dict:
    """
    Process a single chunk of tickers.

    Runs the existing IdeaGenerationEngine.scan() in an asyncio event loop,
    serialises the results, and returns them for aggregation.

    Parameters
    ----------
    self : Task
        Celery task instance (for retry support).
    scan_id : str
        Parent scan job ID.
    chunk_id : int
        Index of this chunk within the scan.
    tickers : list[str]
        Ticker symbols in this chunk.
    score_history : dict
        Previous scores for event detection.
    current_scores : dict
        Current scores.

    Returns
    -------
    dict
        Serialised chunk result.
    """
    logger.info(
        f"WORKER: Processing chunk {chunk_id} for scan {scan_id} "
        f"({len(tickers)} tickers)"
    )

    try:
        from src.engines.idea_generation.engine import IdeaGenerationEngine

        engine = IdeaGenerationEngine()

        # Run the async scan in a sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                engine.scan(tickers, score_history, current_scores)
            )
        finally:
            loop.close()

        serialised_ideas = [
            idea.model_dump(mode="json") for idea in result.ideas
        ]

        logger.info(
            f"WORKER: Chunk {chunk_id} complete — "
            f"{len(serialised_ideas)} ideas in {result.scan_duration_ms:.0f}ms"
        )

        return {
            "scan_id": scan_id,
            "chunk_id": chunk_id,
            "tickers_processed": len(tickers),
            "ideas_found": len(serialised_ideas),
            "ideas": serialised_ideas,
            "detector_stats": result.detector_stats,
            "duration_ms": result.scan_duration_ms,
            "status": "success",
            "error": None,
        }

    except Exception as exc:
        logger.error(
            f"WORKER: Chunk {chunk_id} failed — {exc}",
            exc_info=True,
        )

        # Retry with exponential backoff
        try:
            self.retry(
                exc=exc,
                countdown=self.default_retry_delay * (2 ** self.request.retries),
            )
        except self.MaxRetriesExceededError:
            return {
                "scan_id": scan_id,
                "chunk_id": chunk_id,
                "tickers_processed": 0,
                "ideas_found": 0,
                "ideas": [],
                "detector_stats": {},
                "duration_ms": 0.0,
                "status": "failed",
                "error": str(exc),
            }
