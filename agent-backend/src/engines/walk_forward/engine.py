"""
src/engines/walk_forward/engine.py
──────────────────────────────────────────────────────────────────────────────
Walk-Forward Validation Engine — orchestrates the IS/OOS pipeline.

Reuses:
  - HistoricalEvaluator     for signal evaluation (no look-ahead)
  - BacktestEngine helpers  for OHLCV fetching
  - metrics.py              for hit-rate, Sharpe, excess-return calculation
  - ReturnTracker           for benchmark enrichment
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone

import pandas as pd

from src.engines.alpha_signals.models import AlphaSignalDefinition
from src.engines.alpha_signals.registry import registry as signal_registry
from src.engines.backtesting.engine import BacktestEngine
from src.engines.backtesting.historical_evaluator import HistoricalEvaluator
from src.engines.backtesting.metrics import (
    compute_avg_excess_return,
    compute_hit_rate,
    compute_sharpe,
)
from src.engines.backtesting.models import SignalEvent
from src.engines.backtesting.return_tracker import ReturnTracker
from src.engines.walk_forward.models import (
    WalkForwardConfig,
    WalkForwardFold,
    WalkForwardRun,
    WFSignalFoldResult,
)
from src.engines.walk_forward.stability_analyzer import StabilityAnalyzer
from src.engines.walk_forward.window_generator import WindowGenerator

logger = logging.getLogger("365advisers.walk_forward.engine")


class WalkForwardEngine:
    """
    Orchestrates walk-forward validation across temporal folds.

    Usage::

        engine = WalkForwardEngine()
        run = await engine.run(WalkForwardConfig(
            universe=["AAPL", "MSFT", "GOOGL"],
            start_date=date(2015, 1, 1),
            end_date=date(2025, 1, 1),
        ))
    """

    def __init__(self) -> None:
        self._window_gen = WindowGenerator()
        self._evaluator = HistoricalEvaluator()
        self._stability = StabilityAnalyzer()

    # ── Public API ────────────────────────────────────────────────────────

    async def run(self, config: WalkForwardConfig) -> WalkForwardRun:
        """
        Execute a full walk-forward validation run.

        Parameters
        ----------
        config : WalkForwardConfig
            Universe, date range, window sizes, signal filters, etc.

        Returns
        -------
        WalkForwardRun
            Complete results with per-fold metrics and stability scores.
        """
        start_time = time.time()

        run = WalkForwardRun(config=config, status="running")
        logger.info("WF-ENGINE: Starting run %s", run.run_id)

        try:
            # Step 1: Generate folds
            folds = self._window_gen.generate(config)
            if not folds:
                raise ValueError(
                    f"No folds generated for {config.start_date} → {config.end_date} "
                    f"with train={config.train_days}d, test={config.test_days}d"
                )
            run.folds = folds
            run.total_folds = len(folds)
            logger.info("WF-ENGINE: Generated %d folds", len(folds))

            # Step 2: Get signals
            signals = self._get_signals(config.signal_ids)
            if not signals:
                raise ValueError("No enabled signals to validate")
            logger.info("WF-ENGINE: Validating %d signals", len(signals))

            # Step 3: Fetch full historical data (covers all folds)
            all_tickers = list(set(config.universe + [config.benchmark_ticker]))
            ohlcv_data = await BacktestEngine._fetch_historical_data(
                all_tickers, config.start_date, config.end_date,
            )
            benchmark_ohlcv = ohlcv_data.get(config.benchmark_ticker, pd.DataFrame())

            # Step 4: Evaluate each fold
            self._evaluator.cooldown_factor = config.cooldown_factor
            all_fold_results: list[WFSignalFoldResult] = []

            for fold in folds:
                fold_results = self._evaluate_fold(
                    fold, signals, ohlcv_data, benchmark_ohlcv, config,
                )
                all_fold_results.extend(fold_results)

            # Step 5: Compute stability scores
            signal_meta = {
                s.id: (s.name, s.category) for s in signals
            }
            summaries = self._stability.analyze(
                all_fold_results, signal_meta, len(folds),
            )

            # Step 6: Build final report
            run.signal_summaries = summaries
            run.robust_signals = [
                s.signal_id for s in summaries
                if s.stability_class.value == "robust"
            ]
            run.overfit_signals = [
                s.signal_id for s in summaries
                if s.stability_class.value == "overfit"
            ]
            run.completed_at = datetime.now(timezone.utc)
            run.execution_time_seconds = round(time.time() - start_time, 2)
            run.status = "completed"

            logger.info(
                "WF-ENGINE: Run %s completed in %.1fs — %d signals, "
                "%d robust, %d overfit",
                run.run_id, run.execution_time_seconds,
                len(summaries), len(run.robust_signals), len(run.overfit_signals),
            )

        except Exception as exc:
            run.status = "failed"
            run.error_message = str(exc)
            run.execution_time_seconds = round(time.time() - start_time, 2)
            logger.error("WF-ENGINE: Run %s failed — %s", run.run_id, exc)

        return run

    # ── Internal ──────────────────────────────────────────────────────────

    def _evaluate_fold(
        self,
        fold: WalkForwardFold,
        signals: list[AlphaSignalDefinition],
        ohlcv_data: dict[str, pd.DataFrame],
        benchmark_ohlcv: pd.DataFrame,
        config: WalkForwardConfig,
    ) -> list[WFSignalFoldResult]:
        """
        Run IS evaluation → IS filter → OOS evaluation for a single fold.

        Returns one WFSignalFoldResult per signal.
        """
        results: list[WFSignalFoldResult] = []

        # ── Slice OHLCV to fold windows ───────────────────────────────────
        is_ohlcv = self._slice_ohlcv(ohlcv_data, fold.train_start, fold.train_end)
        oos_ohlcv = self._slice_ohlcv(ohlcv_data, fold.test_start, fold.test_end)
        is_bench = self._slice_df(benchmark_ohlcv, fold.train_start, fold.train_end)
        oos_bench = self._slice_df(benchmark_ohlcv, fold.test_start, fold.test_end)

        # ── Phase 1: In-Sample evaluation ─────────────────────────────────
        is_events = self._evaluate_signals(
            config.universe, is_ohlcv, signals, config.forward_windows,
        )
        is_events = ReturnTracker(is_bench).enrich(is_events, config.forward_windows)

        # Group IS events by signal
        is_by_signal: dict[str, list[SignalEvent]] = defaultdict(list)
        for e in is_events:
            is_by_signal[e.signal_id].append(e)

        # ── Phase 2: IS quality filter and OOS evaluation ─────────────────
        qualified_ids: set[str] = set()

        for signal in signals:
            sig_events = is_by_signal.get(signal.id, [])
            n_firings = len(sig_events)

            # Compute IS metrics
            is_hr = self._safe_hit_rate(sig_events, config.forward_windows)
            is_sharpe = self._safe_sharpe(sig_events, config.forward_windows)
            is_alpha = self._safe_alpha(sig_events, config.forward_windows)

            # Check qualification
            qualified = (
                n_firings >= config.min_train_events
                and is_hr >= config.is_hit_rate_threshold
                and is_sharpe >= config.is_sharpe_threshold
            )

            result = WFSignalFoldResult(
                signal_id=signal.id,
                signal_name=signal.name,
                fold_index=fold.fold_index,
                is_hit_rate=round(is_hr, 4),
                is_sharpe=round(is_sharpe, 4),
                is_alpha=round(is_alpha, 6),
                is_firings=n_firings,
                qualified=qualified,
            )

            if qualified:
                qualified_ids.add(signal.id)

            results.append(result)

        # ── Phase 3: OOS evaluation for qualified signals ─────────────────
        if qualified_ids:
            qual_signals = [s for s in signals if s.id in qualified_ids]
            oos_events = self._evaluate_signals(
                config.universe, oos_ohlcv, qual_signals, config.forward_windows,
            )
            oos_events = ReturnTracker(oos_bench).enrich(
                oos_events, config.forward_windows,
            )

            oos_by_signal: dict[str, list[SignalEvent]] = defaultdict(list)
            for e in oos_events:
                oos_by_signal[e.signal_id].append(e)

            # Enrich qualified results with OOS metrics
            for result in results:
                if result.qualified:
                    oos_evts = oos_by_signal.get(result.signal_id, [])
                    result.oos_hit_rate = round(
                        self._safe_hit_rate(oos_evts, config.forward_windows), 4,
                    )
                    result.oos_sharpe = round(
                        self._safe_sharpe(oos_evts, config.forward_windows), 4,
                    )
                    result.oos_alpha = round(
                        self._safe_alpha(oos_evts, config.forward_windows), 6,
                    )
                    result.oos_firings = len(oos_evts)

        logger.debug(
            "WF-ENGINE: Fold %d — %d/%d signals qualified",
            fold.fold_index, len(qualified_ids), len(signals),
        )
        return results

    def _evaluate_signals(
        self,
        universe: list[str],
        ohlcv_data: dict[str, pd.DataFrame],
        signals: list[AlphaSignalDefinition],
        forward_windows: list[int],
    ) -> list[SignalEvent]:
        """Evaluate signals across all tickers in the universe."""
        all_events: list[SignalEvent] = []
        for ticker in universe:
            ticker_ohlcv = ohlcv_data.get(ticker)
            if ticker_ohlcv is None or ticker_ohlcv.empty:
                continue
            events = self._evaluator.evaluate(
                ticker=ticker,
                ohlcv=ticker_ohlcv,
                signals=signals,
                forward_windows=forward_windows,
            )
            all_events.extend(events)
        return all_events

    @staticmethod
    def _get_signals(
        signal_ids: list[str] | None,
    ) -> list[AlphaSignalDefinition]:
        """Retrieve signal definitions from the registry."""
        if signal_ids:
            return [
                s for s in signal_registry.get_all()
                if s.id in signal_ids and s.enabled
            ]
        return signal_registry.get_enabled()

    @staticmethod
    def _slice_ohlcv(
        ohlcv_data: dict[str, pd.DataFrame],
        start: object,
        end: object,
    ) -> dict[str, pd.DataFrame]:
        """Slice all ticker DataFrames to a date range."""
        sliced: dict[str, pd.DataFrame] = {}
        for ticker, df in ohlcv_data.items():
            mask = (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))
            sub = df.loc[mask]
            if not sub.empty:
                sliced[ticker] = sub
        return sliced

    @staticmethod
    def _slice_df(df: pd.DataFrame, start: object, end: object) -> pd.DataFrame:
        """Slice a single DataFrame to a date range."""
        if df.empty:
            return df
        mask = (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))
        return df.loc[mask]

    # ── Metric helpers ────────────────────────────────────────────────────

    @staticmethod
    def _safe_hit_rate(events: list[SignalEvent], windows: list[int]) -> float:
        """Hit rate for the largest forward window, defaulting to 0.0."""
        if not events:
            return 0.0
        hr = compute_hit_rate(events, windows)
        # Use the largest window available
        target = max(windows)
        return hr.get(target, 0.0)

    @staticmethod
    def _safe_sharpe(events: list[SignalEvent], windows: list[int]) -> float:
        """Sharpe for the largest forward window, defaulting to 0.0."""
        if not events:
            return 0.0
        sharpes = compute_sharpe(events, windows)
        target = max(windows)
        val = sharpes.get(target, 0.0)
        if val != val:  # nan check
            return 0.0
        return val

    @staticmethod
    def _safe_alpha(events: list[SignalEvent], windows: list[int]) -> float:
        """Mean excess return for largest window, defaulting to 0.0."""
        if not events:
            return 0.0
        alphas = compute_avg_excess_return(events, windows)
        target = max(windows)
        val = alphas.get(target, 0.0)
        if val != val:  # nan check
            return 0.0
        return val
