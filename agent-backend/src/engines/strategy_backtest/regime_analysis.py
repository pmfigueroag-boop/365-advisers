"""
src/engines/strategy_backtest/regime_analysis.py
─────────────────────────────────────────────────────────────────────────────
RegimePerformance — analyze strategy performance across market regimes.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict

logger = logging.getLogger("365advisers.strategy_backtest.regime")


class RegimePerformance:
    """Analyze strategy performance breakdown by market regime."""

    @staticmethod
    def analyze(
        equity_curve: list[dict],
        regime_labels: dict[str, str] | None = None,
    ) -> dict:
        """Break down strategy performance by market regime.

        Args:
            equity_curve: [{date, portfolio_value, benchmark_value}]
            regime_labels: Optional {date: regime} mapping

        Returns:
            Performance breakdown per regime.
        """
        if not equity_curve or len(equity_curve) < 2:
            return {"regimes": {}, "error": "Insufficient data"}

        # Auto-detect regimes from returns if not provided
        if not regime_labels:
            regime_labels = _auto_detect_regimes(equity_curve)

        # Group returns by regime
        regime_returns: dict[str, list[float]] = defaultdict(list)

        for i in range(1, len(equity_curve)):
            date = equity_curve[i]["date"]
            prev_val = equity_curve[i - 1]["portfolio_value"]
            curr_val = equity_curve[i]["portfolio_value"]

            if prev_val > 0:
                ret = (curr_val - prev_val) / prev_val
                regime = regime_labels.get(date, "unknown")
                regime_returns[regime].append(ret)

        # Compute metrics per regime
        regimes = {}
        for regime, returns in regime_returns.items():
            n = len(returns)
            mean_r = sum(returns) / n if n > 0 else 0
            var_r = sum((r - mean_r) ** 2 for r in returns) / max(n - 1, 1)
            std_r = math.sqrt(var_r)
            ann_ret = mean_r * 252
            ann_vol = std_r * math.sqrt(252)
            sharpe = ann_ret / ann_vol if ann_vol > 0 else 0

            win_rate = sum(1 for r in returns if r > 0) / n if n > 0 else 0

            regimes[regime] = {
                "periods": n,
                "mean_return": round(mean_r, 6),
                "annualized_return": round(ann_ret, 4),
                "annualized_volatility": round(ann_vol, 4),
                "sharpe_ratio": round(sharpe, 4),
                "win_rate": round(win_rate, 4),
                "worst_period": round(min(returns), 6) if returns else 0,
                "best_period": round(max(returns), 6) if returns else 0,
            }

        # Rank regimes
        sorted_regimes = sorted(regimes.items(), key=lambda x: x[1]["annualized_return"], reverse=True)

        return {
            "regimes": regimes,
            "best_regime": sorted_regimes[0][0] if sorted_regimes else None,
            "worst_regime": sorted_regimes[-1][0] if sorted_regimes else None,
            "regime_count": len(regimes),
        }


def _auto_detect_regimes(equity_curve: list[dict]) -> dict[str, str]:
    """Simple regime detection based on benchmark trend."""
    regimes = {}
    window = 20  # lookback window

    for i, entry in enumerate(equity_curve):
        date = entry["date"]
        bm_val = entry.get("benchmark_value")

        if bm_val and i >= window:
            bm_prev = equity_curve[i - window].get("benchmark_value", bm_val)
            if bm_prev > 0:
                trend = (bm_val - bm_prev) / bm_prev
                if trend > 0.02:
                    regimes[date] = "bull"
                elif trend < -0.02:
                    regimes[date] = "bear"
                else:
                    regimes[date] = "range"
            else:
                regimes[date] = "unknown"
        else:
            regimes[date] = "unknown"

    return regimes
