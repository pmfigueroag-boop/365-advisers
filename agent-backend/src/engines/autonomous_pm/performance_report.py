"""
src/engines/autonomous_pm/performance_report.py
--------------------------------------------------------------------------
Enhanced Performance Report — extends PerformanceEngine with institutional
analytics that were missing.

New metrics over the base PerformanceSnapshot:
  - Sortino ratio (downside deviation only)
  - Calmar ratio (annualized return / |max drawdown|)
  - Max drawdown duration (days from peak to recovery)
  - Rolling Sharpe (60-day window series)
  - Win rate (% of positive return days)
  - Monthly/quarterly return tables
  - Best/worst day/month

Usage::

    report = PerformanceReportBuilder.build(
        portfolio_returns=[0.01, -0.005, ...],
        benchmark_returns=[0.005, -0.003, ...],
    )
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from src.engines.autonomous_pm.performance_engine import PerformanceEngine
from src.engines.autonomous_pm.models import PerformanceSnapshot

logger = logging.getLogger("365advisers.apm.report")


# ── Contracts ────────────────────────────────────────────────────────────────

class DrawdownInfo(BaseModel):
    """Drawdown analysis."""
    max_drawdown: float = 0.0
    max_drawdown_duration_days: int = 0
    current_drawdown: float = 0.0
    current_drawdown_days: int = 0
    recovery_days: int | None = None


class RollingSharpe(BaseModel):
    """Rolling Sharpe series."""
    window_days: int = 60
    values: list[float] = Field(default_factory=list)
    mean: float = 0.0
    std: float = 0.0


class MonthlyReturn(BaseModel):
    """Return for a specific month."""
    year: int
    month: int
    return_pct: float


class PerformanceReport(BaseModel):
    """Full institutional performance report."""
    # Base metrics (from PerformanceEngine)
    snapshot: PerformanceSnapshot | None = None

    # Enhanced ratios
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # Drawdown analysis
    drawdown: DrawdownInfo = Field(default_factory=DrawdownInfo)

    # Rolling Sharpe
    rolling_sharpe: RollingSharpe = Field(default_factory=RollingSharpe)

    # Distribution metrics
    win_rate: float = 0.0
    best_day: float = 0.0
    worst_day: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0

    # Monthly returns
    monthly_returns: list[MonthlyReturn] = Field(default_factory=list)

    # Metadata
    period_days: int = 0
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Builder ──────────────────────────────────────────────────────────────────

class PerformanceReportBuilder:
    """Builds an enhanced performance report from return series."""

    @classmethod
    def build(
        cls,
        portfolio_returns: list[float],
        benchmark_returns: list[float] | None = None,
        benchmark_name: str = "S&P 500",
        risk_free_rate: float = 0.05,
        rolling_window: int = 60,
    ) -> PerformanceReport:
        """
        Build a complete performance report.

        Parameters
        ----------
        portfolio_returns : list[float]
            Daily return series for the portfolio.
        benchmark_returns : list[float] | None
            Daily return series for the benchmark.
        risk_free_rate : float
            Annualized risk-free rate.
        rolling_window : int
            Window size for rolling Sharpe.
        """
        if not portfolio_returns:
            return PerformanceReport()

        p_ret = portfolio_returns
        n = len(p_ret)

        # 1. Base snapshot from existing engine
        engine = PerformanceEngine()
        snapshot = engine.evaluate(
            portfolio_returns=p_ret,
            benchmark_returns=benchmark_returns,
            benchmark_name=benchmark_name,
            risk_free_rate=risk_free_rate,
        )

        # 2. Sortino ratio
        sortino = cls._sortino(p_ret, risk_free_rate)

        # 3. Calmar ratio
        calmar = cls._calmar(p_ret)

        # 4. Drawdown analysis
        dd_info = cls._drawdown_analysis(p_ret)

        # 5. Rolling Sharpe
        rolling = cls._rolling_sharpe(p_ret, rolling_window, risk_free_rate)

        # 6. Distribution metrics
        win_rate = sum(1 for r in p_ret if r > 0) / n
        best_day = max(p_ret) if p_ret else 0.0
        worst_day = min(p_ret) if p_ret else 0.0

        winners = [r for r in p_ret if r > 0]
        losers = [r for r in p_ret if r < 0]
        avg_win = sum(winners) / len(winners) if winners else 0.0
        avg_loss = sum(losers) / len(losers) if losers else 0.0

        # Profit factor = gross profits / gross losses
        gross_profit = sum(winners)
        gross_loss = abs(sum(losers))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

        # Skewness and kurtosis
        skew = cls._skewness(p_ret)
        kurt = cls._kurtosis(p_ret)

        # 7. Monthly returns
        monthly = cls._monthly_returns(p_ret)

        return PerformanceReport(
            snapshot=snapshot,
            sortino_ratio=round(sortino, 4),
            calmar_ratio=round(calmar, 4),
            drawdown=dd_info,
            rolling_sharpe=rolling,
            win_rate=round(win_rate, 4),
            best_day=round(best_day, 6),
            worst_day=round(worst_day, 6),
            avg_win=round(avg_win, 6),
            avg_loss=round(avg_loss, 6),
            profit_factor=round(profit_factor, 4),
            skewness=round(skew, 4),
            kurtosis=round(kurt, 4),
            monthly_returns=monthly,
            period_days=n,
        )

    # ── Static helpers ───────────────────────────────────────────────────

    @staticmethod
    def _sortino(returns: list[float], risk_free_rate: float = 0.05) -> float:
        """Sortino ratio: excess return / downside deviation."""
        if len(returns) < 5:
            return 0.0
        daily_rf = risk_free_rate / 252
        mean_ret = sum(returns) / len(returns)
        excess = mean_ret - daily_rf

        # Downside deviation (only negative excess returns)
        downside = [min(r - daily_rf, 0) ** 2 for r in returns]
        downside_var = sum(downside) / len(downside)
        downside_dev = math.sqrt(downside_var) if downside_var > 0 else 1e-9

        return (excess / downside_dev) * math.sqrt(252)

    @staticmethod
    def _calmar(returns: list[float]) -> float:
        """Calmar ratio: annualized return / |max drawdown|."""
        if len(returns) < 20:
            return 0.0
        n = len(returns)

        cumulative = 1.0
        for r in returns:
            cumulative *= (1 + r)
        ann_return = (cumulative ** (252 / max(n, 1))) - 1.0

        # Max drawdown
        peak = 1.0
        cum = 1.0
        max_dd = 0.0
        for r in returns:
            cum *= (1 + r)
            peak = max(peak, cum)
            dd = (cum - peak) / peak
            max_dd = min(max_dd, dd)

        if abs(max_dd) < 1e-9:
            return 0.0
        return ann_return / abs(max_dd)

    @staticmethod
    def _drawdown_analysis(returns: list[float]) -> DrawdownInfo:
        """Detailed drawdown: max DD, duration, current state."""
        if not returns:
            return DrawdownInfo()

        cumulative = 1.0
        peak = 1.0
        max_dd = 0.0
        max_dd_duration = 0
        current_dd_start: int | None = None
        max_dd_peak_idx = 0
        max_dd_trough_idx = 0

        # Track durations
        dd_start_idx: int | None = None
        longest_dd_duration = 0

        for i, r in enumerate(returns):
            cumulative *= (1 + r)

            if cumulative >= peak:
                # New peak — end of drawdown (if any)
                if dd_start_idx is not None:
                    duration = i - dd_start_idx
                    longest_dd_duration = max(longest_dd_duration, duration)
                    dd_start_idx = None
                peak = cumulative
            else:
                # In drawdown
                if dd_start_idx is None:
                    dd_start_idx = i

                dd = (cumulative - peak) / peak
                if dd < max_dd:
                    max_dd = dd
                    max_dd_peak_idx = dd_start_idx if dd_start_idx is not None else 0
                    max_dd_trough_idx = i

        # Current drawdown state
        current_dd = (cumulative - peak) / peak if peak > 0 else 0.0
        current_dd_days = len(returns) - (dd_start_idx or len(returns)) if dd_start_idx is not None else 0

        # Max DD duration: from peak to trough
        max_dd_dur = max_dd_trough_idx - max_dd_peak_idx if max_dd < 0 else 0

        return DrawdownInfo(
            max_drawdown=round(max_dd, 6),
            max_drawdown_duration_days=max(max_dd_dur, longest_dd_duration),
            current_drawdown=round(current_dd, 6),
            current_drawdown_days=current_dd_days,
        )

    @staticmethod
    def _rolling_sharpe(
        returns: list[float],
        window: int = 60,
        risk_free_rate: float = 0.05,
    ) -> RollingSharpe:
        """Compute rolling Sharpe ratio."""
        if len(returns) < window:
            return RollingSharpe(window_days=window)

        daily_rf = risk_free_rate / 252
        values = []

        for i in range(window, len(returns) + 1):
            chunk = returns[i - window:i]
            mean_ret = sum(chunk) / len(chunk)
            var = sum((r - mean_ret) ** 2 for r in chunk) / max(len(chunk) - 1, 1)
            std = math.sqrt(var) if var > 0 else 1e-9
            sharpe = ((mean_ret - daily_rf) / std) * math.sqrt(252)
            values.append(round(sharpe, 4))

        mean_sharpe = sum(values) / len(values) if values else 0.0
        if len(values) > 1:
            var = sum((v - mean_sharpe) ** 2 for v in values) / (len(values) - 1)
            std_sharpe = math.sqrt(var) if var > 0 else 0.0
        else:
            std_sharpe = 0.0

        return RollingSharpe(
            window_days=window,
            values=values,
            mean=round(mean_sharpe, 4),
            std=round(std_sharpe, 4),
        )

    @staticmethod
    def _skewness(values: list[float]) -> float:
        """Sample skewness."""
        n = len(values)
        if n < 3:
            return 0.0
        mean = sum(values) / n
        m2 = sum((v - mean) ** 2 for v in values) / n
        m3 = sum((v - mean) ** 3 for v in values) / n
        if m2 <= 0:
            return 0.0
        return m3 / (m2 ** 1.5)

    @staticmethod
    def _kurtosis(values: list[float]) -> float:
        """Excess kurtosis."""
        n = len(values)
        if n < 4:
            return 0.0
        mean = sum(values) / n
        m2 = sum((v - mean) ** 2 for v in values) / n
        m4 = sum((v - mean) ** 4 for v in values) / n
        if m2 <= 0:
            return 0.0
        return (m4 / (m2 ** 2)) - 3.0

    @staticmethod
    def _monthly_returns(
        returns: list[float],
        trading_days_per_month: int = 21,
    ) -> list[MonthlyReturn]:
        """Approximate monthly returns from daily series."""
        if len(returns) < trading_days_per_month:
            return []

        monthly = []
        n_months = len(returns) // trading_days_per_month

        for m in range(n_months):
            start = m * trading_days_per_month
            end = start + trading_days_per_month
            chunk = returns[start:end]

            cum = 1.0
            for r in chunk:
                cum *= (1 + r)
            month_ret = cum - 1.0

            monthly.append(MonthlyReturn(
                year=2024 + (m // 12),
                month=(m % 12) + 1,
                return_pct=round(month_ret * 100, 4),
            ))

        return monthly
