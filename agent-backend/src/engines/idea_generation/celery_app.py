"""
src/engines/idea_generation/celery_app.py
──────────────────────────────────────────────────────────────────────────────
Celery application configuration for distributed idea scanning.

Requires a running Redis instance. Falls back gracefully if Redis
is unavailable — the system will continue using the single-process
IdeaGenerationEngine.scan() path.

Start workers with:
    celery -A src.engines.idea_generation.celery_app worker \
           --loglevel=info --concurrency=10 -Q idea_scan
"""

from __future__ import annotations

import os
import logging

from celery import Celery

logger = logging.getLogger("365advisers.idea_generation.celery")

# Redis connection — configurable via env var
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "idea_generation",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,                # Results expire after 1 hour
    # Worker settings
    worker_prefetch_multiplier=1,       # Fair scheduling
    worker_max_tasks_per_child=100,     # Recycle workers for memory
    # Queue routing
    task_default_queue="idea_scan",
    task_routes={
        "src.engines.idea_generation.distributed.worker.scan_chunk_task": {
            "queue": "idea_scan",
        },
    },
    # Retry behaviour
    task_acks_late=True,                # Re-queue on crash
    task_reject_on_worker_lost=True,    # Re-queue if worker dies
    # Time limits
    task_soft_time_limit=120,           # 2 minutes per chunk
    task_time_limit=180,                # Hard kill at 3 minutes
)

logger.info(f"Celery app configured with broker: {REDIS_URL}")
