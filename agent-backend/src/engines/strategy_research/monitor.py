"""
src/engines/strategy_research/monitor.py
─────────────────────────────────────────────────────────────────────────────
StrategyMonitor — unified live/paper strategy monitoring hub.

Aggregates data from shadow portfolios, scorecards, and monitoring
into a unified strategy status view with alerts.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger("365advisers.strategy_research.monitor")


class StrategyMonitor:
    """Unified strategy monitoring hub."""

    @staticmethod
    def get_status(
        strategy_id: str,
        shadow_data: dict | None = None,
        scorecard_data: dict | None = None,
        regime_data: dict | None = None,
    ) -> dict:
        """Get comprehensive strategy status.

        Args:
            strategy_id: Strategy identifier
            shadow_data: Shadow portfolio state (positions, P&L)
            scorecard_data: Live scorecard metrics
            regime_data: Current regime info

        Returns:
            Unified strategy status.
        """
        status = "active"
        alerts = []

        # Parse shadow portfolio data
        positions = []
        unrealized_pnl = 0.0
        realized_pnl = 0.0

        if shadow_data:
            positions = shadow_data.get("positions", [])
            unrealized_pnl = shadow_data.get("unrealized_pnl", 0.0)
            realized_pnl = shadow_data.get("realized_pnl", 0.0)

            # Check for drift
            if shadow_data.get("drift_detected", False):
                alerts.append({
                    "type": "drift",
                    "severity": "warning",
                    "message": "Concept drift detected — strategy signals may be degrading",
                })
                status = "degraded"

        # Parse scorecard
        total_score = 0
        grade = "N/A"
        if scorecard_data:
            total_score = scorecard_data.get("total_score", 0)
            grade = scorecard_data.get("grade", "N/A")

            if total_score < 35:
                alerts.append({
                    "type": "quality",
                    "severity": "critical",
                    "message": f"Strategy quality score critically low: {total_score}/100",
                })
                status = "degraded"
            elif total_score < 50:
                alerts.append({
                    "type": "quality",
                    "severity": "warning",
                    "message": f"Strategy quality score below target: {total_score}/100",
                })

        # Parse regime
        current_regime = "unknown"
        regime_alignment = "neutral"
        if regime_data:
            current_regime = regime_data.get("current_regime", "unknown")
            best_regime = regime_data.get("best_regime", "unknown")
            worst_regime = regime_data.get("worst_regime", "unknown")

            if current_regime == best_regime:
                regime_alignment = "favorable"
            elif current_regime == worst_regime:
                regime_alignment = "unfavorable"
                alerts.append({
                    "type": "regime",
                    "severity": "warning",
                    "message": f"Current regime '{current_regime}' is this strategy's weakest",
                })

        # Performance alerts
        if unrealized_pnl < -0.10:  # > 10% drawdown
            alerts.append({
                "type": "drawdown",
                "severity": "critical",
                "message": f"Unrealized P&L at {unrealized_pnl:.1%}",
            })
            status = "degraded"

        return {
            "strategy_id": strategy_id,
            "status": status,
            "alert_count": len(alerts),
            "alerts": alerts,

            "positions": {
                "count": len(positions),
                "tickers": [p.get("ticker", "") for p in positions[:10]],
            },

            "performance": {
                "unrealized_pnl": round(unrealized_pnl, 4),
                "realized_pnl": round(realized_pnl, 4),
            },

            "quality": {
                "score": total_score,
                "grade": grade,
            },

            "regime": {
                "current": current_regime,
                "alignment": regime_alignment,
            },

            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def get_all_statuses(strategies: list[dict]) -> dict:
        """Get status summary for all active strategies.

        Args:
            strategies: List of {strategy_id, shadow_data, scorecard_data, regime_data}

        Returns:
            Summary with per-strategy statuses and aggregate health.
        """
        statuses = []
        active = 0
        degraded = 0
        total_alerts = 0

        for s in strategies:
            st = StrategyMonitor.get_status(
                strategy_id=s.get("strategy_id", ""),
                shadow_data=s.get("shadow_data"),
                scorecard_data=s.get("scorecard_data"),
                regime_data=s.get("regime_data"),
            )
            statuses.append(st)

            if st["status"] == "active":
                active += 1
            else:
                degraded += 1
            total_alerts += st["alert_count"]

        return {
            "total_strategies": len(statuses),
            "active": active,
            "degraded": degraded,
            "total_alerts": total_alerts,
            "statuses": statuses,
            "health": "healthy" if degraded == 0 else "degraded" if degraded < len(statuses) else "critical",
        }

    @staticmethod
    def check_exit_conditions(
        positions: list[dict],
        exit_rules: list[dict],
    ) -> list[dict]:
        """Check exit conditions for all positions.

        Args:
            positions: Current positions with {ticker, entry_date, unrealized_pnl_pct, days_held, ...}
            exit_rules: ExitRule dicts from StrategyConfig

        Returns:
            List of positions that should be exited.
        """
        from .rules import RuleEngine

        exits = []
        for pos in positions:
            result = RuleEngine.evaluate_exit(pos, exit_rules)
            if result["should_exit"]:
                exits.append({
                    "ticker": pos.get("ticker", ""),
                    "reason": result["triggered_rules"],
                    "position": pos,
                })

        return exits
