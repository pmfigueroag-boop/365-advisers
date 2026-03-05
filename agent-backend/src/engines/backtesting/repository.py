"""
src/engines/backtesting/repository.py
──────────────────────────────────────────────────────────────────────────────
Persistence layer for backtest runs and results.

Uses the BacktestRun / BacktestResult SQLAlchemy models defined in
src/data/database.py.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from src.data.database import SessionLocal, BacktestRun, BacktestResult
from src.engines.backtesting.models import (
    BacktestConfig,
    BacktestReport,
    BacktestRunSummary,
    BacktestStatus,
    CalibrationSuggestion,
    SignalPerformanceRecord,
)

logger = logging.getLogger("365advisers.backtesting.repository")


class BacktestRepository:
    """CRUD operations for backtest persistence."""

    # ── Create ────────────────────────────────────────────────────────────

    @staticmethod
    def create_run(run_id: str, config: BacktestConfig) -> None:
        """Insert a new run record in PENDING state."""
        with SessionLocal() as db:
            row = BacktestRun(
                run_id=run_id,
                universe_json=json.dumps(config.universe),
                start_date=config.start_date.isoformat(),
                end_date=config.end_date.isoformat(),
                config_json=config.model_dump_json(),
                status=BacktestStatus.PENDING.value,
            )
            db.add(row)
            db.commit()
            logger.info(f"BACKTEST-REPO: Created run {run_id}")

    @staticmethod
    def update_run_status(
        run_id: str,
        status: BacktestStatus,
        signal_count: int = 0,
        execution_time: float = 0.0,
        error_message: str | None = None,
    ) -> None:
        """Update the status of an existing run."""
        with SessionLocal() as db:
            row = db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
            if row:
                row.status = status.value
                row.signal_count = signal_count
                row.execution_time_s = execution_time
                if error_message:
                    row.error_message = error_message
                db.commit()

    @staticmethod
    def save_results(run_id: str, results: list[SignalPerformanceRecord]) -> None:
        """Batch-insert signal performance records for a run."""
        with SessionLocal() as db:
            rows = []
            for r in results:
                rows.append(BacktestResult(
                    run_id=run_id,
                    signal_id=r.signal_id,
                    signal_name=r.signal_name,
                    category=r.category.value,
                    total_firings=r.total_firings,
                    hit_rate_json=json.dumps({str(k): v for k, v in r.hit_rate.items()}),
                    avg_return_json=json.dumps({str(k): v for k, v in r.avg_return.items()}),
                    avg_excess_return_json=json.dumps({str(k): v for k, v in r.avg_excess_return.items()}),
                    median_return_json=json.dumps({str(k): v for k, v in r.median_return.items()}),
                    sharpe_json=json.dumps({str(k): v for k, v in r.sharpe_ratio.items()}),
                    sortino_json=json.dumps({str(k): v for k, v in r.sortino_ratio.items()}),
                    max_drawdown=r.max_drawdown,
                    empirical_half_life=r.empirical_half_life,
                    optimal_hold_period=r.optimal_hold_period,
                    alpha_decay_curve_json=json.dumps(r.alpha_decay_curve),
                    t_statistic_json=json.dumps({str(k): v for k, v in r.t_statistic.items()}),
                    p_value_json=json.dumps({str(k): v for k, v in r.p_value.items()}),
                    confidence_level=r.confidence_level,
                    sample_size=r.sample_size,
                    universe_size=r.universe_size,
                    date_range=r.date_range,
                ))
            db.bulk_save_objects(rows)
            db.commit()
            logger.info(f"BACKTEST-REPO: Saved {len(rows)} results for run {run_id}")

    @staticmethod
    def save_calibration(run_id: str, suggestions: list[CalibrationSuggestion]) -> None:
        """Persist calibration suggestions for a run."""
        with SessionLocal() as db:
            row = db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()
            if row:
                row.calibration_json = json.dumps([s.model_dump() for s in suggestions])
                db.commit()

    # ── Read ──────────────────────────────────────────────────────────────

    @staticmethod
    def get_run(run_id: str) -> BacktestRun | None:
        """Fetch a single run by ID."""
        with SessionLocal() as db:
            return db.query(BacktestRun).filter(BacktestRun.run_id == run_id).first()

    @staticmethod
    def list_runs(limit: int = 20) -> list[BacktestRunSummary]:
        """List recent backtest runs."""
        with SessionLocal() as db:
            rows = (
                db.query(BacktestRun)
                .order_by(BacktestRun.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                BacktestRunSummary(
                    run_id=r.run_id,
                    universe_size=len(json.loads(r.universe_json or "[]")),
                    signal_count=r.signal_count or 0,
                    status=BacktestStatus(r.status),
                    date_range=f"{r.start_date} to {r.end_date}",
                    created_at=r.created_at or datetime.now(timezone.utc),
                    execution_time_seconds=r.execution_time_s or 0.0,
                )
                for r in rows
            ]

    @staticmethod
    def get_results(run_id: str) -> list[SignalPerformanceRecord]:
        """Load all signal results for a run."""
        with SessionLocal() as db:
            rows = (
                db.query(BacktestResult)
                .filter(BacktestResult.run_id == run_id)
                .all()
            )
            return [BacktestRepository._row_to_record(r) for r in rows]

    @staticmethod
    def get_signal_latest(signal_id: str) -> SignalPerformanceRecord | None:
        """Get the most recent backtest result for a specific signal."""
        with SessionLocal() as db:
            row = (
                db.query(BacktestResult)
                .filter(BacktestResult.signal_id == signal_id)
                .order_by(BacktestResult.created_at.desc())
                .first()
            )
            return BacktestRepository._row_to_record(row) if row else None

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_record(row: BacktestResult) -> SignalPerformanceRecord:
        """Convert a DB row to a Pydantic model."""
        def _load_int_keys(raw_json: str) -> dict[int, float]:
            data = json.loads(raw_json or "{}")
            return {int(k): float(v) for k, v in data.items()}

        from src.engines.alpha_signals.models import SignalCategory

        return SignalPerformanceRecord(
            signal_id=row.signal_id,
            signal_name=row.signal_name or "",
            category=SignalCategory(row.category),
            total_firings=row.total_firings or 0,
            hit_rate=_load_int_keys(row.hit_rate_json),
            avg_return=_load_int_keys(row.avg_return_json),
            avg_excess_return=_load_int_keys(row.avg_excess_return_json),
            median_return=_load_int_keys(row.median_return_json),
            sharpe_ratio=_load_int_keys(row.sharpe_json),
            sortino_ratio=_load_int_keys(row.sortino_json),
            max_drawdown=row.max_drawdown or 0.0,
            empirical_half_life=row.empirical_half_life,
            optimal_hold_period=row.optimal_hold_period,
            alpha_decay_curve=json.loads(row.alpha_decay_curve_json or "[]"),
            t_statistic=_load_int_keys(row.t_statistic_json),
            p_value=_load_int_keys(row.p_value_json),
            confidence_level=row.confidence_level or "LOW",
            sample_size=row.sample_size or 0,
            universe_size=row.universe_size or 0,
            date_range=row.date_range or "",
            backtest_date=row.created_at or datetime.now(timezone.utc),
        )
