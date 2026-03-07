"""
src/engines/shadow/performance.py
─────────────────────────────────────────────────────────────────────────────
ShadowPerformanceCalc — Computes performance analytics for shadow portfolios:
Sharpe ratio, max drawdown, daily returns, cumulative returns.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from src.data.database import SessionLocal

logger = logging.getLogger("365advisers.shadow.performance")


class ShadowPerformanceCalc:
    """Computes analytics from shadow portfolio snapshots."""

    def compute_performance(self, portfolio_id: str) -> dict:
        """Compute full performance statistics from NAV time series."""
        from src.data.database import ShadowSnapshotRecord

        with SessionLocal() as db:
            snapshots = (
                db.query(ShadowSnapshotRecord)
                .filter(ShadowSnapshotRecord.portfolio_id == portfolio_id)
                .order_by(ShadowSnapshotRecord.snapshot_date.asc())
                .all()
            )

        if not snapshots:
            return {"portfolio_id": portfolio_id, "error": "No snapshots"}

        navs = [s.nav for s in snapshots]
        daily_returns = [s.daily_return or 0.0 for s in snapshots]

        # Cumulative return
        total_return = (navs[-1] - 100.0) / 100.0 if navs else 0.0

        # Max drawdown
        peak = 100.0
        max_dd = 0.0
        for nav in navs:
            peak = max(peak, nav)
            dd = (nav - peak) / peak
            max_dd = min(max_dd, dd)

        # Sharpe ratio (annualized, assuming ~252 trading days)
        n = len(daily_returns)
        if n > 1:
            mean_ret = sum(daily_returns) / n
            variance = sum((r - mean_ret) ** 2 for r in daily_returns) / (n - 1)
            std_ret = math.sqrt(variance) if variance > 0 else 1e-6
            sharpe = (mean_ret / std_ret) * math.sqrt(252)
        else:
            sharpe = 0.0

        # Sortino (only downside deviation)
        downside_returns = [r for r in daily_returns if r < 0]
        if len(downside_returns) > 1:
            downside_var = sum(r ** 2 for r in downside_returns) / len(downside_returns)
            downside_dev = math.sqrt(downside_var) if downside_var > 0 else 1e-6
            mean_ret = sum(daily_returns) / n if n > 0 else 0.0
            sortino = (mean_ret / downside_dev) * math.sqrt(252)
        else:
            sortino = 0.0

        # Win rate
        positive_days = sum(1 for r in daily_returns if r > 0)
        win_rate = positive_days / n if n > 0 else 0.0

        return {
            "portfolio_id": portfolio_id,
            "total_return_pct": round(total_return * 100, 4),
            "current_nav": round(navs[-1], 4) if navs else 100.0,
            "max_drawdown_pct": round(max_dd * 100, 4),
            "sharpe_ratio": round(sharpe, 4),
            "sortino_ratio": round(sortino, 4),
            "win_rate": round(win_rate, 4),
            "total_snapshots": n,
            "latest_date": (
                snapshots[-1].snapshot_date.isoformat() if snapshots else None
            ),
        }

    def compare_portfolios(self, portfolio_ids: list[str]) -> dict:
        """Compare performance across multiple shadow portfolios."""
        results = {}
        for pid in portfolio_ids:
            results[pid] = self.compute_performance(pid)
        return {
            "portfolios": results,
            "comparison_date": datetime.now(timezone.utc).isoformat(),
        }

    def get_nav_series(self, portfolio_id: str, limit: int = 252) -> list[dict]:
        """Return the NAV time series for charting."""
        from src.data.database import ShadowSnapshotRecord

        with SessionLocal() as db:
            snapshots = (
                db.query(ShadowSnapshotRecord)
                .filter(ShadowSnapshotRecord.portfolio_id == portfolio_id)
                .order_by(ShadowSnapshotRecord.snapshot_date.desc())
                .limit(limit)
                .all()
            )

        return [
            {
                "date": s.snapshot_date.isoformat() if s.snapshot_date else None,
                "nav": s.nav,
                "daily_return": s.daily_return,
                "cumulative_return": s.cumulative_return,
                "drawdown": s.drawdown,
                "positions": s.positions_count,
            }
            for s in reversed(snapshots)
        ]
