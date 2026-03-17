"""
src/engines/backtesting/cross_sectional.py
--------------------------------------------------------------------------
Cross-Sectional Ranking Engine -- quintile spread analysis.

At each rebalance date, scores all tickers using the alpha signal evaluator,
sorts into quintiles, and measures forward returns per quintile.

The Q1-Q5 spread measures the long-short alpha of the signal system.
"""

from __future__ import annotations

import logging
import math
import time
from datetime import date

import pandas as pd

from src.engines.alpha_signals.models import AlphaSignalDefinition, SignalCategory
from src.engines.alpha_signals.registry import registry as signal_registry
from src.engines.backtesting.cross_sectional_models import (
    CrossSectionalConfig,
    CrossSectionalReport,
    QuintileResult,
    RebalancePeriod,
)
from src.engines.backtesting.historical_evaluator import (
    _build_technical_snapshot,
    _resolve_feature_value,
    _check_fired,
    _compute_strength,
    _compute_confidence,
)

logger = logging.getLogger("365advisers.backtesting.cross_sectional")

# Numeric strength mapping
_STRENGTH_NUMERIC = {"STRONG": 1.0, "MODERATE": 0.6, "WEAK": 0.3}


class CrossSectionalRanker:
    """
    Evaluates all tickers in a universe at each rebalance date,
    sorts into quintiles, and measures forward returns per quintile.
    """

    def run(
        self,
        config: CrossSectionalConfig,
        ohlcv_data: dict[str, pd.DataFrame],
        fundamental_data: dict[str, dict[str, dict[str, float]]] | None = None,
    ) -> CrossSectionalReport:
        """
        Execute cross-sectional ranking analysis.

        Parameters
        ----------
        config : CrossSectionalConfig
            Analysis configuration.
        ohlcv_data : dict[str, pd.DataFrame]
            Ticker -> OHLCV DataFrame.
        fundamental_data : dict | None
            Ticker -> {date_str: {metric: value}} fundamental snapshots.

        Returns
        -------
        CrossSectionalReport
        """
        t0 = time.monotonic()
        signals = signal_registry.get_enabled()
        logger.info(
            f"CROSS-SECTIONAL: Starting analysis with "
            f"{len(config.universe)} tickers, {len(signals)} signals"
        )

        # Build a common date index from all tickers
        common_dates = self._build_common_dates(ohlcv_data, config)
        if not common_dates:
            logger.warning("CROSS-SECTIONAL: No common dates found")
            return CrossSectionalReport(
                config=config,
                execution_time_seconds=time.monotonic() - t0,
            )

        # Select rebalance dates
        rebalance_dates = common_dates[::config.rebalance_frequency_days]
        logger.info(f"CROSS-SECTIONAL: {len(rebalance_dates)} rebalance periods")

        # Benchmark data for excess returns
        benchmark_ohlcv = ohlcv_data.get(config.benchmark_ticker)
        bench_close = None
        if benchmark_ohlcv is not None and not benchmark_ohlcv.empty:
            bench_close = benchmark_ohlcv["Close"]
            if isinstance(bench_close, pd.DataFrame):
                bench_close = bench_close.iloc[:, 0]

        periods: list[RebalancePeriod] = []
        prev_q1_tickers: set[str] = set()

        for r_date in rebalance_dates:
            period = self._evaluate_period(
                r_date, config, signals, ohlcv_data,
                fundamental_data, bench_close,
            )
            if period.scored_tickers >= 10:
                periods.append(period)

                # Turnover tracking
                q1_tickers = set(periods[-1].quintiles[0].tickers) if periods[-1].quintiles else set()
                if prev_q1_tickers:
                    overlap = len(q1_tickers & prev_q1_tickers)
                    turnover = 1.0 - (overlap / max(len(q1_tickers), 1))
                    # Store for avg later
                prev_q1_tickers = q1_tickers

        # Compute aggregate metrics
        report = self._build_report(config, periods, t0)
        logger.info(
            f"CROSS-SECTIONAL: Completed in {report.execution_time_seconds:.1f}s -- "
            f"{report.total_periods} periods, "
            f"Q1-Q5 spread@20d: {report.avg_spread.get(20, 0):.4f}"
        )
        return report

    def _build_common_dates(
        self,
        ohlcv_data: dict[str, pd.DataFrame],
        config: CrossSectionalConfig,
    ) -> list:
        """Build a list of common trading dates across all tickers."""
        all_indices = []
        max_window = max(config.forward_windows)

        for ticker in config.universe:
            df = ohlcv_data.get(ticker)
            if df is not None and not df.empty:
                all_indices.append(set(df.index))

        if not all_indices:
            return []

        # Use intersection of at least 50% of tickers
        min_count = max(1, len(all_indices) // 2)
        from collections import Counter
        date_counts = Counter()
        for idx_set in all_indices:
            date_counts.update(idx_set)

        common = sorted(d for d, c in date_counts.items() if c >= min_count)

        # Trim: need warm-up (200 bars) and forward data
        if len(common) <= 200 + max_window:
            return []

        return common[200:-max_window]

    def _evaluate_period(
        self,
        rebalance_date,
        config: CrossSectionalConfig,
        signals: list[AlphaSignalDefinition],
        ohlcv_data: dict[str, pd.DataFrame],
        fundamental_data: dict[str, dict[str, dict[str, float]]] | None,
        bench_close: pd.Series | None,
    ) -> RebalancePeriod:
        """Score all tickers at a single rebalance date and sort into quintiles."""
        date_str = (
            rebalance_date.strftime("%Y-%m-%d")
            if hasattr(rebalance_date, "strftime")
            else str(rebalance_date)[:10]
        )

        # Score each ticker
        ticker_scores: list[tuple[str, float, dict[int, float]]] = []

        for ticker in config.universe:
            df = ohlcv_data.get(ticker)
            if df is None or df.empty:
                continue

            # Find the index position for this date
            try:
                idx = df.index.get_indexer([rebalance_date], method="ffill")[0]
            except Exception:
                continue

            if idx < 0 or idx < 200:
                continue

            # Build technical snapshot
            tech_snap = _build_technical_snapshot(df, idx)

            # Get fundamental snapshot
            fund_snap = None
            if fundamental_data and ticker in fundamental_data:
                fund_snap = fundamental_data[ticker].get(date_str)

            # Score: fire count weighted by strength
            score = 0.0
            total_weight = 0.0
            for signal in signals:
                value = _resolve_feature_value(signal.feature_path, tech_snap, fund_snap)
                if value is None:
                    continue
                total_weight += signal.weight
                if _check_fired(signal, value):
                    strength = _compute_strength(signal, value)
                    confidence = _compute_confidence(signal, value)
                    str_numeric = _STRENGTH_NUMERIC.get(strength.value, 0.3)
                    score += signal.weight * str_numeric * max(confidence, 0.1)

            if total_weight > 0:
                normalized_score = score / total_weight
            else:
                normalized_score = 0.0

            # Compute forward returns
            fwd_returns: dict[int, float] = {}
            close_col = df["Close"]
            if isinstance(close_col, pd.DataFrame):
                close_col = close_col.iloc[:, 0]
            close_vals = close_col.values

            if idx < len(close_vals):
                current_price = float(close_vals[idx])
                if current_price > 0:
                    for w in config.forward_windows:
                        future_idx = idx + w
                        if future_idx < len(close_vals):
                            fwd_returns[w] = (
                                float(close_vals[future_idx]) - current_price
                            ) / current_price

            if fwd_returns:
                ticker_scores.append((ticker, normalized_score, fwd_returns))

        if len(ticker_scores) < 10:
            return RebalancePeriod(
                rebalance_date=rebalance_date.date()
                if hasattr(rebalance_date, "date")
                else rebalance_date,
                scored_tickers=len(ticker_scores),
            )

        # Sort by score (descending)
        ticker_scores.sort(key=lambda x: x[1], reverse=True)

        # Split into quintiles
        n = len(ticker_scores)
        quintile_size = n // 5
        quintiles: list[QuintileResult] = []

        # Benchmark returns at this date
        bench_returns: dict[int, float] = {}
        if bench_close is not None:
            try:
                b_idx = bench_close.index.get_indexer([rebalance_date], method="ffill")[0]
                if b_idx >= 0:
                    bench_price = float(bench_close.iloc[b_idx])
                    if bench_price > 0:
                        for w in config.forward_windows:
                            future_idx = b_idx + w
                            if future_idx < len(bench_close):
                                bench_returns[w] = (
                                    float(bench_close.iloc[future_idx]) - bench_price
                                ) / bench_price
            except Exception:
                pass

        for q in range(5):
            start = q * quintile_size
            end = start + quintile_size if q < 4 else n
            slice_data = ticker_scores[start:end]

            avg_score = sum(s for _, s, _ in slice_data) / len(slice_data) if slice_data else 0.0
            avg_ret: dict[int, float] = {}
            avg_excess: dict[int, float] = {}

            for w in config.forward_windows:
                rets = [fwd[w] for _, _, fwd in slice_data if w in fwd]
                if rets:
                    ar = sum(rets) / len(rets)
                    avg_ret[w] = round(ar, 6)
                    br = bench_returns.get(w, 0.0)
                    avg_excess[w] = round(ar - br, 6)

            quintiles.append(QuintileResult(
                quintile=q + 1,
                n_tickers=len(slice_data),
                avg_score=round(avg_score, 4),
                avg_return=avg_ret,
                avg_excess_return=avg_excess,
                tickers=[t for t, _, _ in slice_data],
            ))

        # Q1-Q5 spread
        q1_q5_spread: dict[int, float] = {}
        if len(quintiles) >= 5:
            for w in config.forward_windows:
                q1_ret = quintiles[0].avg_return.get(w, 0.0)
                q5_ret = quintiles[4].avg_return.get(w, 0.0)
                q1_q5_spread[w] = round(q1_ret - q5_ret, 6)

        r_date_val = (
            rebalance_date.date()
            if hasattr(rebalance_date, "date")
            else rebalance_date
        )

        return RebalancePeriod(
            rebalance_date=r_date_val,
            scored_tickers=len(ticker_scores),
            quintiles=quintiles,
            q1_q5_spread=q1_q5_spread,
        )

    def _build_report(
        self,
        config: CrossSectionalConfig,
        periods: list[RebalancePeriod],
        t0: float,
    ) -> CrossSectionalReport:
        """Aggregate period results into a report."""
        if not periods:
            return CrossSectionalReport(
                config=config,
                execution_time_seconds=time.monotonic() - t0,
            )

        # Aggregate Q1 and Q5 returns
        avg_q1: dict[int, list[float]] = {}
        avg_q5: dict[int, list[float]] = {}
        spreads: dict[int, list[float]] = {}

        for p in periods:
            for w in config.forward_windows:
                spread = p.q1_q5_spread.get(w)
                if spread is not None:
                    spreads.setdefault(w, []).append(spread)

                if p.quintiles and len(p.quintiles) >= 5:
                    q1_ret = p.quintiles[0].avg_return.get(w)
                    q5_ret = p.quintiles[4].avg_return.get(w)
                    if q1_ret is not None:
                        avg_q1.setdefault(w, []).append(q1_ret)
                    if q5_ret is not None:
                        avg_q5.setdefault(w, []).append(q5_ret)

        # Average returns
        avg_q1_ret = {w: round(sum(v) / len(v), 6) for w, v in avg_q1.items() if v}
        avg_q5_ret = {w: round(sum(v) / len(v), 6) for w, v in avg_q5.items() if v}
        avg_spread = {w: round(sum(v) / len(v), 6) for w, v in spreads.items() if v}

        # T-test on spread
        t_stats: dict[int, float] = {}
        p_vals: dict[int, float] = {}
        for w, vals in spreads.items():
            n = len(vals)
            if n < 3:
                t_stats[w] = 0.0
                p_vals[w] = 1.0
                continue
            mean = sum(vals) / n
            var = sum((v - mean) ** 2 for v in vals) / (n - 1)
            se = math.sqrt(var / n) if var > 0 else 0.0
            if se > 0:
                t = mean / se
                t_stats[w] = round(t, 4)
                # Approximate p-value
                p = 2 * (1 - self._normal_cdf(abs(t)))
                p_vals[w] = round(max(p, 1e-10), 6)
            else:
                t_stats[w] = 0.0
                p_vals[w] = 1.0

        # Monotonicity check (Spearman correlation: quintile rank vs avg return)
        monotonicity: dict[int, float] = {}
        for w in config.forward_windows:
            quintile_returns = []
            for p in periods:
                if p.quintiles and len(p.quintiles) >= 5:
                    rets = [q.avg_return.get(w, 0.0) for q in p.quintiles]
                    quintile_returns.append(rets)

            if quintile_returns:
                # Average returns per quintile across all periods
                avg_per_q = []
                for q_idx in range(5):
                    vals = [pr[q_idx] for pr in quintile_returns if len(pr) > q_idx]
                    avg_per_q.append(sum(vals) / len(vals) if vals else 0.0)

                # Spearman: rank correlation between [1,2,3,4,5] and returns
                # Monotonic means Q1 > Q2 > ... > Q5 (negative correlation with rank)
                from scipy.stats import spearmanr  # type: ignore
                try:
                    corr, _ = spearmanr([1, 2, 3, 4, 5], avg_per_q)
                    monotonicity[w] = round(float(-corr), 4)  # Negate: +1 = Q1 best
                except Exception:
                    # Manual fallback if scipy not available
                    monotonicity[w] = self._spearman_manual(avg_per_q)

        # Turnover
        turnovers: list[float] = []
        prev_q1: set[str] = set()
        for p in periods:
            if p.quintiles:
                q1 = set(p.quintiles[0].tickers)
                if prev_q1:
                    overlap = len(q1 & prev_q1)
                    turnovers.append(1.0 - overlap / max(len(q1), 1))
                prev_q1 = q1

        avg_turnover = sum(turnovers) / len(turnovers) if turnovers else 0.0

        return CrossSectionalReport(
            config=config,
            total_periods=len(periods),
            periods=periods,
            avg_q1_return=avg_q1_ret,
            avg_q5_return=avg_q5_ret,
            avg_spread=avg_spread,
            spread_t_stat=t_stats,
            spread_p_value=p_vals,
            is_monotonic=monotonicity,
            avg_turnover=round(avg_turnover, 4),
            execution_time_seconds=round(time.monotonic() - t0, 2),
        )

    @staticmethod
    def _spearman_manual(avg_returns: list[float]) -> float:
        """Simple Spearman rank correlation without scipy."""
        n = len(avg_returns)
        if n < 3:
            return 0.0

        # Rank the returns (higher return = rank 1)
        sorted_indices = sorted(range(n), key=lambda i: avg_returns[i], reverse=True)
        ranks = [0.0] * n
        for rank_val, orig_idx in enumerate(sorted_indices, 1):
            ranks[orig_idx] = float(rank_val)

        # Expected ranks for perfect monotonicity: [1, 2, 3, 4, 5]
        expected = list(range(1, n + 1))

        # Spearman: 1 - 6*sum(d^2) / (n*(n^2-1))
        d_sq_sum = sum((ranks[i] - expected[i]) ** 2 for i in range(n))
        rho = 1 - (6 * d_sq_sum) / (n * (n ** 2 - 1))
        return round(rho, 4)

    @staticmethod
    def _normal_cdf(x: float) -> float:
        """Approximate standard normal CDF (Abramowitz & Stegun)."""
        if x < -8.0:
            return 0.0
        if x > 8.0:
            return 1.0

        a1 = 0.254829592
        a2 = -0.284496736
        a3 = 1.421413741
        a4 = -1.453152027
        a5 = 1.061405429
        p = 0.3275911

        sign = 1
        if x < 0:
            sign = -1
        x = abs(x) / math.sqrt(2)

        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)

        return 0.5 * (1.0 + sign * y)
