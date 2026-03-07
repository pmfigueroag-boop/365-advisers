"""
src/engines/portfolio_lab/blender.py
─────────────────────────────────────────────────────────────────────────────
StrategyBlender — combine multiple strategy portfolios into a master allocation.

Blending methods:
  - equal: Equal weight across strategies
  - risk_parity: Weight inversely to strategy volatility
  - regime_adaptive: Shift weights based on regime performance
  - momentum: Overweight recently outperforming strategies
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

logger = logging.getLogger("365advisers.portfolio_lab.blender")


class StrategyBlender:
    """Combine multiple strategies into a blended master portfolio."""

    @staticmethod
    def blend(
        strategies: list[dict],
        method: str = "equal",
        current_regime: str | None = None,
        lookback_months: int = 3,
    ) -> dict:
        """Blend multiple strategy portfolios.

        Args:
            strategies: List of {name, metrics, positions}
            method: "equal" | "risk_parity" | "regime_adaptive" | "momentum"
            current_regime: Current market regime (for regime_adaptive)
            lookback_months: Lookback for momentum method

        Returns:
            Blended portfolio with per-strategy weights and merged positions.
        """
        if not strategies:
            return {"error": "No strategies to blend"}

        n = len(strategies)

        if method == "equal":
            weights = {s.get("name", f"s{i}"): 1.0 / n for i, s in enumerate(strategies)}

        elif method == "risk_parity":
            weights = _risk_parity_weights(strategies)

        elif method == "regime_adaptive":
            weights = _regime_adaptive_weights(strategies, current_regime)

        elif method == "momentum":
            weights = _momentum_weights(strategies, lookback_months)

        else:
            weights = {s.get("name", f"s{i}"): 1.0 / n for i, s in enumerate(strategies)}

        # Merge positions
        merged_positions = _merge_positions(strategies, weights)

        return {
            "method": method,
            "strategy_count": n,
            "weights": {k: round(v, 4) for k, v in weights.items()},
            "merged_positions": merged_positions,
            "position_count": len(merged_positions),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


def _risk_parity_weights(strategies: list[dict]) -> dict[str, float]:
    """Weight inversely to strategy volatility."""
    vols = {}
    for s in strategies:
        name = s.get("name", "")
        vol = s.get("metrics", {}).get("annualized_volatility", 0.15)
        vols[name] = max(vol, 0.01)  # Floor at 1%

    inv_vols = {name: 1.0 / vol for name, vol in vols.items()}
    total = sum(inv_vols.values())
    return {name: iv / total for name, iv in inv_vols.items()}


def _regime_adaptive_weights(strategies: list[dict], regime: str | None) -> dict[str, float]:
    """Weight by regime-specific Sharpe ratio."""
    if not regime:
        # Equal weight fallback
        n = len(strategies)
        return {s.get("name", f"s{i}"): 1.0 / n for i, s in enumerate(strategies)}

    regime_sharpes = {}
    for s in strategies:
        name = s.get("name", "")
        regime_data = s.get("regime_analysis", {}).get("regimes", {})
        regime_stats = regime_data.get(regime, {})
        sharpe = max(regime_stats.get("sharpe_ratio", 0), 0.01)
        regime_sharpes[name] = sharpe

    total = sum(regime_sharpes.values())
    return {name: v / total for name, v in regime_sharpes.items()}


def _momentum_weights(strategies: list[dict], lookback_months: int) -> dict[str, float]:
    """Overweight recently outperforming strategies."""
    recent_returns = {}
    for s in strategies:
        name = s.get("name", "")
        monthly = s.get("monthly_returns", [])

        if monthly and len(monthly) >= lookback_months:
            recent = monthly[-lookback_months:]
            avg_ret = sum(m.get("return", 0) for m in recent) / len(recent)
        else:
            avg_ret = s.get("metrics", {}).get("total_return", 0)

        recent_returns[name] = max(avg_ret + 0.01, 0.001)  # Ensure positive

    total = sum(recent_returns.values())
    return {name: v / total for name, v in recent_returns.items()}


def _merge_positions(strategies: list[dict], weights: dict[str, float]) -> list[dict]:
    """Merge positions across strategies weighted by strategy allocation."""
    ticker_weights: dict[str, float] = {}
    ticker_sources: dict[str, list[str]] = {}

    for s in strategies:
        name = s.get("name", "")
        strategy_weight = weights.get(name, 0)
        positions = s.get("positions", [])

        if isinstance(positions, dict):
            positions = positions.get("positions", [])

        for pos in positions:
            ticker = pos.get("ticker", "")
            pos_weight = pos.get("weight", 0)
            blended_weight = pos_weight * strategy_weight

            ticker_weights[ticker] = ticker_weights.get(ticker, 0) + blended_weight
            ticker_sources.setdefault(ticker, []).append(name)

    # Build merged list
    merged = []
    for ticker, weight in sorted(ticker_weights.items(), key=lambda x: x[1], reverse=True):
        merged.append({
            "ticker": ticker,
            "weight": round(weight, 6),
            "sources": ticker_sources.get(ticker, []),
            "source_count": len(ticker_sources.get(ticker, [])),
        })

    return merged
