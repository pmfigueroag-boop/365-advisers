"""
src/engines/backtesting/engine.py
──────────────────────────────────────────────────────────────────────────────
Alpha Signal Backtesting Engine — facade orchestrator.

Coordinates the full backtesting pipeline:
  1. Fetch historical OHLCV for universe + benchmark
  2. Retrieve enabled signal definitions from the registry
  3. Walk-forward signal evaluation per ticker
  4. Enrich events with benchmark returns
  5. Calculate per-signal performance metrics
  6. Build category summaries and calibration suggestions
  7. Persist results and return the full report
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from uuid import uuid4

import yfinance as yf
import pandas as pd

from src.engines.alpha_signals.models import AlphaSignalDefinition, SignalCategory
from src.engines.alpha_signals.registry import registry as signal_registry
from src.engines.backtesting.fundamental_provider import FundamentalProvider
from src.engines.backtesting.historical_evaluator import HistoricalEvaluator
from src.engines.backtesting.metrics import (
    classify_confidence,
    compute_alpha_decay_curve,
    compute_avg_excess_return,
    compute_avg_return,
    compute_empirical_half_life,
    compute_hit_rate,
    compute_max_drawdown,
    compute_median_return,
    compute_sharpe,
    compute_sortino,
    compute_t_statistic,
    find_optimal_hold_period,
)
from src.engines.backtesting.models import (
    BacktestConfig,
    BacktestReport,
    BacktestRunSummary,
    BacktestStatus,
    CombinationBacktestResult,
    RegimePerformanceReport,
    SignalEvent,
    SignalPerformanceRecord,
)
from src.engines.backtesting.regime_detector import MarketRegime, RegimeDetector
from src.engines.backtesting.report_builder import (
    build_category_summaries,
    generate_calibration_suggestions,
    identify_top_signals,
    identify_underperformers,
)
from src.engines.backtesting.repository import BacktestRepository
from src.engines.backtesting.performance_repository import SignalPerformanceRepository
from src.engines.backtesting.return_tracker import ReturnTracker

logger = logging.getLogger("365advisers.backtesting.engine")

# Concurrency limiter for yfinance requests
_MAX_CONCURRENT = 3


class BacktestEngine:
    """
    Facade for the Alpha Signal Backtesting Engine.

    Usage
    -----
    engine = BacktestEngine()
    report = await engine.run(BacktestConfig(
        universe=["AAPL", "MSFT", "GOOGL"],
        start_date=date(2023, 1, 1),
    ))
    """

    def __init__(self) -> None:
        self._evaluator = HistoricalEvaluator()
        self._repo = BacktestRepository
        self._perf_repo = SignalPerformanceRepository

    # ── Public API ────────────────────────────────────────────────────────

    async def run(self, config: BacktestConfig) -> BacktestReport:
        """
        Execute a full backtesting run.

        Parameters
        ----------
        config : BacktestConfig
            Universe, date range, forward windows, etc.

        Returns
        -------
        BacktestReport
            Complete results with per-signal metrics and calibration.
        """
        run_id = str(uuid4())
        start_time = time.time()

        logger.info(
            f"BACKTEST: Starting run {run_id} — "
            f"{len(config.universe)} tickers, "
            f"{config.start_date} to {config.end_date}"
        )

        # Persist run in RUNNING state
        self._repo.create_run(run_id, config)
        self._repo.update_run_status(run_id, BacktestStatus.RUNNING)

        try:
            report = await self._execute_pipeline(run_id, config, start_time)
            return report
        except Exception as exc:
            elapsed = time.time() - start_time
            self._repo.update_run_status(
                run_id, BacktestStatus.FAILED,
                execution_time=elapsed,
                error_message=str(exc),
            )
            logger.error(f"BACKTEST: Run {run_id} failed — {exc}")
            return BacktestReport(
                run_id=run_id,
                config=config,
                status=BacktestStatus.FAILED,
                error_message=str(exc),
                execution_time_seconds=elapsed,
            )

    async def get_report(self, run_id: str) -> BacktestReport | None:
        """Retrieve a previously completed report."""
        run = self._repo.get_run(run_id)
        if not run:
            return None

        results = self._repo.get_results(run_id)
        category_summaries = build_category_summaries(results)
        top = identify_top_signals(results)
        under = identify_underperformers(results)

        import json
        from src.engines.backtesting.models import CalibrationSuggestion
        calibration = []
        try:
            raw = json.loads(run.calibration_json or "[]")
            calibration = [CalibrationSuggestion(**s) for s in raw]
        except Exception:
            pass

        config_data = json.loads(run.config_json or "{}")

        return BacktestReport(
            run_id=run_id,
            config=BacktestConfig(**config_data) if config_data else BacktestConfig(
                universe=json.loads(run.universe_json or "[]"),
                start_date=date.fromisoformat(run.start_date),
                end_date=date.fromisoformat(run.end_date),
            ),
            signal_results=results,
            category_summaries=category_summaries,
            top_signals=top,
            underperforming_signals=under,
            calibration_suggestions=calibration,
            status=BacktestStatus(run.status),
            execution_time_seconds=run.execution_time_s or 0.0,
            completed_at=run.created_at,
        )

    def get_signal_performance(self, signal_id: str) -> SignalPerformanceRecord | None:
        """Get the latest backtest result for a specific signal."""
        return self._repo.get_signal_latest(signal_id)

    def list_runs(self, limit: int = 20) -> list[BacktestRunSummary]:
        """List recent backtest runs."""
        return self._repo.list_runs(limit)

    # ── Pipeline ──────────────────────────────────────────────────────────

    async def _execute_pipeline(
        self,
        run_id: str,
        config: BacktestConfig,
        start_time: float,
    ) -> BacktestReport:
        """Core pipeline: fetch → evaluate → metrics → report."""

        # Step 1: Get signals
        signals = self._get_signals(config.signal_ids)
        if not signals:
            raise ValueError("No enabled signals to backtest")

        logger.info(f"BACKTEST: Evaluating {len(signals)} signals")

        # Step 2: Fetch historical data
        ohlcv_data = await self._fetch_historical_data(
            config.universe + [config.benchmark_ticker],
            config.start_date,
            config.end_date,
        )

        # Step 3: Fundamental snapshots (if enabled)
        fund_provider = FundamentalProvider() if config.include_fundamentals else None

        # Step 4: Walk-forward evaluation per ticker
        all_events: list[SignalEvent] = []
        benchmark_ohlcv = ohlcv_data.get(config.benchmark_ticker, pd.DataFrame())
        return_tracker = ReturnTracker(benchmark_ohlcv)

        self._evaluator.cooldown_factor = config.cooldown_factor
        total_tickers = len(config.universe)

        for t_idx, ticker in enumerate(config.universe, 1):
            ticker_ohlcv = ohlcv_data.get(ticker)
            if ticker_ohlcv is None or ticker_ohlcv.empty:
                logger.warning(f"BACKTEST: No data for {ticker}, skipping")
                continue

            # Fetch fundamental snapshots if enabled
            fund_snapshots = None
            if fund_provider is not None:
                fund_snapshots = fund_provider.get_snapshots(
                    ticker, config.start_date, config.end_date, ticker_ohlcv,
                )

            events = self._evaluator.evaluate(
                ticker=ticker,
                ohlcv=ticker_ohlcv,
                signals=signals,
                forward_windows=config.forward_windows,
                fundamental_snapshots=fund_snapshots,
            )

            # Step 5: Enrich with benchmark returns
            events = return_tracker.enrich(events, config.forward_windows)
            all_events.extend(events)

            if t_idx % 10 == 0 or t_idx == total_tickers:
                logger.info(f"BACKTEST: Progress {t_idx}/{total_tickers} tickers evaluated")

        logger.info(f"BACKTEST: Total signal events: {len(all_events)}")

        # Step 4b: Persist raw events to Signal Performance Database
        signal_names = {s.id: s.name for s in signals}
        event_count = self._perf_repo.save_events(all_events, run_id, signal_names)
        logger.info(f"BACKTEST: Persisted {event_count} events to performance DB")

        # Step 5: Compute per-signal metrics
        results = self._compute_signal_metrics(
            all_events, signals, config
        )

        # Step 6: Build report
        category_summaries = build_category_summaries(results)
        top = identify_top_signals(results)
        under = identify_underperformers(results)
        calibration = generate_calibration_suggestions(results)

        elapsed = time.time() - start_time

        # Step 7: Persist
        self._repo.save_results(run_id, results)
        self._repo.save_calibration(run_id, calibration)
        self._repo.update_run_status(
            run_id, BacktestStatus.COMPLETED,
            signal_count=len(signals),
            execution_time=elapsed,
        )

        report = BacktestReport(
            run_id=run_id,
            config=config,
            signal_results=results,
            category_summaries=category_summaries,
            top_signals=top,
            underperforming_signals=under,
            calibration_suggestions=calibration,
            completed_at=datetime.now(timezone.utc),
            execution_time_seconds=round(elapsed, 2),
            status=BacktestStatus.COMPLETED,
        )

        logger.info(
            f"BACKTEST: Run {run_id} completed in {elapsed:.1f}s — "
            f"{len(results)} signal results, {len(calibration)} calibration suggestions"
        )

        return report

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _get_signals(
        signal_ids: list[str] | None,
    ) -> list[AlphaSignalDefinition]:
        """Retrieve signal definitions from the registry."""
        if signal_ids:
            return [
                s for s in signal_registry.get_enabled()
                if s.id in signal_ids
            ]
        return signal_registry.get_enabled()

    @staticmethod
    async def _fetch_historical_data(
        tickers: list[str],
        start_date: date,
        end_date: date,
    ) -> dict[str, pd.DataFrame]:
        """
        Fetch OHLCV for all tickers using yfinance.

        Runs in a thread pool to avoid blocking the event loop.
        """
        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
        results: dict[str, pd.DataFrame] = {}

        async def fetch_one(ticker: str) -> None:
            async with semaphore:
                try:
                    loop = asyncio.get_event_loop()
                    df = await loop.run_in_executor(
                        None,
                        lambda t=ticker: yf.download(
                            t,
                            start=start_date.isoformat(),
                            end=end_date.isoformat(),
                            progress=False,
                            auto_adjust=True,
                        ),
                    )
                    if df is not None and not df.empty:
                        # Flatten MultiIndex columns if present
                        if isinstance(df.columns, pd.MultiIndex):
                            # Try to extract this ticker's slice first
                            try:
                                df = df.xs(ticker, level=1, axis=1)
                            except (KeyError, TypeError):
                                df.columns = df.columns.get_level_values(0)
                        results[ticker] = df
                        logger.info(f"BACKTEST: Fetched {len(df)} bars for {ticker}")
                    else:
                        logger.warning(f"BACKTEST: No data returned for {ticker}")
                except Exception as exc:
                    logger.error(f"BACKTEST: Failed to fetch {ticker} -- {exc}")

        # Deduplicate tickers
        unique_tickers = list(set(tickers))
        tasks = [fetch_one(t) for t in unique_tickers]
        await asyncio.gather(*tasks)

        return results

    @staticmethod
    def _compute_signal_metrics(
        events: list[SignalEvent],
        signals: list[AlphaSignalDefinition],
        config: BacktestConfig,
    ) -> list[SignalPerformanceRecord]:
        """Compute performance metrics per signal from all events."""
        # Group events by signal_id
        by_signal: dict[str, list[SignalEvent]] = defaultdict(list)
        for e in events:
            by_signal[e.signal_id].append(e)

        # Build a quick lookup for signal definitions
        signal_map = {s.id: s for s in signals}

        results: list[SignalPerformanceRecord] = []
        windows = config.forward_windows

        for signal_id, signal_events in by_signal.items():
            sig_def = signal_map.get(signal_id)
            if not sig_def:
                continue

            n = len(signal_events)

            # Core metrics
            hit_rate = compute_hit_rate(signal_events, windows)
            avg_ret = compute_avg_return(signal_events, windows)
            avg_excess = compute_avg_excess_return(signal_events, windows)
            median_ret = compute_median_return(signal_events, windows)

            # Risk-adjusted
            sharpe = compute_sharpe(signal_events, windows)
            sortino = compute_sortino(signal_events, windows)
            max_dd = compute_max_drawdown(signal_events)

            # Decay curve
            decay_curve = compute_alpha_decay_curve(signal_events)
            emp_half_life = compute_empirical_half_life(decay_curve)
            opt_hold = find_optimal_hold_period(sharpe)

            # Statistical significance
            t_stats, p_vals = compute_t_statistic(signal_events, windows)
            confidence = classify_confidence(p_vals, n)

            results.append(SignalPerformanceRecord(
                signal_id=signal_id,
                signal_name=sig_def.name,
                category=sig_def.category,
                total_firings=n,
                hit_rate=hit_rate,
                avg_return=avg_ret,
                avg_excess_return=avg_excess,
                median_return=median_ret,
                sharpe_ratio=sharpe,
                sortino_ratio=sortino,
                max_drawdown=max_dd,
                empirical_half_life=emp_half_life,
                optimal_hold_period=opt_hold,
                alpha_decay_curve=decay_curve,
                t_statistic=t_stats,
                p_value=p_vals,
                confidence_level=confidence,
                sample_size=n,
                universe_size=len(config.universe),
                date_range=f"{config.start_date} to {config.end_date}",
            ))

        # Sort by Sharpe (20-day) descending
        results.sort(
            key=lambda r: r.sharpe_ratio.get(20, 0.0),
            reverse=True,
        )

        return results

    # ── Combination Backtest ──────────────────────────────────────────────

    async def run_combination(
        self,
        config: BacktestConfig,
        signal_groups: list[list[str]],
    ) -> list[CombinationBacktestResult]:
        """
        Test signal combinations using AND logic.

        For each group of signal IDs, finds dates where ALL signals in
        the group fired simultaneously, then measures forward returns
        and compares against individual signal performance.

        Parameters
        ----------
        config : BacktestConfig
            Universe, date range, forward windows.
        signal_groups : list[list[str]]
            Each inner list is a combination to test.

        Returns
        -------
        list[CombinationBacktestResult]
        """
        # Fetch data and run walk-forward for the full universe
        all_signals = self._get_signals(None)
        if not all_signals:
            return []

        ohlcv_data = await self._fetch_historical_data(
            config.universe + [config.benchmark_ticker],
            config.start_date,
            config.end_date,
        )

        benchmark_ohlcv = ohlcv_data.get(config.benchmark_ticker, pd.DataFrame())
        return_tracker = ReturnTracker(benchmark_ohlcv)
        self._evaluator.cooldown_factor = config.cooldown_factor

        # Collect all events
        all_events: list[SignalEvent] = []
        for ticker in config.universe:
            ticker_ohlcv = ohlcv_data.get(ticker)
            if ticker_ohlcv is None or ticker_ohlcv.empty:
                continue
            events = self._evaluator.evaluate(
                ticker=ticker, ohlcv=ticker_ohlcv,
                signals=all_signals, forward_windows=config.forward_windows,
            )
            events = return_tracker.enrich(events, config.forward_windows)
            all_events.extend(events)

        # Group events by (ticker, fired_date) for AND-join
        from collections import defaultdict
        event_index: dict[tuple[str, date], dict[str, SignalEvent]] = defaultdict(dict)
        individual_counts: dict[str, int] = defaultdict(int)

        for e in all_events:
            event_index[(e.ticker, e.fired_date)][e.signal_id] = e
            individual_counts[e.signal_id] += 1

        results: list[CombinationBacktestResult] = []

        for group in signal_groups:
            if len(group) < 2:
                continue

            sorted_ids = sorted(group)
            combo_id = "+".join(sorted_ids)

            # Find joint firings: dates where ALL signals fired
            joint_events: list[SignalEvent] = []
            for (ticker, fired_date), sig_map in event_index.items():
                if all(sid in sig_map for sid in sorted_ids):
                    # Use the first signal's event as the carrier
                    representative = sig_map[sorted_ids[0]]
                    # Average forward returns across all signals
                    avg_fwd: dict[int, float] = {}
                    avg_exc: dict[int, float] = {}
                    for w in config.forward_windows:
                        vals = [sig_map[s].forward_returns.get(w) for s in sorted_ids]
                        exc_vals = [sig_map[s].excess_returns.get(w) for s in sorted_ids]
                        clean = [v for v in vals if v is not None]
                        clean_exc = [v for v in exc_vals if v is not None]
                        if clean:
                            avg_fwd[w] = sum(clean) / len(clean)
                        if clean_exc:
                            avg_exc[w] = sum(clean_exc) / len(clean_exc)

                    joint_events.append(representative.model_copy(update={
                        "forward_returns": avg_fwd,
                        "excess_returns": avg_exc,
                    }))

            if not joint_events:
                continue

            # Compute metrics for the combination
            windows = config.forward_windows
            combo_hit = compute_hit_rate(joint_events, windows)
            combo_ret = compute_avg_return(joint_events, windows)
            combo_exc = compute_avg_excess_return(joint_events, windows)
            combo_sharpe = compute_sharpe(joint_events, windows)

            # Incremental alpha: combo T+20 excess vs. best individual T+20 excess
            ref_w = 20
            best_individual_excess = 0.0
            for sid in sorted_ids:
                sid_events = [e for e in all_events if e.signal_id == sid]
                if sid_events:
                    ind_exc = compute_avg_excess_return(sid_events, [ref_w])
                    ind_val = ind_exc.get(ref_w, 0.0)
                    best_individual_excess = max(best_individual_excess, ind_val)

            inc_alpha = combo_exc.get(ref_w, 0.0) - best_individual_excess

            # Synergy: 1 - (joint / min(individual counts))
            min_individual = min(individual_counts.get(s, 0) for s in sorted_ids)
            synergy = 1.0 - (len(joint_events) / max(min_individual, 1))
            synergy = max(0.0, min(1.0, synergy))

            results.append(CombinationBacktestResult(
                combination_id=combo_id,
                signal_ids=sorted_ids,
                joint_firings=len(joint_events),
                individual_firings={s: individual_counts.get(s, 0) for s in sorted_ids},
                hit_rate=combo_hit,
                avg_return=combo_ret,
                avg_excess_return=combo_exc,
                sharpe=combo_sharpe,
                incremental_alpha=round(inc_alpha, 6),
                synergy_score=round(synergy, 4),
            ))

        logger.info(
            "BACKTEST-COMBO: Tested %d combinations, %d had joint firings",
            len(signal_groups), len(results),
        )
        return results

    # ── Regime-Conditional Backtest ───────────────────────────────────────

    async def run_regime_conditional(
        self,
        config: BacktestConfig,
    ) -> list[RegimePerformanceReport]:
        """
        Run backtests partitioned by market regime.

        Classifies each day as Bull / Bear / Range / HighVol using the
        benchmark, then computes per-signal metrics within each regime.

        Returns
        -------
        list[RegimePerformanceReport]
            One report per signal with per-regime breakdown.
        """
        signals = self._get_signals(config.signal_ids)
        if not signals:
            return []

        ohlcv_data = await self._fetch_historical_data(
            config.universe + [config.benchmark_ticker],
            config.start_date,
            config.end_date,
        )

        benchmark_ohlcv = ohlcv_data.get(config.benchmark_ticker, pd.DataFrame())
        return_tracker = ReturnTracker(benchmark_ohlcv)
        self._evaluator.cooldown_factor = config.cooldown_factor

        # Classify regimes
        detector = RegimeDetector()
        regimes = detector.classify(benchmark_ohlcv)

        if not regimes:
            logger.warning("BACKTEST-REGIME: Could not classify regimes")
            return []

        # Collect all events
        all_events: list[SignalEvent] = []
        for ticker in config.universe:
            ticker_ohlcv = ohlcv_data.get(ticker)
            if ticker_ohlcv is None or ticker_ohlcv.empty:
                continue
            events = self._evaluator.evaluate(
                ticker=ticker, ohlcv=ticker_ohlcv,
                signals=signals, forward_windows=config.forward_windows,
            )
            events = return_tracker.enrich(events, config.forward_windows)
            all_events.extend(events)

        # Segment events by regime
        segmented = detector.segment_events(all_events, regimes)

        # Compute per-signal, per-regime metrics
        import numpy as np
        signal_map = {s.id: s for s in signals}
        reports: list[RegimePerformanceReport] = []

        for sig_def in signals:
            regime_results: dict[str, SignalPerformanceRecord] = {}
            sharpe_values: list[float] = []

            for regime in MarketRegime:
                regime_events = [
                    e for e in segmented.get(regime, [])
                    if e.signal_id == sig_def.id
                ]
                if len(regime_events) < 5:
                    continue

                # Compute metrics for this signal in this regime
                windows = config.forward_windows
                hit_rate = compute_hit_rate(regime_events, windows)
                avg_ret = compute_avg_return(regime_events, windows)
                avg_excess = compute_avg_excess_return(regime_events, windows)
                sharpe = compute_sharpe(regime_events, windows)
                sortino = compute_sortino(regime_events, windows)
                max_dd = compute_max_drawdown(regime_events)
                t_stats, p_vals = compute_t_statistic(regime_events, windows)
                confidence = classify_confidence(p_vals, len(regime_events))

                record = SignalPerformanceRecord(
                    signal_id=sig_def.id,
                    signal_name=sig_def.name,
                    category=sig_def.category,
                    total_firings=len(regime_events),
                    hit_rate=hit_rate,
                    avg_return=avg_ret,
                    avg_excess_return=avg_excess,
                    sharpe_ratio=sharpe,
                    sortino_ratio=sortino,
                    max_drawdown=max_dd,
                    t_statistic=t_stats,
                    p_value=p_vals,
                    confidence_level=confidence,
                    sample_size=len(regime_events),
                    universe_size=len(config.universe),
                    date_range=f"{config.start_date} to {config.end_date}",
                )
                regime_results[regime.value] = record
                sharpe_20 = sharpe.get(20, 0.0)
                sharpe_values.append(sharpe_20)

            if not regime_results:
                continue

            # Best/worst regime by T+20 Sharpe
            best = max(regime_results.items(), key=lambda kv: kv[1].sharpe_ratio.get(20, 0.0))
            worst = min(regime_results.items(), key=lambda kv: kv[1].sharpe_ratio.get(20, 0.0))
            stability = float(np.std(sharpe_values)) if len(sharpe_values) > 1 else 0.0

            reports.append(RegimePerformanceReport(
                signal_id=sig_def.id,
                signal_name=sig_def.name,
                regime_results=regime_results,
                best_regime=best[0],
                worst_regime=worst[0],
                regime_stability=round(stability, 4),
            ))

        logger.info(
            "BACKTEST-REGIME: Produced %d regime reports across %d regimes",
            len(reports), len(MarketRegime),
        )
        return reports
