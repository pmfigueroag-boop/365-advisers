"""
src/engines/pilot/metrics.py
─────────────────────────────────────────────────────────────────────────────
PilotMetrics — rolling metric calculators for the pilot deployment.

Computes signal, idea, strategy, and portfolio metrics plus
leaderboards and Go/No-Go success criteria evaluation.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

from .config import MetricTargets
from .models import (
    MetricLevel,
    PilotIdeaMetrics,
    PilotPortfolioMetrics,
    PilotSignalMetrics,
    PilotStrategyMetrics,
    PilotHealthStatus,
    PilotSuccessAssessment,
    PortfolioType,
    SignalLeaderboardEntry,
    StrategyLeaderboardEntry,
    SuccessCriterionResult,
)

logger = logging.getLogger("365advisers.pilot.metrics")


class PilotMetrics:
    """
    Computes rolling pilot metrics from raw data snapshots.

    This module is stateless — it receives data and returns computed metrics.
    Persistence is handled by the PilotRunner.
    """

    def __init__(self):
        self.targets = MetricTargets()

    # ── Signal Metrics ──────────────────────────────────────────────────

    def compute_signal_metrics(
        self,
        signal_firings: list[dict[str, Any]],
        forward_returns: dict[str, list[float]],
    ) -> list[PilotSignalMetrics]:
        """
        Compute signal-level metrics from firing history and forward returns.

        Args:
            signal_firings: list of {signal_id, category, fired_at, ticker}
            forward_returns: {signal_id: [5d_return, 20d_return, ...]}
        """
        # Group by category
        by_category: dict[str, list[dict]] = {}
        for firing in signal_firings:
            cat = firing.get("category", "unknown")
            by_category.setdefault(cat, []).append(firing)

        results = []
        all_returns_5d = []
        all_returns_20d = []

        for category, firings in by_category.items():
            returns_5d = []
            returns_20d = []

            for f in firings:
                sid = f.get("signal_id", "")
                if sid in forward_returns:
                    rets = forward_returns[sid]
                    if len(rets) > 0:
                        returns_5d.append(rets[0])
                    if len(rets) > 1:
                        returns_20d.append(rets[1])

            hit_rate_5d = (
                sum(1 for r in returns_5d if r > 0) / len(returns_5d)
                if returns_5d else 0.0
            )
            hit_rate_20d = (
                sum(1 for r in returns_20d if r > 0) / len(returns_20d)
                if returns_20d else 0.0
            )
            avg_5d = sum(returns_5d) / len(returns_5d) if returns_5d else 0.0
            avg_20d = sum(returns_20d) / len(returns_20d) if returns_20d else 0.0

            # Information Coefficient (simplified: correlation with direction)
            ic = self._compute_ic(returns_20d) if returns_20d else 0.0
            ic_ir = ic / (self._std(returns_20d) + 1e-9) if returns_20d else 0.0

            results.append(PilotSignalMetrics(
                category=category,
                hit_rate_5d=round(hit_rate_5d, 4),
                hit_rate_20d=round(hit_rate_20d, 4),
                avg_forward_return_5d=round(avg_5d, 6),
                avg_forward_return_20d=round(avg_20d, 6),
                information_coefficient=round(ic, 4),
                ic_ir=round(ic_ir, 4),
                signal_breadth=len(set(f.get("signal_id") for f in firings)),
                total_firings=len(firings),
            ))

            all_returns_5d.extend(returns_5d)
            all_returns_20d.extend(returns_20d)

        # Aggregate
        if all_returns_20d:
            agg_hr = sum(1 for r in all_returns_20d if r > 0) / len(all_returns_20d)
            agg_avg = sum(all_returns_20d) / len(all_returns_20d)
            results.append(PilotSignalMetrics(
                category="aggregate",
                hit_rate_5d=round(
                    sum(1 for r in all_returns_5d if r > 0) / max(len(all_returns_5d), 1), 4
                ),
                hit_rate_20d=round(agg_hr, 4),
                avg_forward_return_5d=round(
                    sum(all_returns_5d) / max(len(all_returns_5d), 1), 6
                ),
                avg_forward_return_20d=round(agg_avg, 6),
                information_coefficient=round(self._compute_ic(all_returns_20d), 4),
                total_firings=len(signal_firings),
            ))

        return results

    # ── Idea Metrics ────────────────────────────────────────────────────

    def compute_idea_metrics(
        self,
        ideas: list[dict[str, Any]],
    ) -> list[PilotIdeaMetrics]:
        """
        Compute idea-level metrics.

        Args:
            ideas: list of {idea_type, return_20d, alpha, decay_days}
        """
        by_type: dict[str, list[dict]] = {}
        for idea in ideas:
            itype = idea.get("idea_type", "unknown")
            by_type.setdefault(itype, []).append(idea)

        results = []
        for itype, type_ideas in by_type.items():
            returns = [i.get("return_20d", 0) for i in type_ideas]
            alphas = [i.get("alpha", 0) for i in type_ideas]
            decays = [i.get("decay_days", 0) for i in type_ideas if i.get("decay_days")]

            hr = sum(1 for r in returns if r > 0) / max(len(returns), 1)

            results.append(PilotIdeaMetrics(
                idea_type=itype,
                hit_rate=round(hr, 4),
                avg_alpha=round(sum(alphas) / max(len(alphas), 1), 6),
                avg_decay_days=round(sum(decays) / max(len(decays), 1), 1),
                detector_precision=round(hr, 4),
                ideas_generated=len(type_ideas),
            ))

        return results

    # ── Strategy Metrics ────────────────────────────────────────────────

    def compute_strategy_metrics(
        self,
        strategy_returns: dict[str, list[float]],
        strategy_names: dict[str, str] | None = None,
        risk_free_rate: float = 0.04,
    ) -> list[PilotStrategyMetrics]:
        """
        Compute strategy performance metrics from daily return series.

        Args:
            strategy_returns: {strategy_id: [daily_returns]}
            strategy_names: {strategy_id: display_name}
            risk_free_rate: annual risk-free rate for Sharpe calculation
        """
        results = []
        daily_rf = risk_free_rate / 252

        for sid, returns in strategy_returns.items():
            if not returns:
                continue

            avg = sum(returns) / len(returns)
            std = self._std(returns)

            # Sharpe (annualised)
            sharpe = (
                (avg - daily_rf) / std * math.sqrt(252)
                if std > 0 else 0.0
            )

            # Sortino (annualised) — only downside deviation
            downside = [r for r in returns if r < 0]
            ds_std = self._std(downside) if downside else 1e-9
            sortino = (avg - daily_rf) / ds_std * math.sqrt(252) if ds_std > 0 else 0.0

            # Max drawdown
            cum = 0.0
            peak = 0.0
            max_dd = 0.0
            for r in returns:
                cum += r
                peak = max(peak, cum)
                dd = peak - cum
                max_dd = max(max_dd, dd)

            # Calmar
            annual_return = avg * 252
            calmar = annual_return / max_dd if max_dd > 0 else 0.0

            # Win rate
            wins = sum(1 for r in returns if r > 0)
            win_rate = wins / len(returns) if returns else 0.0

            # Avg win / avg loss
            gain = [r for r in returns if r > 0]
            loss = [abs(r) for r in returns if r < 0]
            avg_wl = (
                (sum(gain) / len(gain)) / (sum(loss) / len(loss))
                if gain and loss else 0.0
            )

            name = (strategy_names or {}).get(sid, sid)

            results.append(PilotStrategyMetrics(
                strategy_id=sid,
                strategy_name=name,
                sharpe_ratio=round(sharpe, 4),
                sortino_ratio=round(sortino, 4),
                max_drawdown=round(max_dd, 4),
                calmar_ratio=round(calmar, 4),
                win_rate=round(win_rate, 4),
                avg_win_loss_ratio=round(avg_wl, 4),
            ))

        return results

    # ── Portfolio Metrics ───────────────────────────────────────────────

    def compute_portfolio_metrics(
        self,
        portfolio_returns: dict[str, list[float]],
        benchmark_returns: list[float],
        portfolio_types: dict[str, PortfolioType] | None = None,
    ) -> list[PilotPortfolioMetrics]:
        """
        Compute portfolio-level performance metrics.

        Args:
            portfolio_returns: {portfolio_id: [daily_returns]}
            benchmark_returns: [daily_returns] of the benchmark
            portfolio_types: {portfolio_id: PortfolioType}
        """
        results = []

        for pid, returns in portfolio_returns.items():
            if not returns:
                continue

            total_ret = sum(returns)
            bench_ret = sum(benchmark_returns[:len(returns)]) if benchmark_returns else 0.0
            alpha = total_ret - bench_ret

            std = self._std(returns)
            avg = sum(returns) / len(returns)
            ann_vol = std * math.sqrt(252) if std > 0 else 0.0

            sharpe = (avg / std) * math.sqrt(252) if std > 0 else 0.0

            # Tracking error and IR
            if benchmark_returns:
                excess = [r - b for r, b in zip(returns, benchmark_returns)]
                te = self._std(excess)
                ir = (sum(excess) / len(excess)) / te * math.sqrt(252) if te > 0 else 0.0
            else:
                ir = 0.0

            ptype = (portfolio_types or {}).get(pid, PortfolioType.RESEARCH)

            results.append(PilotPortfolioMetrics(
                portfolio_id=pid,
                portfolio_type=ptype,
                total_return=round(total_ret, 6),
                alpha_vs_benchmark=round(alpha, 6),
                information_ratio=round(ir, 4),
                annualized_volatility=round(ann_vol, 4),
                sharpe_ratio=round(sharpe, 4),
            ))

        return results

    # ── Health ──────────────────────────────────────────────────────────

    def compute_health_status(
        self,
        pipeline_complete: bool,
        data_fresh: bool,
        data_last_updated: datetime | None,
        active_strategies: int,
        target_strategies: int,
        critical_alerts: int,
        warning_alerts: int,
        run_duration_seconds: float,
        uptime_pct: float = 100.0,
    ) -> PilotHealthStatus:
        return PilotHealthStatus(
            pipeline_status="complete" if pipeline_complete else "failed",
            data_fresh=data_fresh,
            data_last_updated=data_last_updated,
            uptime_pct=uptime_pct,
            active_strategies_count=active_strategies,
            target_strategies_count=target_strategies,
            critical_alerts_count=critical_alerts,
            warning_alerts_count=warning_alerts,
            last_run_duration_seconds=round(run_duration_seconds, 2),
        )

    # ── Leaderboards ────────────────────────────────────────────────────

    def generate_signal_leaderboard(
        self,
        signal_metrics: list[PilotSignalMetrics],
        top_n: int = 10,
    ) -> list[SignalLeaderboardEntry]:
        """Top N signals by hit rate (20d)."""
        # Filter out aggregate
        items = [s for s in signal_metrics if s.category != "aggregate"]
        sorted_items = sorted(items, key=lambda s: s.hit_rate_20d, reverse=True)

        return [
            SignalLeaderboardEntry(
                rank=i + 1,
                signal_id=s.category,
                signal_name=s.category,
                category=s.category,
                hit_rate=s.hit_rate_20d,
                avg_return=s.avg_forward_return_20d,
                ic=s.information_coefficient,
                total_firings=s.total_firings,
            )
            for i, s in enumerate(sorted_items[:top_n])
        ]

    def generate_strategy_leaderboard(
        self,
        strategy_metrics: list[PilotStrategyMetrics],
    ) -> list[StrategyLeaderboardEntry]:
        """All strategies ranked by quality score, then Sharpe."""
        sorted_items = sorted(
            strategy_metrics,
            key=lambda s: (s.quality_score, s.sharpe_ratio),
            reverse=True,
        )
        return [
            StrategyLeaderboardEntry(
                rank=i + 1,
                strategy_id=s.strategy_id,
                strategy_name=s.strategy_name,
                sharpe_ratio=s.sharpe_ratio,
                max_drawdown=s.max_drawdown,
                quality_score=s.quality_score,
            )
            for i, s in enumerate(sorted_items)
        ]

    # ── Go / No-Go ──────────────────────────────────────────────────────

    def check_success_criteria(
        self,
        signal_hit_rate: float,
        research_alpha: float,
        strategy_sharpe: float,
        max_drawdown: float,
        strategy_quality: float,
        system_uptime: float,
        pilot_id: str = "",
    ) -> PilotSuccessAssessment:
        """
        Evaluate the 6 quantitative Go/No-Go criteria.
        Returns GO if ≥ 4/6 pass, EXTEND if 3/6, NO_GO if ≤ 2/6.
        """
        criteria = [
            SuccessCriterionResult(
                criterion_name="Signal Hit Rate",
                description="Aggregate signal hit rate (20d forward) ≥ 53%",
                target_value=self.targets.SIGNAL_HIT_RATE,
                actual_value=signal_hit_rate,
                passed=signal_hit_rate >= self.targets.SIGNAL_HIT_RATE,
            ),
            SuccessCriterionResult(
                criterion_name="Research Portfolio Alpha",
                description="Research portfolio alpha vs benchmark > 0%",
                target_value=self.targets.RESEARCH_ALPHA,
                actual_value=research_alpha,
                passed=research_alpha > self.targets.RESEARCH_ALPHA,
            ),
            SuccessCriterionResult(
                criterion_name="Strategy Portfolio Sharpe",
                description="Strategy portfolio Sharpe ratio > 0.8",
                target_value=self.targets.STRATEGY_SHARPE,
                actual_value=strategy_sharpe,
                passed=strategy_sharpe > self.targets.STRATEGY_SHARPE,
            ),
            SuccessCriterionResult(
                criterion_name="Max Drawdown",
                description="Max drawdown across all portfolios < 20%",
                target_value=self.targets.MAX_DRAWDOWN,
                actual_value=max_drawdown,
                passed=max_drawdown < self.targets.MAX_DRAWDOWN,
            ),
            SuccessCriterionResult(
                criterion_name="Strategy Quality Score",
                description="Average strategy quality score > 60",
                target_value=self.targets.STRATEGY_QUALITY,
                actual_value=strategy_quality,
                passed=strategy_quality > self.targets.STRATEGY_QUALITY,
            ),
            SuccessCriterionResult(
                criterion_name="System Uptime",
                description="System uptime > 99%",
                target_value=self.targets.SYSTEM_UPTIME,
                actual_value=system_uptime,
                passed=system_uptime > self.targets.SYSTEM_UPTIME,
            ),
        ]

        passed = sum(1 for c in criteria if c.passed)

        if passed >= self.targets.MIN_CRITERIA_FOR_GO:
            recommendation = "GO"
        elif passed == self.targets.MIN_CRITERIA_FOR_GO - 1:
            recommendation = "EXTEND"
        else:
            recommendation = "NO_GO"

        return PilotSuccessAssessment(
            pilot_id=pilot_id,
            criteria_results=criteria,
            criteria_passed=passed,
            criteria_total=self.targets.TOTAL_CRITERIA,
            recommendation=recommendation,
        )

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _std(values: list[float]) -> float:
        """Standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return math.sqrt(variance)

    @staticmethod
    def _compute_ic(returns: list[float]) -> float:
        """
        Simplified IC: fraction of returns that are positive minus 0.5,
        scaled to correlation-like range.
        """
        if not returns:
            return 0.0
        pos = sum(1 for r in returns if r > 0)
        return (pos / len(returns)) - 0.5
