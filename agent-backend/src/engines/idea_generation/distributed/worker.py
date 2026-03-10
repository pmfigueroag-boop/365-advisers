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
from src.engines.idea_generation.metrics import get_collector

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
    context_data: dict | None = None,
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
    context_data : dict | None
        Serialized ScanContext from the dispatcher. Contains
        ``score_history`` and ``current_scores`` for EventDetector.
        Falls back to the positional score_history / current_scores
        if not provided (backward compatibility).

    Returns
    -------
    dict
        Serialised chunk result.
    """
    logger.info(
        "chunk_started",
        extra={
            "scan_id": scan_id,
            "chunk_id": chunk_id,
            "chunk_size": len(tickers),
        },
    )

    try:
        from src.engines.idea_generation.engine import IdeaGenerationEngine

        engine = IdeaGenerationEngine()

        # Prefer context_data if provided (distributed path),
        # fall back to positional args (backward compat)
        hist = score_history
        curr = current_scores
        if context_data:
            hist = context_data.get("score_history", hist)
            curr = context_data.get("current_scores", curr)

        # Run the async scan in a sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                engine.scan(tickers, hist, curr)
            )
        finally:
            loop.close()

        serialised_ideas = [
            idea.model_dump(mode="json") for idea in result.ideas
        ]

        logger.info(
            "chunk_complete",
            extra={
                "scan_id": scan_id,
                "chunk_id": chunk_id,
                "ideas_found": len(serialised_ideas),
                "duration_ms": round(result.scan_duration_ms, 1),
            },
        )
        get_collector().timing("chunk_processing_ms", result.scan_duration_ms, tags={
            "mode": "distributed",
        })

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
            "chunk_failed",
            extra={
                "scan_id": scan_id,
                "chunk_id": chunk_id,
                "error": str(exc),
            },
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
