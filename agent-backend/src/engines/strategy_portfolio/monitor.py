"""
src/engines/strategy_portfolio/monitor.py
─────────────────────────────────────────────────────────────────────────────
PortfolioMonitor — monitoring for multi-strategy portfolios.

Tracks weight drift, correlation drift, and generates rebalance alerts.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

logger = logging.getLogger("365advisers.strategy_portfolio.monitor")


class PortfolioMonitor:
    """Monitor a strategy portfolio for drift and performance alerts."""

    @staticmethod
    def check(
        portfolio_result: dict,
        drift_threshold: float = 0.05,
        correlation_threshold: float = 0.85,
        drawdown_alert_threshold: float = -0.10,
    ) -> dict:
        """Check portfolio health and generate alerts.

        Args:
            portfolio_result: Result from StrategyPortfolioEngine.run()
            drift_threshold: Trigger alert if weight drift exceeds this
            correlation_threshold: Alert if any pair exceeds this
            drawdown_alert_threshold: Alert if DD exceeds this (negative)

        Returns:
            MonitorState with alerts and rebalance recommendations.
        """
        alerts: list[dict] = []
        weights = portfolio_result.get("weights", {})
        strategies = portfolio_result.get("strategies", [])

        # ── Weight drift ──
        composition = []
        for s in strategies:
            name = s.get("name", "")
            target_w = weights.get(name, 0)
            # Approximate current weight from returns
            ret = s.get("total_return", 0)
            current_w = target_w * (1 + ret)
            drift = abs(current_w - target_w)

            composition.append({
                "strategy": name,
                "target_weight": round(target_w, 4),
                "current_weight": round(current_w, 4),
                "drift": round(drift, 4),
            })

            if drift >= drift_threshold:
                alerts.append({
                    "type": "drift",
                    "severity": "warning" if drift < drift_threshold * 2 else "critical",
                    "msg": f"Strategy {name} drifted {drift:.1%} from target ({target_w:.1%} → {current_w:.1%})",
                })

        # ── Correlation drift ──
        div = portfolio_result.get("diversification", {})
        corr_matrix = div.get("correlation_matrix", {})
        max_corr = div.get("max_correlation", 0)

        if max_corr >= correlation_threshold:
            # Find the pair
            for na, row in corr_matrix.items():
                for nb, c in row.items():
                    if na != nb and abs(c) >= correlation_threshold:
                        alerts.append({
                            "type": "correlation",
                            "severity": "warning",
                            "msg": f"Strategies {na} + {nb} correlation is {c:.2f} (threshold: {correlation_threshold})",
                        })
                        break
                else:
                    continue
                break

        # ── Drawdown alert ──
        metrics = portfolio_result.get("metrics", {})
        max_dd = metrics.get("max_drawdown", 0)
        if max_dd < drawdown_alert_threshold:
            alerts.append({
                "type": "drawdown",
                "severity": "critical",
                "msg": f"Portfolio max drawdown {max_dd:.1%} exceeds threshold ({drawdown_alert_threshold:.1%})",
            })

        # ── Concentration alert ──
        hhi = div.get("concentration_index", 0)
        if hhi > 0.35:
            alerts.append({
                "type": "concentration",
                "severity": "info",
                "msg": f"Portfolio is concentrated (HHI={hhi:.2f}). Consider adding more strategies.",
            })

        # ── Regime alignment ──
        regime_analysis = portfolio_result.get("regime_analysis", {})
        regime_alignment = {
            "best_regime": regime_analysis.get("best_regime"),
            "worst_regime": regime_analysis.get("worst_regime"),
            "regime_count": regime_analysis.get("regime_count", 0),
        }

        # ── Rebalance recommendation ──
        needs_rebalance = any(a["type"] == "drift" for a in alerts)
        rebalance_rec = None
        if needs_rebalance:
            rebalance_rec = {
                "action": "rebalance",
                "reason": "Weight drift detected",
                "drifted_strategies": [
                    c["strategy"] for c in composition if c["drift"] >= drift_threshold
                ],
            }

        return {
            "portfolio_id": portfolio_result.get("portfolio_id"),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "current_composition": composition,
            "performance_vs_benchmark": portfolio_result.get("benchmark_comparison", {}),
            "regime_alignment": regime_alignment,
            "alerts": alerts,
            "alert_count": len(alerts),
            "rebalance_recommendation": rebalance_rec,
            "health_status": "healthy" if not alerts else (
                "critical" if any(a.get("severity") == "critical" for a in alerts) else "warning"
            ),
        }
