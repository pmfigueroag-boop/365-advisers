"""
src/engines/strategy_research/scorecard.py
─────────────────────────────────────────────────────────────────────────────
StrategyScorecard — comprehensive strategy quality scoring (0–100).

Aggregates five dimensions:
  1. Performance (return, Sharpe, Sortino)
  2. Stability (walk-forward, regime consistency)
  3. Robustness (drawdown, recovery, tail risk)
  4. Efficiency (turnover, cost drag, capacity)
  5. Signal Quality (IC, decay, breadth from signal_lab)
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

logger = logging.getLogger("365advisers.strategy_research.scorecard")


class StrategyScorecard:
    """Compute Strategy Quality Score (0–100) from backtest + signal data."""

    DIMENSION_WEIGHTS = {
        "performance": 0.30,
        "stability": 0.20,
        "robustness": 0.20,
        "efficiency": 0.15,
        "signal_quality": 0.15,
    }

    @staticmethod
    def compute(
        backtest_result: dict | None = None,
        signal_lab_report: dict | None = None,
        stability_data: dict | None = None,
    ) -> dict:
        """Compute full strategy scorecard.

        Args:
            backtest_result: Output from StrategyBacktester.run()
            signal_lab_report: Output from LabReport.generate()
            stability_data: Walk-forward or bootstrap stability results

        Returns:
            {total_score: 0-100, dimensions: {name: {score, details}}}
        """
        dimensions = {}

        # 1. Performance Score
        dimensions["performance"] = _score_performance(backtest_result)

        # 2. Stability Score
        dimensions["stability"] = _score_stability(stability_data)

        # 3. Robustness Score
        dimensions["robustness"] = _score_robustness(backtest_result)

        # 4. Efficiency Score
        dimensions["efficiency"] = _score_efficiency(backtest_result)

        # 5. Signal Quality Score
        dimensions["signal_quality"] = _score_signal_quality(signal_lab_report)

        # Weighted total
        total = sum(
            dimensions[dim]["score"] * StrategyScorecard.DIMENSION_WEIGHTS[dim]
            for dim in dimensions
        )

        # Grade
        grade = _classify_grade(total)

        return {
            "total_score": round(total, 1),
            "grade": grade,
            "dimensions": dimensions,
            "weights": StrategyScorecard.DIMENSION_WEIGHTS,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def rank_strategies(scorecards: list[dict]) -> list[dict]:
        """Rank strategies by total quality score."""
        ranked = sorted(scorecards, key=lambda s: s.get("total_score", 0), reverse=True)
        for i, sc in enumerate(ranked):
            sc["rank"] = i + 1
        return ranked


# ── Dimension Scorers ────────────────────────────────────────────────────────

def _score_performance(backtest: dict | None) -> dict:
    """Score performance (0–100) from backtest metrics."""
    if not backtest:
        return {"score": 0, "details": {"note": "No backtest data"}}

    metrics = backtest.get("metrics", {})
    sharpe = metrics.get("sharpe_ratio", 0)
    sortino = metrics.get("sortino_ratio", 0)
    total_return = metrics.get("total_return", 0)
    alpha = metrics.get("alpha", 0)

    # Sharpe: 0 → 0pts, 1 → 40pts, 2+ → 60pts
    sharpe_score = min(60, max(0, sharpe * 30))
    # Sortino bonus: up to 20pts
    sortino_bonus = min(20, max(0, sortino * 10))
    # Return bonus: up to 20pts
    return_bonus = min(20, max(0, total_return * 100))

    score = min(100, sharpe_score + sortino_bonus + return_bonus)

    return {
        "score": round(score, 1),
        "details": {
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "total_return": total_return,
            "alpha": alpha,
        },
    }


def _score_stability(stability: dict | None) -> dict:
    """Score stability (0–100) from walk-forward results."""
    if not stability:
        return {"score": 50, "details": {"note": "No stability data — default 50"}}

    consistency = stability.get("temporal_consistency", 0.5)
    bootstrap_score = stability.get("bootstrap", {}).get("stability_score", 0.5)
    trend = stability.get("temporal", {}).get("trend", "stable")

    # Consistency: 0–60pts
    consistency_pts = consistency * 60
    # Bootstrap stability: 0–30pts
    bootstrap_pts = bootstrap_score * 30
    # Trend bonus: +10 improving, 0 stable, -10 degrading
    trend_pts = {"improving": 10, "stable": 0, "degrading": -10}.get(trend, 0)

    score = max(0, min(100, consistency_pts + bootstrap_pts + trend_pts))

    return {
        "score": round(score, 1),
        "details": {
            "temporal_consistency": consistency,
            "bootstrap_stability": bootstrap_score,
            "trend": trend,
        },
    }


def _score_robustness(backtest: dict | None) -> dict:
    """Score robustness (0–100) from drawdown and recovery metrics."""
    if not backtest:
        return {"score": 0, "details": {"note": "No backtest data"}}

    metrics = backtest.get("metrics", {})
    max_dd = abs(metrics.get("max_drawdown", 0))
    calmar = min(metrics.get("calmar_ratio", 0), 10)
    win_rate = metrics.get("win_rate", 0.5)

    # Low drawdown = high score: <5% → 50pts, <10% → 40pts, <20% → 25pts, >30% → 0pts
    if max_dd < 0.05:
        dd_score = 50
    elif max_dd < 0.10:
        dd_score = 40
    elif max_dd < 0.20:
        dd_score = 25
    elif max_dd < 0.30:
        dd_score = 10
    else:
        dd_score = 0

    # Calmar: up to 30pts
    calmar_score = min(30, calmar * 10)
    # Win rate bonus: up to 20pts
    win_pts = max(0, (win_rate - 0.4) * 50)  # 50% → 5pts, 60% → 10pts

    score = min(100, dd_score + calmar_score + win_pts)

    return {
        "score": round(score, 1),
        "details": {
            "max_drawdown": max_dd,
            "calmar_ratio": calmar,
            "win_rate": win_rate,
        },
    }


def _score_efficiency(backtest: dict | None) -> dict:
    """Score efficiency (0–100) from turnover and cost metrics."""
    if not backtest:
        return {"score": 50, "details": {"note": "No backtest data — default 50"}}

    trades = backtest.get("trades", [])
    total_cost = backtest.get("total_cost_usd", 0)
    initial = backtest.get("initial_capital", 1_000_000)

    cost_drag_pct = total_cost / initial if initial > 0 else 0
    avg_turnover = sum(t.get("turnover", 0) for t in trades) / max(len(trades), 1)

    # Low cost drag = high score: <0.5% → 40pts, <1% → 30pts, <2% → 15pts
    if cost_drag_pct < 0.005:
        cost_score = 40
    elif cost_drag_pct < 0.01:
        cost_score = 30
    elif cost_drag_pct < 0.02:
        cost_score = 15
    else:
        cost_score = 0

    # Low turnover = high score: <10% → 30pts, <25% → 20pts, <50% → 10pts
    if avg_turnover < 0.10:
        turnover_score = 30
    elif avg_turnover < 0.25:
        turnover_score = 20
    elif avg_turnover < 0.50:
        turnover_score = 10
    else:
        turnover_score = 0

    # Trade count penalty: >100 trades per year is noisy
    n_trades = len(trades)
    trade_penalty = max(0, (n_trades - 100) * 0.1)

    score = max(0, min(100, cost_score + turnover_score + 30 - trade_penalty))

    return {
        "score": round(score, 1),
        "details": {
            "cost_drag_pct": round(cost_drag_pct, 4),
            "avg_turnover": round(avg_turnover, 4),
            "total_trades": n_trades,
        },
    }


def _score_signal_quality(signal_report: dict | None) -> dict:
    """Score signal quality (0–100) from Signal Lab report."""
    if not signal_report:
        return {"score": 50, "details": {"note": "No signal lab data — default 50"}}

    library_quality = signal_report.get("library_quality", 0.5)
    diversity = signal_report.get("diversity_score", 0.5)
    redundancy = signal_report.get("redundancy_score", 0)

    quality_pts = library_quality * 50  # 0–50
    diversity_pts = diversity * 30       # 0–30
    no_redundancy_pts = (1 - redundancy) * 20  # 0–20

    score = min(100, quality_pts + diversity_pts + no_redundancy_pts)

    return {
        "score": round(score, 1),
        "details": {
            "library_quality": library_quality,
            "diversity_score": diversity,
            "redundancy_score": redundancy,
        },
    }


def _classify_grade(score: float) -> str:
    """Classify score into institutional grade."""
    if score >= 85:
        return "A+"
    elif score >= 75:
        return "A"
    elif score >= 65:
        return "B+"
    elif score >= 55:
        return "B"
    elif score >= 45:
        return "C+"
    elif score >= 35:
        return "C"
    else:
        return "D"
