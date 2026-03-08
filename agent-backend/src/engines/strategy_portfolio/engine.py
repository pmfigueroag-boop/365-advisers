"""
src/engines/strategy_portfolio/engine.py
─────────────────────────────────────────────────────────────────────────────
StrategyPortfolioEngine — 7-stage pipeline for multi-strategy portfolio
simulation and evaluation.

Pipeline:
  1. Portfolio Definition
  2. Per-Strategy Backtest (via StrategyBacktestEngine)
  3. Strategy Allocation (7 methods)
  4. Position Aggregation
  5. Portfolio Constraints
  6. Cost-Aware Execution
  7. Portfolio Analytics
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("365advisers.strategy_portfolio.engine")


class StrategyPortfolioEngine:
    """Multi-strategy portfolio simulation with 7-stage pipeline."""

    @staticmethod
    def run(
        portfolio_config: dict,
        data: dict,
        initial_capital: float = 1_000_000.0,
        use_full_cost_model: bool = True,
    ) -> dict:
        """Run a full multi-strategy portfolio simulation.

        Args:
            portfolio_config: {
                name, portfolio_type, strategies: [{strategy_name, strategy_config, target_weight}],
                allocation_method, constraints, rebalance_frequency, benchmark
            }
            data: BacktestDataBundle dict (shared across all strategies)
            initial_capital: Starting capital
            use_full_cost_model: Use 4-component cost model

        Returns:
            Complete portfolio result with per-strategy backtests,
            merged positions, diversification, contribution, and metrics.
        """
        import time
        t0 = time.perf_counter()
        portfolio_id = uuid.uuid4().hex[:12]

        name = portfolio_config.get("name", "Untitled Portfolio")
        strategies = portfolio_config.get("strategies", [])
        allocation_method = portfolio_config.get("allocation_method", "equal")
        constraints = portfolio_config.get("constraints", {})
        benchmark_name = portfolio_config.get("benchmark", "SPY")

        if not strategies:
            return {"error": "No strategies defined", "portfolio_id": portfolio_id}

        # ── Stage 2: Per-Strategy Backtest ──
        from src.engines.strategy_backtest.full_engine import StrategyBacktestEngine

        strategy_results = []
        for s in strategies:
            cfg = s.get("strategy_config", s.get("config", {}))
            cfg["name"] = s.get("strategy_name", s.get("name", "unnamed"))

            result = StrategyBacktestEngine.run(
                strategy_config=cfg,
                data=data,
                initial_capital=initial_capital,
                use_full_cost_model=use_full_cost_model,
            )
            strategy_results.append(result)

        if all("error" in r for r in strategy_results):
            return {"error": "All strategy backtests failed", "portfolio_id": portfolio_id}

        valid_results = [r for r in strategy_results if "error" not in r]

        # ── Stage 3: Strategy Allocation ──
        weights = _compute_allocation(valid_results, allocation_method, data)

        # Apply constraint caps
        max_single = constraints.get("max_single_strategy_weight", 0.50)
        min_weight = constraints.get("min_strategy_weight", 0.05)
        max_corr = constraints.get("max_strategy_correlation", 0.85)

        for name_k in weights:
            weights[name_k] = min(weights[name_k], max_single)
            if weights[name_k] < min_weight:
                weights[name_k] = 0.0

        # Remove zero-weight and renormalize
        weights = {k: v for k, v in weights.items() if v > 0}
        total_w = sum(weights.values())
        if total_w > 0:
            weights = {k: v / total_w for k, v in weights.items()}

        # ── Stage 4: Position Aggregation ──
        merged_positions = _merge_positions(valid_results, weights)

        # ── Stage 5: Portfolio Constraints ──
        # Apply position-level constraints from strategies
        max_positions = constraints.get("max_positions", 50)
        if len(merged_positions) > max_positions:
            merged_positions = sorted(merged_positions, key=lambda p: p["weight"], reverse=True)[:max_positions]

        # ── Stage 6: Build portfolio equity curve ──
        portfolio_equity = _build_portfolio_equity(valid_results, weights)

        # ── Stage 7: Portfolio Analytics ──
        from src.engines.strategy_backtest.full_engine import _compute_full_metrics, _compute_regime_analysis

        pv_series = [e["portfolio_value"] for e in portfolio_equity]
        bm_series = [e.get("benchmark_value") for e in portfolio_equity
                     if e.get("benchmark_value") is not None]

        metrics = _compute_full_metrics(pv_series, bm_series if bm_series else None)

        # Strategy contribution
        contribution = _compute_contribution(valid_results, weights)

        # Diversification analysis
        diversification = _compute_diversification(valid_results, weights)

        # Regime analysis
        regime_analysis = _compute_regime_analysis(portfolio_equity)

        # Cost aggregation
        total_cost_usd = sum(
            r.get("cost_analysis", {}).get("total_cost_usd", 0) * weights.get(r.get("strategy_name", ""), 0)
            for r in valid_results
        )

        # Portfolio-specific metrics
        metrics["diversification_ratio"] = diversification.get("diversification_ratio", 0)
        metrics["concentration_index"] = diversification.get("concentration_index", 0)
        metrics["position_count"] = len(merged_positions)
        metrics["strategy_count"] = len(weights)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        return {
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio_config.get("name", "Untitled"),
            "portfolio_type": portfolio_config.get("portfolio_type", "multi_strategy"),
            "period": valid_results[0].get("period") if valid_results else None,
            "trading_days": valid_results[0].get("trading_days", 0) if valid_results else 0,
            "initial_capital": initial_capital,
            "final_value": round(pv_series[-1], 2) if pv_series else 0,
            "total_return": round((pv_series[-1] - pv_series[0]) / pv_series[0], 4) if len(pv_series) > 1 else 0,

            # Allocation
            "allocation_method": allocation_method,
            "weights": {k: round(v, 4) for k, v in weights.items()},

            # Strategies
            "strategies": [
                {
                    "name": r.get("strategy_name", "unnamed"),
                    "weight": round(weights.get(r.get("strategy_name", ""), 0), 4),
                    "total_return": r.get("total_return", 0),
                    "sharpe": r.get("metrics", {}).get("sharpe_ratio", 0),
                    "max_drawdown": r.get("metrics", {}).get("max_drawdown", 0),
                }
                for r in valid_results
            ],
            "strategy_results": valid_results,

            # Portfolio
            "merged_positions": merged_positions[:30],  # Top 30 positions
            "equity_curve": portfolio_equity,
            "metrics": metrics,

            # Analysis
            "strategy_contribution": contribution,
            "diversification": diversification,
            "regime_analysis": regime_analysis,
            "cost_analysis": {
                "total_cost_usd": round(total_cost_usd, 2),
                "total_cost_bps": round(total_cost_usd / max(initial_capital, 1) * 10000, 2),
            },
            "benchmark_comparison": {
                "benchmark_return": metrics.get("benchmark_return"),
                "alpha": metrics.get("alpha"),
                "beta": metrics.get("beta"),
                "information_ratio": metrics.get("information_ratio"),
                "tracking_error": metrics.get("tracking_error"),
            } if bm_series else None,

            "generated_at": datetime.now(timezone.utc).isoformat(),
            "execution_time_ms": elapsed_ms,
        }


# ── Allocation Methods ────────────────────────────────────────────────────────

def _compute_allocation(results: list[dict], method: str, data: dict) -> dict[str, float]:
    """Compute strategy weights using the specified method."""
    names = [r.get("strategy_name", f"s{i}") for i, r in enumerate(results)]
    n = len(names)

    if n == 0:
        return {}

    if method == "equal":
        return {name: 1.0 / n for name in names}

    elif method == "risk_parity":
        vols = {}
        for r in results:
            name = r.get("strategy_name", "")
            vol = r.get("metrics", {}).get("annualized_volatility", 0.15)
            vols[name] = max(vol, 0.01)
        inv_vols = {name: 1.0 / vol for name, vol in vols.items()}
        total = sum(inv_vols.values())
        return {name: iv / total for name, iv in inv_vols.items()}

    elif method == "regime_adaptive":
        regimes = data.get("regimes_by_date", {})
        regime_vals = list(regimes.values())
        current_regime = regime_vals[-1] if regime_vals else "unknown"

        regime_sharpes = {}
        for r in results:
            name = r.get("strategy_name", "")
            ra = r.get("regime_analysis", {}).get("regimes", {})
            sharpe = ra.get(current_regime, {}).get("sharpe_ratio", 0.01)
            regime_sharpes[name] = max(sharpe, 0.01)

        total = sum(regime_sharpes.values())
        return {name: v / total for name, v in regime_sharpes.items()}

    elif method == "momentum":
        recent_returns = {}
        for r in results:
            name = r.get("strategy_name", "")
            ec = r.get("equity_curve", [])
            if len(ec) > 63:  # ~3 months
                recent = ec[-63:]
                ret = (recent[-1]["portfolio_value"] - recent[0]["portfolio_value"]) / recent[0]["portfolio_value"]
            else:
                ret = r.get("total_return", 0)
            recent_returns[name] = max(ret + 0.01, 0.001)

        total = sum(recent_returns.values())
        return {name: v / total for name, v in recent_returns.items()}

    elif method == "mean_variance":
        return _mean_variance_optimize(results)

    elif method == "sharpe_optimal":
        return _sharpe_optimize(results)

    else:
        return {name: 1.0 / n for name in names}


def _mean_variance_optimize(results: list[dict]) -> dict[str, float]:
    """Simplified mean-variance optimization.
    Minimize portfolio variance at given return target.
    Uses inverse-variance as analytical approximation.
    """
    names = []
    returns_list = []
    vols_list = []

    for r in results:
        name = r.get("strategy_name", "")
        names.append(name)
        ret = r.get("metrics", {}).get("annualized_return", 0)
        vol = max(r.get("metrics", {}).get("annualized_volatility", 0.15), 0.01)
        returns_list.append(ret)
        vols_list.append(vol)

    # Inverse-variance weights (analytical MVO approximation)
    inv_var = [1.0 / (v ** 2) for v in vols_list]
    total = sum(inv_var)
    weights = {names[i]: inv_var[i] / total for i in range(len(names))}

    return weights


def _sharpe_optimize(results: list[dict]) -> dict[str, float]:
    """Sharpe-optimal allocation: weight proportional to Sharpe ratio."""
    names = []
    sharpes = []

    for r in results:
        name = r.get("strategy_name", "")
        names.append(name)
        sharpe = max(r.get("metrics", {}).get("sharpe_ratio", 0), 0.01)
        sharpes.append(sharpe)

    total = sum(sharpes)
    weights = {names[i]: sharpes[i] / total for i in range(len(names))}
    return weights


# ── Position Aggregation ──────────────────────────────────────────────────────

def _merge_positions(results: list[dict], weights: dict[str, float]) -> list[dict]:
    """Merge positions across strategies weighted by allocation."""
    ticker_weights: dict[str, float] = {}
    ticker_sources: dict[str, list[str]] = {}

    for r in results:
        name = r.get("strategy_name", "")
        strategy_weight = weights.get(name, 0)
        ph = r.get("positions_history", [])
        if not ph:
            continue

        # Use last snapshot
        last_snap = ph[-1]
        positions = last_snap.get("positions", [])

        for pos in positions:
            ticker = pos.get("ticker", "")
            pos_weight = pos.get("weight", 0)
            blended = pos_weight * strategy_weight

            ticker_weights[ticker] = ticker_weights.get(ticker, 0) + blended
            ticker_sources.setdefault(ticker, []).append(name)

    merged = []
    for ticker, weight in sorted(ticker_weights.items(), key=lambda x: x[1], reverse=True):
        merged.append({
            "ticker": ticker,
            "weight": round(weight, 6),
            "sources": list(set(ticker_sources.get(ticker, []))),
            "source_count": len(set(ticker_sources.get(ticker, []))),
        })

    return merged


# ── Portfolio Equity Curve ────────────────────────────────────────────────────

def _build_portfolio_equity(results: list[dict], weights: dict[str, float]) -> list[dict]:
    """Build weighted portfolio equity curve from strategy equity curves."""
    # Align all curves by date
    date_values: dict[str, dict[str, float]] = {}  # date → {strategy → value}
    date_benchmark: dict[str, float] = {}
    date_regime: dict[str, str] = {}

    for r in results:
        name = r.get("strategy_name", "")
        ec = r.get("equity_curve", [])
        for point in ec:
            d = point["date"]
            date_values.setdefault(d, {})[name] = point["portfolio_value"]
            if point.get("benchmark_value") is not None:
                date_benchmark[d] = point["benchmark_value"]
            date_regime[d] = point.get("regime", "unknown")

    # Build portfolio curve
    dates = sorted(date_values.keys())
    if not dates:
        return []

    # Get initial values per strategy (from first date)
    initial_values = {}
    for name, val in date_values.get(dates[0], {}).items():
        initial_values[name] = val

    portfolio_curve = []
    peak = 0.0

    for d in dates:
        day_values = date_values.get(d, {})

        # Weighted portfolio value
        pv = 0.0
        total_w = 0.0
        for name, val in day_values.items():
            w = weights.get(name, 0)
            if name in initial_values and initial_values[name] > 0:
                # Normalize: strategy return × weight × initial_capital
                strategy_return = val / initial_values[name]
                pv += w * strategy_return
                total_w += w

        if total_w == 0:
            continue

        portfolio_value = pv / total_w * initial_values.get(list(initial_values.keys())[0], 1_000_000)

        peak = max(peak, portfolio_value)
        dd = (portfolio_value - peak) / peak if peak > 0 else 0

        portfolio_curve.append({
            "date": d,
            "portfolio_value": round(portfolio_value, 2),
            "benchmark_value": round(date_benchmark.get(d, 0), 2) if d in date_benchmark else None,
            "drawdown": round(dd, 4),
            "regime": date_regime.get(d, "unknown"),
            "positions_count": len([n for n in day_values if weights.get(n, 0) > 0]),
        })

    return portfolio_curve


# ── Strategy Contribution ─────────────────────────────────────────────────────

def _compute_contribution(results: list[dict], weights: dict[str, float]) -> list[dict]:
    """Compute each strategy's contribution to portfolio return."""
    contributions = []
    total_weighted_return = 0.0

    for r in results:
        name = r.get("strategy_name", "")
        w = weights.get(name, 0)
        ret = r.get("total_return", 0)
        weighted_ret = w * ret
        total_weighted_return += weighted_ret

        contributions.append({
            "strategy_name": name,
            "weight": round(w, 4),
            "strategy_return": round(ret, 4),
            "weighted_return": round(weighted_ret, 4),
        })

    # Compute contribution percentage
    for c in contributions:
        if total_weighted_return != 0:
            c["contribution_pct"] = round(c["weighted_return"] / total_weighted_return * 100, 1)
        else:
            c["contribution_pct"] = 0.0

    # Sort by contribution
    contributions.sort(key=lambda x: x["weighted_return"], reverse=True)

    return contributions


# ── Diversification Analysis ──────────────────────────────────────────────────

def _compute_diversification(results: list[dict], weights: dict[str, float]) -> dict:
    """Compute diversification metrics for the strategy portfolio."""
    n = len(results)
    if n < 2:
        return {
            "correlation_matrix": {},
            "diversification_ratio": 1.0,
            "position_overlap": {},
            "concentration_index": 1.0,
            "max_correlation": 0.0,
            "verdict": "single_strategy",
        }

    # ── Return correlation matrix ──
    return_series: dict[str, list[float]] = {}
    for r in results:
        name = r.get("strategy_name", "")
        ec = r.get("equity_curve", [])
        values = [e["portfolio_value"] for e in ec]
        if len(values) > 1:
            rets = [(values[i] - values[i - 1]) / values[i - 1]
                    for i in range(1, len(values)) if values[i - 1] > 0]
            return_series[name] = rets

    names = list(return_series.keys())
    corr_matrix: dict[str, dict[str, float]] = {}
    max_corr = 0.0

    for i, na in enumerate(names):
        corr_matrix[na] = {}
        for j, nb in enumerate(names):
            if i == j:
                corr_matrix[na][nb] = 1.0
            elif j < i:
                corr_matrix[na][nb] = corr_matrix[nb][na]
            else:
                c = _pearson_corr(return_series[na], return_series[nb])
                corr_matrix[na][nb] = round(c, 4)
                max_corr = max(max_corr, abs(c))

    # ── Position overlap (Jaccard) ──
    position_sets: dict[str, set[str]] = {}
    for r in results:
        name = r.get("strategy_name", "")
        ph = r.get("positions_history", [])
        if ph:
            tickers = {p["ticker"] for p in ph[-1].get("positions", [])}
            position_sets[name] = tickers

    overlap: dict[str, float] = {}
    for i, na in enumerate(names):
        for j, nb in enumerate(names):
            if j <= i:
                continue
            sa = position_sets.get(na, set())
            sb = position_sets.get(nb, set())
            union = sa | sb
            inter = sa & sb
            jaccard = len(inter) / len(union) if union else 0
            overlap[f"{na}_vs_{nb}"] = round(jaccard, 4)

    # ── Diversification ratio ──
    # DR = Σ(w_i × σ_i) / σ_portfolio
    weighted_vols = 0.0
    for r in results:
        name = r.get("strategy_name", "")
        vol = r.get("metrics", {}).get("annualized_volatility", 0.15)
        w = weights.get(name, 0)
        weighted_vols += w * vol

    # Portfolio vol (simplified: assume avg correlation)
    avg_corr = 0.0
    pair_count = 0
    for i, na in enumerate(names):
        for j, nb in enumerate(names):
            if j <= i:
                continue
            avg_corr += corr_matrix.get(na, {}).get(nb, 0)
            pair_count += 1
    avg_corr = avg_corr / pair_count if pair_count > 0 else 0

    vols = [r.get("metrics", {}).get("annualized_volatility", 0.15) for r in results]
    ws = [weights.get(r.get("strategy_name", ""), 0) for r in results]

    # Portfolio variance approximation
    port_var = 0.0
    for i in range(n):
        for j in range(n):
            if i == j:
                port_var += ws[i] ** 2 * vols[i] ** 2
            else:
                c = corr_matrix.get(names[i] if i < len(names) else "", {}).get(
                    names[j] if j < len(names) else "", avg_corr)
                port_var += ws[i] * ws[j] * vols[i] * vols[j] * c

    port_vol = math.sqrt(max(port_var, 0.0001))
    div_ratio = weighted_vols / port_vol if port_vol > 0 else 1.0

    # ── Concentration Index (HHI) ──
    hhi = sum(w ** 2 for w in weights.values())

    # Verdict
    if div_ratio >= 1.3 and max_corr < 0.6:
        verdict = "well_diversified"
    elif div_ratio >= 1.1 or max_corr < 0.75:
        verdict = "moderately_diversified"
    else:
        verdict = "concentrated"

    return {
        "correlation_matrix": corr_matrix,
        "diversification_ratio": round(div_ratio, 4),
        "position_overlap": overlap,
        "concentration_index": round(hhi, 4),
        "max_correlation": round(max_corr, 4),
        "verdict": verdict,
        "avg_correlation": round(avg_corr, 4),
    }


def _pearson_corr(a: list[float], b: list[float]) -> float:
    """Compute Pearson correlation between two return series."""
    n = min(len(a), len(b))
    if n < 2:
        return 0.0

    a = a[:n]
    b = b[:n]
    mean_a = sum(a) / n
    mean_b = sum(b) / n

    cov = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n)) / (n - 1)
    std_a = math.sqrt(sum((x - mean_a) ** 2 for x in a) / (n - 1))
    std_b = math.sqrt(sum((x - mean_b) ** 2 for x in b) / (n - 1))

    return cov / (std_a * std_b) if std_a > 0 and std_b > 0 else 0.0
