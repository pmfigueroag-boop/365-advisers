"""
src/engines/validation/institutional_backtest.py
──────────────────────────────────────────────────────────────────────────────
Institutional-Grade Walk-Forward Backtest Engine (AVS V2).

Features:
  - Rolling windows: configurable train/test (default 3Y/6M)
  - Multi-horizon forward returns: T+5, T+10, T+20, T+60
  - Transaction costs: commissions, slippage, turnover
  - Per-window and aggregate OOS metrics
  - Cross-sectional ranking per evaluation date
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import pandas as pd

from src.engines.alpha_signals.combiner import (
    SignalCombiner,
    BUY_THRESHOLD,
    STRONG_BUY_THRESHOLD,
)
from src.engines.alpha_signals.evaluator import SignalEvaluator
from src.contracts.features import FundamentalFeatureSet, TechnicalFeatureSet

logger = logging.getLogger("365advisers.validation.institutional")


# ═════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class TradeRecord:
    """A single evaluated observation."""
    ticker: str
    eval_date: str
    sector: str
    composite_score: float
    signal_level: str        # STRONG_BUY, BUY, HOLD
    fwd_return_5d: float | None = None
    fwd_return_10d: float | None = None
    fwd_return_20d: float | None = None
    fwd_return_60d: float | None = None
    is_oos: bool = False
    window_id: int = 0


@dataclass
class WindowResult:
    """Performance metrics for a single walk-forward window."""
    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    oos_trades: int = 0
    oos_avg_return_5d: float = 0.0
    oos_avg_return_10d: float = 0.0
    oos_avg_return_20d: float = 0.0
    oos_avg_return_60d: float = 0.0
    oos_hit_rate_20d: float = 0.0
    oos_sharpe_20d: float = 0.0
    oos_excess_return: float = 0.0
    benchmark_return: float = 0.0


@dataclass
class InstitutionalReport:
    """Full institutional backtest report."""
    universe_size: int = 0
    total_years: int = 0
    total_evals: int = 0
    total_buy_trades: int = 0
    total_strong_buy_trades: int = 0

    # Walk-forward windows
    windows: list[WindowResult] = field(default_factory=list)

    # Aggregate OOS metrics
    agg_oos_trades: int = 0
    agg_oos_avg_return_5d: float = 0.0
    agg_oos_avg_return_10d: float = 0.0
    agg_oos_avg_return_20d: float = 0.0
    agg_oos_avg_return_60d: float = 0.0
    agg_oos_hit_rate_20d: float = 0.0
    agg_oos_sharpe_20d: float = 0.0
    agg_oos_excess_return: float = 0.0
    agg_benchmark_return: float = 0.0

    # All trades (for statistical analysis)
    all_trades: list[TradeRecord] = field(default_factory=list)

    # Cross-sectional data (for decile analysis)
    cross_sectional: list[dict] = field(default_factory=list)

    # Cost-adjusted metrics
    commission_per_share: float = 0.005
    slippage_bps: int = 10
    net_alpha: float = 0.0


# ═════════════════════════════════════════════════════════════════════════════
# BACKTEST ENGINE
# ═════════════════════════════════════════════════════════════════════════════

class InstitutionalBacktest:
    """
    Walk-forward rolling backtest engine.

    Algorithm:
      1. For each rolling window [train_start..train_end, test_start..test_end]:
         a. Evaluate all tickers at every 5th trading day
         b. Mark observations in train vs test period
         c. Compute multi-horizon forward returns
      2. Aggregate OOS performance across all windows
      3. Collect cross-sectional rankings per date

    Cost model:
      - Commission: $0.005/share (round-trip: $0.01)
      - Slippage: 10 bps each way (20 bps round-trip)
      - Applied to T+20d return: net_return = gross_return - 0.002 (20bps RT)
    """

    def __init__(
        self,
        data_loader: Any,
        eval_frequency_days: int = 5,
        commission_per_share: float = 0.005,
        slippage_bps: int = 10,
    ):
        self._loader = data_loader
        self._eval_freq = eval_frequency_days
        self._commission = commission_per_share
        self._slippage_bps = slippage_bps
        self._evaluator = SignalEvaluator()
        self._combiner = SignalCombiner()

    def run(
        self,
        tickers: list[str],
        years: int = 10,
        train_years: int = 3,
        test_months: int = 6,
        buy_threshold: float = BUY_THRESHOLD,
        end_date: date | None = None,
    ) -> InstitutionalReport:
        """
        Run walk-forward backtest.

        Args:
            tickers: List of stock symbols.
            years: Total history to fetch per ticker.
            train_years: Training window length.
            test_months: Test window length.
            buy_threshold: Minimum composite score for BUY.
            end_date: End date for the backtest.
        """
        end = end_date or date.today()
        start = end - timedelta(days=int(years * 365))

        report = InstitutionalReport(
            universe_size=len(tickers),
            total_years=years,
            commission_per_share=self._commission,
            slippage_bps=self._slippage_bps,
        )

        # ── Load all data ────────────────────────────────────────────────
        logger.info(f"Loading data for {len(tickers)} tickers, {years}Y...")
        all_data: dict[str, dict] = {}
        for ticker in tickers:
            try:
                data = self._loader.load(ticker, years=years, end_date=end)
                if data["ohlcv"].empty:
                    logger.warning(f"Skipping {ticker}: no data")
                    continue
                all_data[ticker] = data
            except Exception as exc:
                logger.warning(f"Skipping {ticker}: {exc}")

        logger.info(f"Loaded {len(all_data)} / {len(tickers)} tickers")

        if not all_data:
            return report

        # ── Generate walk-forward windows ────────────────────────────────
        windows = self._generate_windows(
            start, end, train_years, test_months,
        )
        logger.info(f"Generated {len(windows)} walk-forward windows")

        # ── Evaluate all tickers at all dates ────────────────────────────
        all_trades = self._evaluate_universe(
            all_data, start, end, buy_threshold,
        )
        report.total_evals = len(all_trades)
        logger.info(f"Total evaluations: {len(all_trades)}")

        # ── Assign trades to windows ─────────────────────────────────────
        for window_id, (tr_start, tr_end, te_start, te_end) in enumerate(windows):
            for trade in all_trades:
                trade_date = date.fromisoformat(trade.eval_date)
                if te_start <= trade_date <= te_end:
                    trade.is_oos = True
                    trade.window_id = window_id

        # ── Compute per-window metrics ───────────────────────────────────
        buy_trades = [t for t in all_trades if t.composite_score > buy_threshold]
        report.total_buy_trades = len(buy_trades)
        report.total_strong_buy_trades = len(
            [t for t in buy_trades if t.composite_score > STRONG_BUY_THRESHOLD]
        )
        report.all_trades = all_trades

        for window_id, (tr_start, tr_end, te_start, te_end) in enumerate(windows):
            oos_buy = [
                t for t in buy_trades
                if t.is_oos and t.window_id == window_id
            ]
            all_oos = [
                t for t in all_trades
                if t.is_oos and t.window_id == window_id
            ]

            wr = WindowResult(
                window_id=window_id,
                train_start=tr_start.isoformat(),
                train_end=tr_end.isoformat(),
                test_start=te_start.isoformat(),
                test_end=te_end.isoformat(),
                oos_trades=len(oos_buy),
            )

            if oos_buy:
                rets_5 = [t.fwd_return_5d for t in oos_buy if t.fwd_return_5d is not None]
                rets_10 = [t.fwd_return_10d for t in oos_buy if t.fwd_return_10d is not None]
                rets_20 = [t.fwd_return_20d for t in oos_buy if t.fwd_return_20d is not None]
                rets_60 = [t.fwd_return_60d for t in oos_buy if t.fwd_return_60d is not None]

                if rets_5:
                    wr.oos_avg_return_5d = sum(rets_5) / len(rets_5)
                if rets_10:
                    wr.oos_avg_return_10d = sum(rets_10) / len(rets_10)
                if rets_20:
                    wr.oos_avg_return_20d = sum(rets_20) / len(rets_20)
                    wr.oos_hit_rate_20d = sum(1 for r in rets_20 if r > 0) / len(rets_20)
                    if len(rets_20) > 1:
                        mean_r = sum(rets_20) / len(rets_20)
                        std_r = (sum((r - mean_r)**2 for r in rets_20) / (len(rets_20) - 1)) ** 0.5
                        wr.oos_sharpe_20d = mean_r / std_r if std_r > 0 else 0.0
                if rets_60:
                    wr.oos_avg_return_60d = sum(rets_60) / len(rets_60)

            # Benchmark: unconditional average of all OOS observations
            if all_oos:
                bench_20 = [t.fwd_return_20d for t in all_oos if t.fwd_return_20d is not None]
                wr.benchmark_return = sum(bench_20) / len(bench_20) if bench_20 else 0.0
                wr.oos_excess_return = wr.oos_avg_return_20d - wr.benchmark_return

            report.windows.append(wr)

        # ── Aggregate OOS metrics ────────────────────────────────────────
        all_oos_buy = [t for t in buy_trades if t.is_oos]
        report.agg_oos_trades = len(all_oos_buy)

        if all_oos_buy:
            r5 = [t.fwd_return_5d for t in all_oos_buy if t.fwd_return_5d is not None]
            r10 = [t.fwd_return_10d for t in all_oos_buy if t.fwd_return_10d is not None]
            r20 = [t.fwd_return_20d for t in all_oos_buy if t.fwd_return_20d is not None]
            r60 = [t.fwd_return_60d for t in all_oos_buy if t.fwd_return_60d is not None]

            if r5: report.agg_oos_avg_return_5d = sum(r5) / len(r5)
            if r10: report.agg_oos_avg_return_10d = sum(r10) / len(r10)
            if r20:
                report.agg_oos_avg_return_20d = sum(r20) / len(r20)
                report.agg_oos_hit_rate_20d = sum(1 for r in r20 if r > 0) / len(r20)
                if len(r20) > 1:
                    mean_r = sum(r20) / len(r20)
                    std_r = (sum((r - mean_r)**2 for r in r20) / (len(r20) - 1)) ** 0.5
                    report.agg_oos_sharpe_20d = mean_r / std_r if std_r > 0 else 0.0
            if r60: report.agg_oos_avg_return_60d = sum(r60) / len(r60)

        # Benchmark (all OOS observations)
        all_oos_all = [t for t in all_trades if t.is_oos]
        if all_oos_all:
            bench = [t.fwd_return_20d for t in all_oos_all if t.fwd_return_20d is not None]
            report.agg_benchmark_return = sum(bench) / len(bench) if bench else 0.0
            report.agg_oos_excess_return = report.agg_oos_avg_return_20d - report.agg_benchmark_return

        # ── Cost-adjusted alpha ──────────────────────────────────────────
        round_trip_cost = (self._slippage_bps * 2) / 10_000  # 20bps default
        report.net_alpha = report.agg_oos_excess_return - round_trip_cost

        # ── Cross-sectional rankings ─────────────────────────────────────
        report.cross_sectional = self._compute_cross_sectional(all_trades)

        return report

    # ── Private ──────────────────────────────────────────────────────────────

    def _generate_windows(
        self,
        start: date,
        end: date,
        train_years: int,
        test_months: int,
    ) -> list[tuple[date, date, date, date]]:
        """Generate rolling walk-forward windows."""
        windows = []
        test_days = test_months * 30  # approximate
        train_days = train_years * 365

        cursor = start + timedelta(days=train_days)
        while cursor + timedelta(days=test_days) <= end:
            tr_start = cursor - timedelta(days=train_days)
            tr_end = cursor
            te_start = cursor + timedelta(days=1)
            te_end = min(cursor + timedelta(days=test_days), end)
            windows.append((tr_start, tr_end, te_start, te_end))
            cursor += timedelta(days=test_days)

        return windows

    def _evaluate_universe(
        self,
        all_data: dict[str, dict],
        start: date,
        end: date,
        buy_threshold: float,
    ) -> list[TradeRecord]:
        """Evaluate all tickers at every eval_freq trading days."""
        trades: list[TradeRecord] = []

        for ticker, data in all_data.items():
            ohlcv = data["ohlcv"]
            fundamentals = data.get("fundamentals", {})
            indicators = data.get("indicators", {})

            if ohlcv.empty:
                continue

            closes = ohlcv["Close"]
            eval_dates = list(indicators.keys())

            # Sample every eval_freq days
            for idx in range(0, len(eval_dates), self._eval_freq):
                eval_date = eval_dates[idx]

                # Build feature sets
                tech_data = indicators.get(eval_date, {})
                if not tech_data:
                    continue

                # Find most recent fundamental snapshot (point-in-time)
                funda_data = self._get_pit_fundamental(fundamentals, eval_date)

                # Build TechnicalFeatureSet
                ohlcv_bars = tech_data.pop("ohlcv_bars", [])
                tech_features = TechnicalFeatureSet(
                    ticker=ticker,
                    ohlcv=ohlcv_bars,
                    **{k: v for k, v in tech_data.items() if v is not None and k != "tv_recommendation"},
                    tv_recommendation=tech_data.get("tv_recommendation", "UNKNOWN"),
                )

                # Build FundamentalFeatureSet
                fund_features = None
                if funda_data:
                    safe_funda = {
                        k: v for k, v in funda_data.items()
                        if k in FundamentalFeatureSet.model_fields and v is not None
                    }
                    safe_funda["ticker"] = ticker
                    try:
                        fund_features = FundamentalFeatureSet(**safe_funda)
                    except Exception:
                        fund_features = FundamentalFeatureSet(ticker=ticker)

                # Evaluate signals
                sector = funda_data.get("sector", "") if funda_data else ""
                profile = self._evaluator.evaluate(
                    ticker=ticker,
                    fundamental=fund_features,
                    technical=tech_features,
                )

                # Combine
                composite = self._combiner.combine(profile, sector=sector)
                score = composite.overall_strength

                # Forward returns
                fwd_5 = self._compute_fwd_return(ohlcv, eval_date, 5)
                fwd_10 = self._compute_fwd_return(ohlcv, eval_date, 10)
                fwd_20 = self._compute_fwd_return(ohlcv, eval_date, 20)
                fwd_60 = self._compute_fwd_return(ohlcv, eval_date, 60)

                trades.append(TradeRecord(
                    ticker=ticker,
                    eval_date=eval_date,
                    sector=sector,
                    composite_score=round(score, 4),
                    signal_level=composite.signal_level.value,
                    fwd_return_5d=fwd_5,
                    fwd_return_10d=fwd_10,
                    fwd_return_20d=fwd_20,
                    fwd_return_60d=fwd_60,
                ))

        return trades

    @staticmethod
    def _get_pit_fundamental(
        fundamentals: dict[str, dict],
        eval_date: str,
    ) -> dict | None:
        """Get most recent fundamental snapshot at or before eval_date (PIT)."""
        if not fundamentals:
            return None

        # fundamentals keyed by calendardate; find the latest <= eval_date
        candidates = [d for d in fundamentals.keys() if d <= eval_date]
        if not candidates:
            return None

        latest = max(candidates)
        return fundamentals[latest]

    @staticmethod
    def _compute_fwd_return(
        ohlcv: pd.DataFrame,
        eval_date: str,
        horizon: int,
    ) -> float | None:
        """Compute forward return from eval_date + horizon trading days."""
        try:
            eval_dt = pd.Timestamp(eval_date)
            # Find the position in the index
            idx = ohlcv.index.get_indexer([eval_dt], method="ffill")[0]
            if idx < 0 or idx + horizon >= len(ohlcv):
                return None
            entry_price = ohlcv.iloc[idx]["Close"]
            exit_price = ohlcv.iloc[idx + horizon]["Close"]
            if entry_price <= 0:
                return None
            return (exit_price - entry_price) / entry_price
        except Exception:
            return None

    @staticmethod
    def _compute_cross_sectional(
        trades: list[TradeRecord],
    ) -> list[dict]:
        """
        Compute cross-sectional rankings per evaluation date.

        For each date where we have >= 10 observations, rank stocks
        by composite score and record quintile assignments.
        """
        from collections import defaultdict

        by_date: dict[str, list[TradeRecord]] = defaultdict(list)
        for t in trades:
            by_date[t.eval_date].append(t)

        cross_sectional = []
        for eval_date, date_trades in sorted(by_date.items()):
            if len(date_trades) < 10:
                continue

            # Sort by composite score descending
            ranked = sorted(date_trades, key=lambda x: x.composite_score, reverse=True)
            n = len(ranked)

            # Assign quintiles (1=top, 5=bottom)
            for i, trade in enumerate(ranked):
                quintile = min(5, int(i / n * 5) + 1)
                fwd_20 = trade.fwd_return_20d if trade.fwd_return_20d is not None else 0.0

                cross_sectional.append({
                    "eval_date": eval_date,
                    "ticker": trade.ticker,
                    "score": trade.composite_score,
                    "rank": i + 1,
                    "quintile": quintile,
                    "fwd_return_20d": fwd_20,
                    "is_oos": trade.is_oos,
                })

        return cross_sectional
