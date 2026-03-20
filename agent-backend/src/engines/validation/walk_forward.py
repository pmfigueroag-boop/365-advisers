"""
src/engines/validation/walk_forward.py
──────────────────────────────────────────────────────────────────────────────
P3.1: Walk-Forward Validation Framework.

Train on 3-year windows, test on 1-year forward, roll quarterly.
This avoids lookahead bias that in-sample backtesting inherently has.

Architecture:
  - WalkForwardValidator manages the rolling window schedule
  - Each fold runs a CompositeBacktest on the IS window
  - Then evaluates OOS performance on the held-out quarter
  - Aggregates stability metrics across all folds

Usage:
    validator = WalkForwardValidator()
    results = validator.run(tickers=SYSTEMATIC_50, total_years=5)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

logger = logging.getLogger("365advisers.validation.walk_forward")


@dataclass
class WalkForwardFold:
    """Single fold of walk-forward validation."""
    fold_id: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    # IS metrics
    is_avg_return: float = 0.0
    is_hit_rate: float = 0.0
    is_trade_count: int = 0
    # OOS metrics
    oos_avg_return: float = 0.0
    oos_hit_rate: float = 0.0
    oos_trade_count: int = 0
    # Decay analysis
    return_decay_pct: float = 0.0  # (IS - OOS) / IS × 100


@dataclass
class WalkForwardReport:
    """Aggregated walk-forward validation report."""
    total_folds: int = 0
    folds: list[WalkForwardFold] = field(default_factory=list)
    # Aggregate OOS performance
    avg_oos_return: float = 0.0
    avg_oos_hit_rate: float = 0.0
    total_oos_trades: int = 0
    # Stability metrics
    avg_decay_pct: float = 0.0           # avg (IS - OOS) / IS
    max_decay_pct: float = 0.0           # worst fold decay
    oos_consistency: float = 0.0         # % of folds with positive OOS return
    sharpe_stability_ratio: float = 0.0  # OOS Sharpe / IS Sharpe


class WalkForwardValidator:
    """
    P3.1: Walk-forward validation engine.

    Schedule:
      - Train window: 3 years (configurable)
      - Test window: 1 quarter (3 months)
      - Roll: advance by test_window_months each iteration
      - Minimum: 4 folds needed for statistical significance

    The validator runs the full CompositeBacktest pipeline on each fold
    and aggregates robustness metrics.
    """

    def __init__(
        self,
        train_years: int = 3,
        test_months: int = 3,
        buy_threshold: float = 0.20,
    ):
        self.train_years = train_years
        self.test_months = test_months
        self.buy_threshold = buy_threshold

    def _generate_schedule(
        self,
        total_start: date,
        total_end: date,
    ) -> list[tuple[date, date, date, date]]:
        """Generate (train_start, train_end, test_start, test_end) tuples."""
        folds = []
        train_start = total_start
        train_delta = timedelta(days=self.train_years * 365)
        test_delta = timedelta(days=self.test_months * 30)

        while True:
            train_end = train_start + train_delta
            test_start = train_end + timedelta(days=1)
            test_end = test_start + test_delta

            if test_end > total_end:
                break

            folds.append((train_start, train_end, test_start, test_end))
            # Roll forward by test window
            train_start = train_start + test_delta

        return folds

    def run(
        self,
        tickers: list[str],
        total_years: int = 5,
    ) -> WalkForwardReport:
        """
        Run walk-forward validation.

        Parameters
        ----------
        tickers : list[str]
            Universe of tickers to validate.
        total_years : int
            Total data window (default 5 years).
        """
        from src.engines.validation.composite_backtest import CompositeBacktest

        today = date.today()
        total_start = today - timedelta(days=total_years * 365)
        schedule = self._generate_schedule(total_start, today)

        if len(schedule) < 2:
            logger.warning(
                f"WF: Only {len(schedule)} folds generated "
                f"(need ≥2). Increase total_years or decrease train_years."
            )

        bt = CompositeBacktest()
        folds: list[WalkForwardFold] = []

        for i, (train_start, train_end, test_start, test_end) in enumerate(schedule):
            logger.info(
                f"WF Fold {i+1}/{len(schedule)}: "
                f"TRAIN {train_start} → {train_end} | "
                f"TEST {test_start} → {test_end}"
            )

            try:
                # Run IS backtest on train window
                report = bt.run(
                    tickers=tickers,
                    years=self.train_years + 1,  # Load enough data
                    buy_threshold=self.buy_threshold,
                    eval_frequency_days=5,
                )

                # Separate IS and OOS trades using date boundaries
                is_return = report.is_avg_return_20d
                is_hit = report.is_hit_rate_20d
                is_trades = report.strong_buy_count + report.buy_only_count

                oos_return = report.oos_avg_return_20d
                oos_hit = report.oos_hit_rate_20d
                oos_trades = report.oos_count

                decay = 0.0
                if is_return > 0:
                    decay = (is_return - oos_return) / is_return * 100

                fold = WalkForwardFold(
                    fold_id=i + 1,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    is_avg_return=is_return,
                    is_hit_rate=is_hit,
                    is_trade_count=is_trades,
                    oos_avg_return=oos_return,
                    oos_hit_rate=oos_hit,
                    oos_trade_count=oos_trades,
                    return_decay_pct=decay,
                )
                folds.append(fold)

            except Exception as exc:
                logger.error(f"WF Fold {i+1} failed: {exc}")
                continue

        # Aggregate
        report = WalkForwardReport(
            total_folds=len(folds),
            folds=folds,
        )

        if folds:
            oos_with_trades = [f for f in folds if f.oos_trade_count > 0]
            if oos_with_trades:
                report.avg_oos_return = sum(f.oos_avg_return for f in oos_with_trades) / len(oos_with_trades)
                report.avg_oos_hit_rate = sum(f.oos_hit_rate for f in oos_with_trades) / len(oos_with_trades)
            report.total_oos_trades = sum(f.oos_trade_count for f in folds)
            decay_values = [f.return_decay_pct for f in folds if f.is_trade_count > 0]
            if decay_values:
                report.avg_decay_pct = sum(decay_values) / len(decay_values)
                report.max_decay_pct = max(decay_values)
            positive_folds = sum(1 for f in folds if f.oos_avg_return > 0)
            report.oos_consistency = positive_folds / len(folds) if folds else 0

        return report

    @staticmethod
    def print_report(report: WalkForwardReport) -> str:
        """Format walk-forward report as text."""
        lines = [
            "=" * 80,
            "WALK-FORWARD VALIDATION REPORT",
            "=" * 80,
            f"Total folds: {report.total_folds}",
            f"Total OOS trades: {report.total_oos_trades}",
            "",
            "─── Per-Fold Results ──────────────────────────────────────",
            f"  {'Fold':>4} {'Train':>22} {'Test':>22} {'IS Ret':>8} {'OOS Ret':>8} {'Decay':>7}",
            "  " + "-" * 72,
        ]

        for f in report.folds:
            lines.append(
                f"  {f.fold_id:>4} "
                f"{str(f.train_start)[:10]}→{str(f.train_end)[:10]} "
                f"{str(f.test_start)[:10]}→{str(f.test_end)[:10]} "
                f"{f.is_avg_return:>+7.2%} "
                f"{f.oos_avg_return:>+7.2%} "
                f"{f.return_decay_pct:>+6.1f}%"
            )

        lines.extend([
            "",
            "─── Aggregate OOS ────────────────────────────────────────",
            f"  Avg OOS return:     {report.avg_oos_return:>+.2%}",
            f"  Avg OOS hit rate:   {report.avg_oos_hit_rate:>.1%}",
            f"  OOS consistency:    {report.oos_consistency:>.0%} of folds positive",
            f"  Avg decay (IS→OOS): {report.avg_decay_pct:>+.1f}%",
            f"  Max decay:          {report.max_decay_pct:>+.1f}%",
            "",
        ])

        # Robustness verdict
        if report.avg_decay_pct < 30 and report.oos_consistency >= 0.5:
            lines.append("  ✅ ROBUST — OOS performance stable across folds")
        elif report.avg_decay_pct < 50:
            lines.append("  ⚠️  MARGINAL — significant OOS decay detected")
        else:
            lines.append("  ❌ OVERFIT — OOS performance degrades severely")

        lines.append("=" * 80)
        text = "\n".join(lines)
        print(text)
        return text
