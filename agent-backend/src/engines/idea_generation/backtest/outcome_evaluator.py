"""
src/engines/idea_generation/backtest/outcome_evaluator.py
──────────────────────────────────────────────────────────────────────────────
Evaluates IdeaSnapshots against actual market outcomes at defined horizons.

Responsibilities:
  - Fetch price at signal and price at horizon
  - Compute raw_return, excess_return
  - Classify hit / miss / outcome_label via HitPolicy
  - Handle missing data gracefully (no crashes)
  - Persist OutcomeResults
"""

from __future__ import annotations

import logging
import time as _time
from datetime import timedelta

from src.engines.idea_generation.backtest.models import (
    BacktestConfig,
    EvaluationHorizon,
    IdeaSnapshot,
    OutcomeResult,
    SnapshotOutcomeRecord,
)
from src.engines.idea_generation.backtest.market_data_provider import MarketDataProvider
from src.engines.idea_generation.metrics import get_collector

logger = logging.getLogger("365advisers.idea_generation.backtest.evaluator")


class OutcomeEvaluator:
    """Evaluates snapshots against realized market data.

    Usage::

        evaluator = OutcomeEvaluator(provider=my_provider, config=BacktestConfig())
        outcomes = evaluator.evaluate(snapshot)
    """

    def __init__(
        self,
        provider: MarketDataProvider,
        config: BacktestConfig | None = None,
    ) -> None:
        self._provider = provider
        self._config = config or BacktestConfig()

    def evaluate(
        self,
        snapshot: IdeaSnapshot,
        horizons: list[EvaluationHorizon] | None = None,
    ) -> list[OutcomeResult]:
        """Evaluate a single snapshot at all configured horizons.

        Returns a list of OutcomeResult, one per horizon.
        Never raises — missing data results in data_available=False.
        """
        _horizons = horizons or self._config.horizons
        results: list[OutcomeResult] = []

        get_collector().increment("snapshot_evaluations_started_total", tags={
            "detector": snapshot.detector,
            "idea_type": snapshot.idea_type,
        })

        start_ns = _time.monotonic_ns()

        for horizon in _horizons:
            try:
                result = self._evaluate_horizon(snapshot, horizon)
                results.append(result)
                get_collector().increment("outcomes_recorded_total", tags={
                    "horizon": horizon.value,
                    "outcome": result.outcome_label.value,
                })
            except Exception as exc:
                logger.warning(
                    "evaluation_failed",
                    extra={
                        "snapshot_id": snapshot.snapshot_id,
                        "horizon": horizon.value,
                        "error": str(exc),
                    },
                )
                get_collector().increment("snapshot_evaluations_failed_total", tags={
                    "horizon": horizon.value,
                })
                # Still produce a result with data_available=False
                results.append(OutcomeResult(
                    snapshot_id=snapshot.snapshot_id,
                    horizon=horizon,
                    data_available=False,
                ))

        elapsed_ms = (_time.monotonic_ns() - start_ns) / 1e6
        get_collector().timing("evaluation_duration_ms", elapsed_ms, tags={
            "detector": snapshot.detector,
        })
        get_collector().increment("snapshot_evaluations_completed_total", tags={
            "detector": snapshot.detector,
            "idea_type": snapshot.idea_type,
        })

        return results

    def _evaluate_horizon(
        self,
        snapshot: IdeaSnapshot,
        horizon: EvaluationHorizon,
    ) -> OutcomeResult:
        """Evaluate a snapshot at a single horizon."""
        # Get price at signal time
        price_at_signal = snapshot.price_at_signal
        if price_at_signal is None:
            price_at_signal = self._provider.get_price(
                snapshot.ticker, snapshot.generated_at,
            )

        # Get price at horizon
        horizon_date = snapshot.generated_at + timedelta(days=horizon.calendar_days)
        price_at_horizon = self._provider.get_price(snapshot.ticker, horizon_date)

        # Compute returns
        raw_return: float | None = None
        if price_at_signal and price_at_horizon and price_at_signal > 0:
            raw_return = (price_at_horizon - price_at_signal) / price_at_signal

        # Compute excess return if benchmark configured
        excess_return: float | None = None
        if raw_return is not None and self._config.benchmark_ticker:
            bench_at_signal = self._provider.get_price(
                self._config.benchmark_ticker, snapshot.generated_at,
            )
            bench_at_horizon = self._provider.get_price(
                self._config.benchmark_ticker, horizon_date,
            )
            if bench_at_signal and bench_at_horizon and bench_at_signal > 0:
                bench_return = (bench_at_horizon - bench_at_signal) / bench_at_signal
                excess_return = raw_return - bench_return

        # Classify
        policy = self._config.hit_policy
        outcome_label = policy.classify(raw_return, excess_return)
        is_hit = outcome_label.value == "win"

        data_available = price_at_signal is not None and price_at_horizon is not None

        return OutcomeResult(
            snapshot_id=snapshot.snapshot_id,
            horizon=horizon,
            price_at_signal=price_at_signal,
            price_at_horizon=price_at_horizon,
            raw_return=raw_return,
            excess_return=excess_return,
            is_hit=is_hit,
            outcome_label=outcome_label,
            data_available=data_available,
        )

    def evaluate_batch(
        self,
        snapshots: list[IdeaSnapshot],
        horizons: list[EvaluationHorizon] | None = None,
    ) -> list[OutcomeResult]:
        """Evaluate a batch of snapshots. Returns all outcomes flat."""
        all_outcomes: list[OutcomeResult] = []
        for snap in snapshots:
            outcomes = self.evaluate(snap, horizons)
            all_outcomes.extend(outcomes)
        return all_outcomes

    def persist_outcomes(self, outcomes: list[OutcomeResult], snapshots_by_id: dict[str, IdeaSnapshot] | None = None) -> int:
        """Persist outcome results to database. Returns count persisted."""
        from src.data.database import SessionLocal

        _snaps = snapshots_by_id or {}
        persisted = 0
        with SessionLocal() as db:
            for outcome in outcomes:
                try:
                    snap = _snaps.get(outcome.snapshot_id)
                    record = SnapshotOutcomeRecord(
                        snapshot_id=outcome.snapshot_id,
                        horizon=outcome.horizon.value,
                        evaluated_at=outcome.evaluated_at,
                        ticker=snap.ticker if snap else "",
                        detector=snap.detector if snap else "",
                        idea_type=snap.idea_type if snap else "",
                        confidence_score=snap.confidence_score if snap else 0.0,
                        signal_strength=snap.signal_strength if snap else 0.0,
                        alpha_score=snap.alpha_score if snap else 0.0,
                        price_at_signal=outcome.price_at_signal,
                        price_at_horizon=outcome.price_at_horizon,
                        raw_return=outcome.raw_return,
                        excess_return=outcome.excess_return,
                        max_favorable_excursion=outcome.max_favorable_excursion,
                        max_adverse_excursion=outcome.max_adverse_excursion,
                        drawdown_from_signal=outcome.drawdown_from_signal,
                        is_hit=outcome.is_hit,
                        outcome_label=outcome.outcome_label.value,
                        data_available=outcome.data_available,
                    )
                    db.add(record)
                    persisted += 1
                except Exception as exc:
                    logger.warning(
                        "outcome_persist_failed",
                        extra={"snapshot_id": outcome.snapshot_id, "error": str(exc)},
                    )
            db.commit()
        return persisted
