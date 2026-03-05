"""
src/engines/idea_generation/distributed/models.py
──────────────────────────────────────────────────────────────────────────────
Data contracts for the distributed idea scanning system.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class ScanStatus(str, Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    PROCESSING = "processing"
    AGGREGATING = "aggregating"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChunkResult(BaseModel):
    """Result of processing a single chunk of tickers."""
    scan_id: str
    chunk_id: int
    tickers_processed: int = 0
    ideas_found: int = 0
    ideas: list[dict] = Field(default_factory=list)
    detector_stats: dict[str, int] = Field(default_factory=dict)
    duration_ms: float = 0.0
    error: str | None = None
    status: str = "pending"


class ScanJob(BaseModel):
    """Tracks the lifecycle of a distributed scan."""
    scan_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    total_tickers: int = 0
    total_chunks: int = 0
    completed_chunks: int = 0
    failed_chunks: int = 0
    task_ids: list[str] = Field(default_factory=list)
    chunk_size: int = 50
    status: ScanStatus = ScanStatus.PENDING
    progress_pct: float = 0.0
    total_ideas: int = 0
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    completed_at: datetime | None = None
    error: str | None = None


class DistributedScanConfig(BaseModel):
    """Configuration for distributed scanning."""
    chunk_size: int = Field(50, ge=10, le=200)
    max_workers: int = Field(10, ge=1, le=50)
    chunk_timeout_seconds: int = Field(120, ge=30)
    retry_limit: int = Field(3, ge=0, le=10)
    fallback_to_local: bool = Field(
        True, description="Use local engine if Redis unavailable",
    )
