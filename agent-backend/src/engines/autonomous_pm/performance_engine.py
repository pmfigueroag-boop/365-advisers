"""
src/engines/autonomous_pm/performance_engine.py
──────────────────────────────────────────────────────────────────────────────
Performance Analysis Engine — evaluates portfolio performance against
benchmarks and computes standard institutional metrics.

Calculates: total return, annualized return, volatility, Sharpe ratio,
            max drawdown, alpha, beta, information ratio, tracking error.
"""

from __future__ import annotations

import logging
import math

from src.engines.autonomous_pm.models import PerformanceSnapshot

logger = logging.getLogger("365advisers.apm.performance")


class PerformanceEngine:
    """
    Evaluates portfolio performance and generates metric snapshots.

    Usage::

        engine = PerformanceEngine()
        snapshot = engine.evaluate(
            portfolio_returns=[0.01, -0.005, 0.008, ...],
            benchmark_returns=[0.005, -0.003, 0.006, ...],
            benchmark_name="S&P 500",
            risk_free_rate=0.05,
        )
    """

    def evaluate(
        self,
        portfolio_returns: list[float] | None = None,
        benchmark_returns: list[float] | None = None,
        benchmark_name: str = "S&P 500",
        risk_free_rate: float = 0.05,
        period_label: str = "",
    ) -> PerformanceSnapshot:
        """
        Compute performance metrics for a portfolio.

        Parameters
        ----------
        portfolio_returns : list[float] | None
            Daily return series for the portfolio.
        benchmark_returns : list[float] | None
            Daily return series for the benchmark.
        risk_free_rate : float
            Annualized risk-free rate for Sharpe/IR calculations.
        """
        p_ret = portfolio_returns or []
        b_ret = benchmark_returns or []

        if not p_ret:
            return PerformanceSnapshot(
                benchmark_name=benchmark_name,
                period_days=0,
            )

        n = len(p_ret)
        daily_rf = risk_free_rate / 252

        # ── Total return ─────────────────────────────────────────────────
        cumulative = 1.0
        for r in p_ret:
            cumulative *= (1 + r)
        total_return = cumulative - 1.0

        # ── Annualized return ────────────────────────────────────────────
        ann_return = 0.0
        if n > 0:
            ann_return = (cumulative ** (252 / max(n, 1))) - 1.0

        # ── Volatility ───────────────────────────────────────────────────
        mean_ret = sum(p_ret) / n
        variance = sum((r - mean_ret) ** 2 for r in p_ret) / max(n - 1, 1)
        daily_vol = math.sqrt(variance)
        ann_vol = daily_vol * math.sqrt(252)

        # ── Sharpe ratio ─────────────────────────────────────────────────
        excess_daily = mean_ret - daily_rf
        sharpe = (excess_daily / daily_vol * math.sqrt(252)) if daily_vol > 0 else 0.0

        # ── Max drawdown ─────────────────────────────────────────────────
        max_dd = self._max_drawdown(p_ret)

        # ── Benchmark metrics ────────────────────────────────────────────
        bench_total = 0.0
        alpha = 0.0
        beta = 0.0
        ir = 0.0
        te = 0.0

        if b_ret:
            # Align lengths
            min_len = min(n, len(b_ret))
            p_aligned = p_ret[:min_len]
            b_aligned = b_ret[:min_len]

            bench_cum = 1.0
            for r in b_aligned:
                bench_cum *= (1 + r)
            bench_total = bench_cum - 1.0

            # Alpha (simple)
            alpha = total_return - bench_total

            # Beta
            mean_b = sum(b_aligned) / len(b_aligned)
            cov_pb = sum((p_aligned[i] - mean_ret) * (b_aligned[i] - mean_b) for i in range(min_len)) / max(min_len - 1, 1)
            var_b = sum((r - mean_b) ** 2 for r in b_aligned) / max(min_len - 1, 1)
            beta = cov_pb / var_b if var_b > 0 else 0.0

            # Tracking error & Information ratio
            excess = [p_aligned[i] - b_aligned[i] for i in range(min_len)]
            mean_excess = sum(excess) / len(excess)
            te_var = sum((e - mean_excess) ** 2 for e in excess) / max(len(excess) - 1, 1)
            te = math.sqrt(te_var) * math.sqrt(252)
            ir = ((mean_excess * 252) / te) if te > 0 else 0.0

        return PerformanceSnapshot(
            total_return=round(total_return, 6),
            annualized_return=round(ann_return, 6),
            volatility=round(ann_vol, 6),
            sharpe_ratio=round(sharpe, 4),
            max_drawdown=round(max_dd, 6),
            alpha_vs_benchmark=round(alpha, 6),
            beta=round(beta, 4),
            information_ratio=round(ir, 4),
            tracking_error=round(te, 6),
            benchmark_name=benchmark_name,
            benchmark_return=round(bench_total, 6),
            period_days=n,
        )

    @staticmethod
    def _max_drawdown(returns: list[float]) -> float:
        if not returns:
            return 0.0
        cumulative = 1.0
        peak = 1.0
        max_dd = 0.0
        for r in returns:
            cumulative *= (1 + r)
            peak = max(peak, cumulative)
            dd = (cumulative - peak) / peak
            max_dd = min(max_dd, dd)
        return max_dd
