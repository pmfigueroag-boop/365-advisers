"""
src/engines/idea_generation/backtest/snapshot_service.py
──────────────────────────────────────────────────────────────────────────────
Captures IdeaCandidate → IdeaSnapshot and persists to storage.

Single responsibility: snapshot creation and persistence.
Configurable via BacktestConfig (can be disabled entirely).
Emits observability metrics via the standard MetricsCollector.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from src.engines.idea_generation.backtest.models import (
    BacktestConfig,
    IdeaSnapshot,
    IdeaSnapshotRecord,
)
from src.engines.idea_generation.models import IdeaCandidate, IdeaScanResult
from src.engines.idea_generation.metrics import get_collector

logger = logging.getLogger("365advisers.idea_generation.backtest.snapshots")


class SnapshotService:
    """Creates and persists IdeaSnapshot records from scan results.

    Usage::

        svc = SnapshotService(config=BacktestConfig())
        snapshots = svc.capture_from_scan(scan_result)
    """

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self._config = config or BacktestConfig()

    @property
    def enabled(self) -> bool:
        return self._config.snapshot_enabled

    def capture_from_candidate(
        self,
        idea: IdeaCandidate,
        scan_id: str | None = None,
        scan_mode: str = "local",
        price_at_signal: float | None = None,
    ) -> IdeaSnapshot:
        """Convert a single IdeaCandidate into an IdeaSnapshot."""
        # Count signals by strength
        strong = sum(1 for s in idea.signals if s.strength.value == "strong")
        moderate = sum(1 for s in idea.signals if s.strength.value == "moderate")
        weak = sum(1 for s in idea.signals if s.strength.value == "weak")

        alpha_score = float(idea.metadata.get("composite_alpha_score", 0.0) or 0.0)
        source = idea.metadata.get("source", "legacy")

        return IdeaSnapshot(
            generated_at=idea.generated_at,
            scan_id=scan_id,
            ticker=idea.ticker,
            detector=idea.detector,
            idea_type=idea.idea_type.value,
            source=source,
            signal_strength=idea.signal_strength,
            confidence_score=idea.confidence_score,
            alpha_score=alpha_score,
            rank_score=float(idea.priority),
            active_signals_count=len(idea.signals),
            strong_signals_count=strong,
            moderate_signals_count=moderate,
            weak_signals_count=weak,
            scan_mode=scan_mode,
            registry_key=idea.detector,
            name=idea.name,
            sector=idea.sector,
            confidence_level=idea.confidence.value,
            price_at_signal=price_at_signal,
        )

    def capture_from_scan(
        self,
        scan_result: IdeaScanResult,
        scan_mode: str = "local",
        prices: dict[str, float] | None = None,
    ) -> list[IdeaSnapshot]:
        """Capture snapshots for all ideas in a scan result."""
        if not self.enabled:
            return []

        _prices = prices or {}
        snapshots: list[IdeaSnapshot] = []

        for idea in scan_result.ideas:
            snapshot = self.capture_from_candidate(
                idea,
                scan_id=scan_result.scan_id,
                scan_mode=scan_mode,
                price_at_signal=_prices.get(idea.ticker),
            )
            snapshots.append(snapshot)
            get_collector().increment("idea_snapshots_created_total", tags={
                "detector": idea.detector,
                "idea_type": idea.idea_type.value,
            })

        logger.info(
            "snapshots_captured",
            extra={
                "scan_id": scan_result.scan_id,
                "count": len(snapshots),
            },
        )
        return snapshots

    def persist(self, snapshots: list[IdeaSnapshot]) -> int:
        """Persist snapshots to database. Returns count persisted."""
        from src.data.database import SessionLocal

        persisted = 0
        with SessionLocal() as db:
            for snap in snapshots:
                try:
                    record = IdeaSnapshotRecord(
                        snapshot_id=snap.snapshot_id,
                        generated_at=snap.generated_at,
                        scan_id=snap.scan_id,
                        ticker=snap.ticker,
                        detector=snap.detector,
                        idea_type=snap.idea_type,
                        source=snap.source,
                        signal_strength=snap.signal_strength,
                        confidence_score=snap.confidence_score,
                        alpha_score=snap.alpha_score,
                        rank_score=snap.rank_score,
                        active_signals_count=snap.active_signals_count,
                        strong_signals_count=snap.strong_signals_count,
                        moderate_signals_count=snap.moderate_signals_count,
                        weak_signals_count=snap.weak_signals_count,
                        rationale=snap.rationale,
                        scan_mode=snap.scan_mode,
                        strategy_profile=snap.strategy_profile,
                        registry_key=snap.registry_key,
                        name=snap.name,
                        sector=snap.sector,
                        confidence_level=snap.confidence_level,
                        price_at_signal=snap.price_at_signal,
                        market_metadata_json=json.dumps(snap.market_metadata),
                        evaluation_status="pending",
                    )
                    db.add(record)
                    persisted += 1
                except Exception as exc:
                    logger.warning(
                        "snapshot_persist_failed",
                        extra={"snapshot_id": snap.snapshot_id, "error": str(exc)},
                    )
            db.commit()

        get_collector().gauge("pending_snapshots_gauge", persisted)
        return persisted

    @staticmethod
    def snapshot_to_dict(snapshot: IdeaSnapshot) -> dict:
        """Serialize a snapshot to a JSON-safe dict."""
        return snapshot.model_dump(mode="json")
