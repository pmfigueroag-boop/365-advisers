"""
src/engines/benchmark_factor/engine.py
──────────────────────────────────────────────────────────────────────────────
Benchmark & Factor Neutral Evaluation Engine — orchestrator.

Evaluates signal performance against multiple benchmarks and a 4-factor
risk model to isolate pure alpha from factor exposure.

Pipeline:
  1. Fetch benchmark + factor ETF OHLCV data
  2. For each signal: compute excess returns vs every benchmark
  3. Build factor return matrix (MKT, SMB, HML, UMD)
  4. Run OLS regression per signal to estimate factor alpha + betas
  5. Classify alpha source (PURE_ALPHA / MIXED / FACTOR_BETA)
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict

import numpy as np
import pandas as pd

from src.engines.backtesting.models import SignalEvent
from src.engines.benchmark_factor.factor_builder import FactorBuilder
from src.engines.benchmark_factor.models import (
    AlphaSource,
    BenchmarkConfig,
    BenchmarkFactorReport,
    BenchmarkResult,
    FactorExposure,
    SECTOR_MAP,
    SignalBenchmarkProfile,
)
from src.engines.benchmark_factor.regression import FactorRegressor

logger = logging.getLogger("365advisers.benchmark_factor.engine")

_TRADING_DAYS_YEAR = 252

# ─── Benchmark Names ────────────────────────────────────────────────────────

BENCHMARK_NAMES: dict[str, str] = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100",
    "IWM": "Russell 2000",
    "XLK": "Technology",
    "XLV": "Healthcare",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLY": "Consumer Disc.",
    "XLI": "Industrials",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLC": "Comm. Services",
    "XLP": "Consumer Staples",
}


class BenchmarkFactorEngine:
    """
    Evaluates signals against multiple benchmarks and risk factors.

    Usage::

        engine = BenchmarkFactorEngine()
        report = engine.evaluate(events, ohlcv_data, config)
    """

    def __init__(self, config: BenchmarkConfig | None = None) -> None:
        self.config = config or BenchmarkConfig()
        self._factor_builder = FactorBuilder()
        self._regressor = FactorRegressor()

    # ── Public API ────────────────────────────────────────────────────────

    def evaluate(
        self,
        events: list[SignalEvent],
        ohlcv_data: dict[str, pd.DataFrame],
        config: BenchmarkConfig | None = None,
    ) -> BenchmarkFactorReport:
        """
        Run benchmark & factor evaluation for all signals.

        Parameters
        ----------
        events : list[SignalEvent]
            Signal events with raw forward_returns.
        ohlcv_data : dict[str, pd.DataFrame]
            OHLCV for tickers, benchmarks, and factor ETFs.
        config : BenchmarkConfig | None
            Override for this run.

        Returns
        -------
        BenchmarkFactorReport
        """
        cfg = config or self.config
        windows = [5, 10, 20]

        # Build factor matrix if regression is enabled
        factor_df: pd.DataFrame | None = None
        if cfg.enable_factor_regression:
            factor_df = self._factor_builder.build(ohlcv_data, cfg.factor_tickers)

        # Group events by signal_id
        events_by_signal: dict[str, list[SignalEvent]] = defaultdict(list)
        for e in events:
            events_by_signal[e.signal_id].append(e)

        # Prepare benchmark tickers
        all_benchmarks = [cfg.market_benchmark] + cfg.additional_benchmarks

        # Evaluate each signal
        profiles: list[SignalBenchmarkProfile] = []
        for sig_id, sig_events in events_by_signal.items():
            profile = self._evaluate_signal(
                sig_id, sig_events, ohlcv_data,
                all_benchmarks, factor_df, cfg, windows,
            )
            profiles.append(profile)

        # Sort by factor alpha descending
        profiles.sort(
            key=lambda p: (
                p.factor_exposure.factor_alpha if p.factor_exposure else 0.0
            ),
            reverse=True,
        )

        pure_alpha = [
            p.signal_id for p in profiles
            if p.alpha_source == AlphaSource.PURE_ALPHA
        ]
        factor_dep = [
            p.signal_id for p in profiles
            if p.alpha_source == AlphaSource.FACTOR_BETA
        ]

        report = BenchmarkFactorReport(
            config=cfg,
            signal_profiles=profiles,
            pure_alpha_signals=pure_alpha,
            factor_dependent_signals=factor_dep,
        )

        logger.info(
            "BENCHMARK-FACTOR: %d signals — %d pure alpha, %d factor-dependent",
            len(profiles), len(pure_alpha), len(factor_dep),
        )
        return report

    # ── Signal-Level Evaluation ───────────────────────────────────────────

    def _evaluate_signal(
        self,
        signal_id: str,
        events: list[SignalEvent],
        ohlcv_data: dict[str, pd.DataFrame],
        benchmarks: list[str],
        factor_df: pd.DataFrame | None,
        cfg: BenchmarkConfig,
        windows: list[int],
    ) -> SignalBenchmarkProfile:
        """Evaluate one signal against all benchmarks and factors."""

        # Multi-benchmark excess returns
        benchmark_results: list[BenchmarkResult] = []
        for bench_ticker in benchmarks:
            bench_ohlcv = ohlcv_data.get(bench_ticker)
            if bench_ohlcv is None or bench_ohlcv.empty:
                continue
            result = self._compute_benchmark_excess(
                events, bench_ohlcv, bench_ticker, windows,
            )
            benchmark_results.append(result)

        # Sector-specific benchmark
        sector_result = self._compute_sector_excess(
            events, ohlcv_data, cfg.sector_benchmarks, windows,
        )

        # Factor regression
        factor_exposure: FactorExposure | None = None
        if factor_df is not None and not factor_df.empty and len(events) >= cfg.min_observations:
            factor_exposure = self._compute_factor_exposure(
                events, factor_df, cfg.forward_window,
            )

        # Classify alpha source
        alpha_source = self._classify_alpha(factor_exposure)

        return SignalBenchmarkProfile(
            signal_id=signal_id,
            signal_name="",
            total_events=len(events),
            benchmark_results=benchmark_results,
            sector_result=sector_result,
            factor_exposure=factor_exposure,
            alpha_source=alpha_source,
        )

    # ── Benchmark Excess ─────────────────────────────────────────────────

    def _compute_benchmark_excess(
        self,
        events: list[SignalEvent],
        bench_ohlcv: pd.DataFrame,
        bench_ticker: str,
        windows: list[int],
    ) -> BenchmarkResult:
        """Compute excess return, IR, TE, and hit rate vs a benchmark."""
        excess_ret: dict[int, float] = {}
        ir: dict[int, float] = {}
        te: dict[int, float] = {}
        hr: dict[int, float] = {}

        bench_returns = self._compute_daily_returns(bench_ohlcv)

        for w in windows:
            sig_rets = []
            bench_rets_list = []

            for e in events:
                sig_r = e.forward_returns.get(w)
                if sig_r is None:
                    continue

                bench_r = self._get_forward_return(bench_returns, e.fired_date, w)
                if bench_r is None:
                    continue

                sig_rets.append(sig_r)
                bench_rets_list.append(bench_r)

            if not sig_rets:
                excess_ret[w] = 0.0
                ir[w] = 0.0
                te[w] = 0.0
                hr[w] = 0.0
                continue

            excess = [s - b for s, b in zip(sig_rets, bench_rets_list)]
            mean_excess = sum(excess) / len(excess)
            excess_ret[w] = round(mean_excess, 6)

            # Information Ratio (annualised)
            if len(excess) >= 2:
                std_excess = math.sqrt(
                    sum((x - mean_excess) ** 2 for x in excess) / (len(excess) - 1)
                )
                annualisation = math.sqrt(_TRADING_DAYS_YEAR / max(w, 1))
                if std_excess > 0:
                    ir[w] = round((mean_excess / std_excess) * annualisation, 4)
                else:
                    ir[w] = 0.0
                te[w] = round(std_excess * annualisation, 6)
            else:
                ir[w] = 0.0
                te[w] = 0.0

            # Hit rate vs benchmark
            hits = sum(1 for x in excess if x > 0)
            hr[w] = round(hits / len(excess), 4)

        return BenchmarkResult(
            benchmark_ticker=bench_ticker,
            benchmark_name=BENCHMARK_NAMES.get(bench_ticker, bench_ticker),
            excess_return=excess_ret,
            information_ratio=ir,
            tracking_error=te,
            hit_rate_vs_bench=hr,
        )

    def _compute_sector_excess(
        self,
        events: list[SignalEvent],
        ohlcv_data: dict[str, pd.DataFrame],
        sector_map: dict[str, str],
        windows: list[int],
    ) -> BenchmarkResult | None:
        """Compute excess return vs the auto-detected sector benchmark."""
        # Find most common sector for these events
        sector_counts: dict[str, int] = defaultdict(int)
        for e in events:
            sector_etf = sector_map.get(e.ticker, "SPY")
            sector_counts[sector_etf] += 1

        if not sector_counts:
            return None

        primary_sector = max(sector_counts, key=sector_counts.get)
        sector_ohlcv = ohlcv_data.get(primary_sector)
        if sector_ohlcv is None or sector_ohlcv.empty:
            return None

        return self._compute_benchmark_excess(
            events, sector_ohlcv, primary_sector, windows,
        )

    # ── Factor Exposure ──────────────────────────────────────────────────

    def _compute_factor_exposure(
        self,
        events: list[SignalEvent],
        factor_df: pd.DataFrame,
        forward_window: int,
    ) -> FactorExposure:
        """Run OLS factor regression for a signal's events."""
        signal_returns: list[float] = []
        factor_rows: list[list[float]] = []

        for e in events:
            sig_r = e.forward_returns.get(forward_window)
            if sig_r is None:
                continue

            factors = self._factor_builder.get_factor_at_date(
                factor_df, e.fired_date, forward_window,
            )
            if factors is None:
                continue

            signal_returns.append(sig_r)
            factor_rows.append([
                factors.get("MKT", 0.0),
                factors.get("SMB", 0.0),
                factors.get("HML", 0.0),
                factors.get("UMD", 0.0),
            ])

        if len(signal_returns) < 3:
            return FactorExposure(
                n_observations=len(signal_returns),
                forward_window=forward_window,
            )

        y = np.array(signal_returns)
        X = np.array(factor_rows)

        return self._regressor.regress(y, X, forward_window)

    # ── Alpha Classification ─────────────────────────────────────────────

    @staticmethod
    def _classify_alpha(exposure: FactorExposure | None) -> AlphaSource:
        """Classify where a signal's return comes from."""
        if exposure is None:
            return AlphaSource.FACTOR_BETA

        if exposure.alpha_significant:
            if exposure.r_squared < 0.30:
                return AlphaSource.PURE_ALPHA
            return AlphaSource.MIXED
        return AlphaSource.FACTOR_BETA

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _compute_daily_returns(ohlcv: pd.DataFrame) -> pd.Series:
        """Compute daily returns from Close column."""
        if "Close" not in ohlcv.columns or ohlcv.empty:
            return pd.Series(dtype=float)
        return ohlcv["Close"].pct_change().dropna()

    @staticmethod
    def _get_forward_return(
        returns: pd.Series,
        fired_date: object,
        window: int,
    ) -> float | None:
        """Get cumulative forward return starting from fired_date."""
        ts = pd.Timestamp(fired_date)
        idx_arr = returns.index.get_indexer([ts], method="pad")
        if len(idx_arr) == 0 or idx_arr[0] < 0:
            return None

        start = int(idx_arr[0])
        end = min(start + window, len(returns))
        if end <= start:
            return None

        chunk = returns.iloc[start:end]
        return float((1 + chunk).prod() - 1)
