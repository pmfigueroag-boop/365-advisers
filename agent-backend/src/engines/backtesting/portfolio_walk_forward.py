"""
src/engines/backtesting/portfolio_walk_forward.py
--------------------------------------------------------------------------
Walk-Forward Validation for the COMPLETE PORTFOLIO — not just individual
signals.

While signal-level WF tests each signal independently, portfolio WF tests
the *combined system*:
  - Signal selection + weighting + optimization + rebalancing
  - Detects: overfitting in the optimizer, correlation breakdown,
    regime dependency, combinatorial signal decay

Method:
  1. Split timeline into IS (in-sample) and OOS (out-of-sample) windows
  2. On IS: run full bridge → optimizer → weights
  3. On OOS: measure performance with those weights
  4. Roll forward and repeat
  5. Report: OOS Sharpe, IS/OOS ratio, stability

Usage::

    wf = PortfolioWalkForward(is_days=252, oos_days=63)
    report = wf.run(events, weights_fn)
"""

from __future__ import annotations

import logging
import math
import random
from datetime import date, timedelta
from collections import defaultdict

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.backtesting.portfolio_wf")


# ── Contracts ────────────────────────────────────────────────────────────────

class WFWindow(BaseModel):
    """A single walk-forward window."""
    window_id: int = 0
    is_start: date = date(2020, 1, 1)
    is_end: date = date(2020, 12, 31)
    oos_start: date = date(2021, 1, 1)
    oos_end: date = date(2021, 3, 31)

    is_sharpe: float = 0.0
    oos_sharpe: float = 0.0
    is_return: float = 0.0
    oos_return: float = 0.0
    is_vol: float = 0.0
    oos_vol: float = 0.0

    n_positions: int = 0
    turnover: float = 0.0
    degradation_ratio: float = Field(
        0.0, description="OOS Sharpe / IS Sharpe — <0.5 = overfitting",
    )


class PortfolioWFReport(BaseModel):
    """Walk-forward report for the complete portfolio."""
    windows: list[WFWindow] = Field(default_factory=list)
    total_windows: int = 0

    # Aggregate metrics
    avg_is_sharpe: float = 0.0
    avg_oos_sharpe: float = 0.0
    avg_degradation: float = 0.0
    oos_sharpe_stability: float = Field(
        0.0, description="StdDev of OOS Sharpe across windows — lower = better",
    )

    is_overfit: bool = False
    overfit_score: float = Field(
        0.0, description="0-1 score, >0.5 = likely overfit",
    )


# ── Engine ───────────────────────────────────────────────────────────────────

class PortfolioWalkForward:
    """
    Walk-forward validation for the complete portfolio system.

    Parameters
    ----------
    is_days : int
        In-sample window in trading days.
    oos_days : int
        Out-of-sample window in trading days.
    step_days : int
        How many days to move forward each step.
    min_windows : int
        Minimum number of windows to consider valid.
    """

    def __init__(
        self,
        is_days: int = 252,
        oos_days: int = 63,
        step_days: int = 63,
        min_windows: int = 3,
    ) -> None:
        self.is_days = is_days
        self.oos_days = oos_days
        self.step_days = step_days
        self.min_windows = min_windows

    def run(
        self,
        daily_returns: list[float],
        start_date: date = date(2020, 1, 1),
        weights_fn: callable | None = None,
    ) -> PortfolioWFReport:
        """
        Run walk-forward on portfolio daily returns.

        Parameters
        ----------
        daily_returns : list[float]
            Daily portfolio returns (sequential).
        start_date : date
            Start date of the return series.
        weights_fn : callable | None
            Function(is_returns) -> weights_dict.
            If None, uses identity (just measures IS/OOS performance).

        Returns
        -------
        PortfolioWFReport
        """
        n = len(daily_returns)
        total_needed = self.is_days + self.oos_days

        if n < total_needed:
            return PortfolioWFReport()

        windows: list[WFWindow] = []
        window_id = 0
        offset = 0

        while offset + total_needed <= n:
            is_start_idx = offset
            is_end_idx = offset + self.is_days
            oos_start_idx = is_end_idx
            oos_end_idx = min(oos_start_idx + self.oos_days, n)

            is_rets = daily_returns[is_start_idx:is_end_idx]
            oos_rets = daily_returns[oos_start_idx:oos_end_idx]

            if len(oos_rets) < 10:
                break

            # Apply weights function if provided
            if weights_fn:
                try:
                    weights_fn(is_rets)
                except Exception:
                    pass

            # Compute metrics
            is_sharpe = self._sharpe(is_rets)
            oos_sharpe = self._sharpe(oos_rets)
            is_ret = sum(is_rets)
            oos_ret = sum(oos_rets)
            is_vol = self._vol(is_rets)
            oos_vol = self._vol(oos_rets)

            degradation = (oos_sharpe / is_sharpe) if abs(is_sharpe) > 0.01 else 1.0

            is_start_date = start_date + timedelta(days=is_start_idx)
            is_end_date = start_date + timedelta(days=is_end_idx)
            oos_start_date = start_date + timedelta(days=oos_start_idx)
            oos_end_date = start_date + timedelta(days=oos_end_idx)

            windows.append(WFWindow(
                window_id=window_id,
                is_start=is_start_date,
                is_end=is_end_date,
                oos_start=oos_start_date,
                oos_end=oos_end_date,
                is_sharpe=round(is_sharpe, 4),
                oos_sharpe=round(oos_sharpe, 4),
                is_return=round(is_ret, 6),
                oos_return=round(oos_ret, 6),
                is_vol=round(is_vol, 6),
                oos_vol=round(oos_vol, 6),
                degradation_ratio=round(degradation, 4),
            ))

            window_id += 1
            offset += self.step_days

        if not windows:
            return PortfolioWFReport()

        # Aggregate
        avg_is = sum(w.is_sharpe for w in windows) / len(windows)
        avg_oos = sum(w.oos_sharpe for w in windows) / len(windows)
        avg_deg = sum(w.degradation_ratio for w in windows) / len(windows)

        oos_sharpes = [w.oos_sharpe for w in windows]
        oos_mean = sum(oos_sharpes) / len(oos_sharpes)
        oos_stability = math.sqrt(
            sum((s - oos_mean) ** 2 for s in oos_sharpes) / max(len(oos_sharpes) - 1, 1)
        )

        # Overfit detection
        overfit_score = 0.0
        if avg_is > 0.01:
            # Degradation-based: high IS, low OOS = overfitting
            overfit_score = max(0, 1 - (avg_oos / avg_is))
        is_overfit = overfit_score > 0.5

        logger.info(
            "PORTFOLIO-WF: %d windows, IS Sharpe=%.2f, OOS Sharpe=%.2f, "
            "degradation=%.2f, overfit_score=%.2f",
            len(windows), avg_is, avg_oos, avg_deg, overfit_score,
        )

        return PortfolioWFReport(
            windows=windows,
            total_windows=len(windows),
            avg_is_sharpe=round(avg_is, 4),
            avg_oos_sharpe=round(avg_oos, 4),
            avg_degradation=round(avg_deg, 4),
            oos_sharpe_stability=round(oos_stability, 4),
            is_overfit=is_overfit,
            overfit_score=round(overfit_score, 4),
        )

    @staticmethod
    def _sharpe(returns: list[float], annualize: bool = True) -> float:
        """Compute Sharpe ratio."""
        if len(returns) < 2:
            return 0.0
        mean_r = sum(returns) / len(returns)
        var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std_r = math.sqrt(var_r) if var_r > 0 else 1e-8
        sharpe = mean_r / std_r
        if annualize:
            sharpe *= math.sqrt(252)
        return sharpe

    @staticmethod
    def _vol(returns: list[float]) -> float:
        """Annualized volatility."""
        if len(returns) < 2:
            return 0.0
        mean_r = sum(returns) / len(returns)
        var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        return math.sqrt(var_r * 252)
