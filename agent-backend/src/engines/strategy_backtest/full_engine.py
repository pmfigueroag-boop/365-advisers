"""
src/engines/strategy_backtest/full_engine.py
─────────────────────────────────────────────────────────────────────────────
StrategyBacktestEngine — 8-stage pipeline for full strategy backtesting.

Pipeline:
  1. Strategy Definition (read StrategyConfig)
  2. Historical Data (receive BacktestDataBundle)
  3. Temporal Signal Replay
  4. Entry / Exit Rule Evaluation
  5. Position Sizing
  6. Portfolio Construction (constraints + rebalancing)
  7. Cost-Aware Execution
  8. Performance Analytics

Reuses existing engines:
  - StrategyComposer (signal filtering)
  - RuleEngine (entry/exit/regime rules)
  - ExecutionCostAggregator (4-component cost model)
  - StrategyMetrics (risk-adjusted metrics)
  - RegimePerformance (regime breakdown)
  - BenchmarkComparison (benchmark analysis)
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("365advisers.strategy_backtest.full_engine")


class StrategyBacktestEngine:
    """Full strategy backtesting with 8-stage pipeline."""

    @staticmethod
    def run(
        strategy_config: dict,
        data: dict,
        initial_capital: float = 1_000_000.0,
        use_full_cost_model: bool = True,
        cost_per_trade_bps: float = 5.0,
    ) -> dict:
        """Run a full strategy backtest.

        Args:
            strategy_config: StrategyConfig dict (SDF format)
            data: BacktestDataBundle dict with prices, signals, scores, regimes
            initial_capital: Starting capital
            use_full_cost_model: Use 4-component cost model vs flat bps
            cost_per_trade_bps: Fallback flat cost (if use_full_cost_model=False)

        Returns:
            Complete BacktestResult dict.
        """
        import time
        t0 = time.perf_counter()
        run_id = uuid.uuid4().hex[:12]

        # ── Extract config components ──
        signals_cfg = strategy_config.get("signals", {})
        thresholds_cfg = strategy_config.get("thresholds", {})
        portfolio_cfg = strategy_config.get("portfolio", {})
        rebalance_cfg = strategy_config.get("rebalance", {})
        entry_rules = strategy_config.get("entry_rules", [])
        exit_rules = strategy_config.get("exit_rules", [])
        regime_rules = strategy_config.get("regime_rules", [])

        # Legacy fallbacks
        signal_filters = strategy_config.get("signal_filters", {})
        score_filters = strategy_config.get("score_filters", {})
        portfolio_rules = strategy_config.get("portfolio_rules", {})

        # Merged parameters
        required_cats = signals_cfg.get("required_categories") or signal_filters.get("required_categories", [])
        preferred_signals = signals_cfg.get("preferred_signals", [])
        min_strength = signals_cfg.get("min_signal_strength") or signal_filters.get("min_signal_strength", 0.0)
        min_confidence_str = signals_cfg.get("min_confidence") or signal_filters.get("min_confidence", "low")
        composition_logic = signals_cfg.get("composition_logic", "all_required")
        min_active = signals_cfg.get("min_active_signals", 1)

        min_case = thresholds_cfg.get("min_case_score") or score_filters.get("min_case_score", 0)
        min_uos = thresholds_cfg.get("min_uos") or score_filters.get("min_uos", 0.0)

        max_positions = portfolio_cfg.get("max_positions") or portfolio_rules.get("max_positions", 20)
        sizing_method = portfolio_cfg.get("sizing_method") or portfolio_rules.get("sizing_method", "vol_parity")
        max_single = portfolio_cfg.get("max_single_position") or portfolio_rules.get("max_single_position", 0.10)
        max_sector = portfolio_cfg.get("max_sector_exposure") or portfolio_rules.get("max_sector_exposure", 0.25)
        max_turnover = portfolio_cfg.get("max_turnover", 0.50)

        rebalance_freq = rebalance_cfg.get("frequency") or portfolio_rules.get("rebalance_frequency", "weekly")
        trigger_type = rebalance_cfg.get("trigger_type", "calendar")
        drift_threshold = rebalance_cfg.get("drift_threshold", 0.05)

        # ── Extract data ──
        prices = data.get("prices", {})
        signals_by_date = data.get("signals_by_date", {})
        scores_by_date = data.get("scores_by_date", {})
        regimes_by_date = data.get("regimes_by_date", {})
        benchmark_prices = data.get("benchmark_prices", {})
        liquidity = data.get("liquidity", {})

        # ── Determine trading dates ──
        all_dates: set[str] = set()
        for ticker_prices in prices.values():
            all_dates.update(ticker_prices.keys())
        all_dates.update(signals_by_date.keys())
        trading_dates = sorted(all_dates)

        if len(trading_dates) < 2:
            return {"error": "Insufficient trading dates", "run_id": run_id}

        # Confidence value mapping
        conf_map = {"low": 0.0, "medium": 0.3, "high": 0.6}
        min_conf_val = conf_map.get(min_confidence_str, 0.0)

        # Strength mapping
        strength_map = {"strong": 3, "moderate": 2, "weak": 1}

        # ── Initialize state ──
        holdings: dict[str, float] = {}  # ticker → weight
        portfolio_value = initial_capital
        equity_curve: list[dict] = []
        trades: list[dict] = []
        positions_history: list[dict] = []
        total_cost_usd = 0.0
        cost_components = {"commission": 0.0, "spread": 0.0, "slippage": 0.0, "impact": 0.0}
        last_rebalance_idx = -999
        rebalance_count = 0

        # Cost model
        cost_aggregator = None
        if use_full_cost_model:
            try:
                from src.engines.execution.cost_models import ExecutionCostAggregator
                cost_aggregator = ExecutionCostAggregator()
            except ImportError:
                logger.warning("ExecutionCostAggregator not available, using flat cost")

        # ── MAIN BACKTEST LOOP ──
        for i, date in enumerate(trading_dates):

            # ── Stage 3: Signal replay ──
            day_signals = signals_by_date.get(date, [])
            day_scores = scores_by_date.get(date, {})
            current_regime = regimes_by_date.get(date, "unknown")

            # Filter signals
            filtered_sigs = _filter_signals(
                day_signals,
                required_categories=required_cats,
                min_strength=min_strength,
                min_conf_val=min_conf_val,
                strength_map=strength_map,
            )

            # Group by ticker
            ticker_signals: dict[str, list] = {}
            for sig in filtered_sigs:
                t = sig.get("ticker", "")
                ticker_signals.setdefault(t, []).append(sig)

            # Min active signals filter
            if min_active > 1:
                ticker_signals = {
                    t: sigs for t, sigs in ticker_signals.items()
                    if len(sigs) >= min_active
                }

            # Score filter
            eligible_tickers = set()
            for ticker in ticker_signals:
                scores = day_scores.get(ticker, {})
                case = scores.get("case_score", 0)
                uos = scores.get("uos", scores.get("opportunity_score", 0))
                if case >= min_case and uos >= min_uos:
                    eligible_tickers.add(ticker)

            # ── Calculate portfolio returns from previous holdings ──
            if i > 0 and holdings:
                prev_date = trading_dates[i - 1]
                period_return = 0.0
                for ticker, weight in holdings.items():
                    p_prev = prices.get(ticker, {}).get(prev_date, 0)
                    p_curr = prices.get(ticker, {}).get(date, 0)
                    if p_prev > 0 and p_curr > 0:
                        period_return += weight * ((p_curr - p_prev) / p_prev)
                portfolio_value *= (1 + period_return)

            # ── Stage 4: Entry/Exit evaluation ──
            pending_entries: list[str] = []
            pending_exits: list[str] = []

            # Entry: eligible tickers NOT in holdings
            for ticker in eligible_tickers:
                if ticker in holdings:
                    continue
                if not entry_rules:
                    pending_entries.append(ticker)
                    continue
                # Evaluate entry rules
                opp = _build_opportunity(ticker, day_scores.get(ticker, {}),
                                         ticker_signals.get(ticker, []),
                                         current_regime)
                if _evaluate_entry_rules(opp, entry_rules):
                    pending_entries.append(ticker)

            # Exit: holdings that should be exited
            for ticker in list(holdings.keys()):
                if not exit_rules:
                    continue
                pos = _build_position(ticker, holdings, prices, date, trading_dates,
                                      day_scores.get(ticker, {}))
                if _evaluate_exit_rules(pos, exit_rules):
                    pending_exits.append(ticker)

            # ── Regime overlay ──
            regime_action = _get_regime_action(current_regime, regime_rules)
            if regime_action == "exit_all":
                pending_exits = list(holdings.keys())
                pending_entries = []
            elif regime_action == "no_new_entries":
                pending_entries = []
            elif regime_action == "reduce_50":
                pending_entries = []  # No new entries during reduce

            # ── Check rebalance schedule ──
            should_rebalance = _should_rebalance(
                i, date, last_rebalance_idx, rebalance_freq,
                trigger_type, drift_threshold, holdings,
            )

            # ── Stage 5 & 6: Sizing + Portfolio construction ──
            if should_rebalance or pending_exits or pending_entries:
                # Execute exits
                for ticker in pending_exits:
                    if ticker in holdings:
                        exit_weight = holdings.pop(ticker)
                        cost = _compute_trade_cost(
                            portfolio_value, exit_weight, ticker, liquidity,
                            cost_aggregator, cost_per_trade_bps, cost_components,
                        )
                        portfolio_value -= cost
                        total_cost_usd += cost
                        trades.append({
                            "date": date, "ticker": ticker, "action": "sell",
                            "weight": round(exit_weight, 4),
                            "cost_bps": round(cost / max(portfolio_value, 1) * 10000, 2),
                            "cost_usd": round(cost, 2), "reason": "exit_rule",
                        })

                # Size and execute entries
                n_available_slots = max_positions - len(holdings)
                entries_to_add = pending_entries[:n_available_slots]

                if entries_to_add:
                    n_total = len(holdings) + len(entries_to_add)
                    for ticker in entries_to_add:
                        weight = _compute_weight(
                            sizing_method, n_total, max_single,
                            ticker_signals.get(ticker, []),
                            day_scores.get(ticker, {}),
                        )
                        holdings[ticker] = weight
                        cost = _compute_trade_cost(
                            portfolio_value, weight, ticker, liquidity,
                            cost_aggregator, cost_per_trade_bps, cost_components,
                        )
                        portfolio_value -= cost
                        total_cost_usd += cost
                        trades.append({
                            "date": date, "ticker": ticker, "action": "buy",
                            "weight": round(weight, 4),
                            "cost_bps": round(cost / max(portfolio_value, 1) * 10000, 2),
                            "cost_usd": round(cost, 2), "reason": "entry_rule",
                        })

                # Apply regime sizing override
                if regime_action == "reduce_50":
                    for ticker in list(holdings.keys()):
                        holdings[ticker] *= 0.5

                # Enforce constraints
                _enforce_constraints(holdings, max_single, max_positions)

                # Normalize weights
                total_w = sum(holdings.values())
                if total_w > 1.0:
                    for t in holdings:
                        holdings[t] /= total_w

                if should_rebalance:
                    last_rebalance_idx = i
                    rebalance_count += 1

            # ── Record equity curve ──
            benchmark_val = None
            if benchmark_prices:
                bm_p = benchmark_prices.get(date, 0)
                bm_first = benchmark_prices.get(trading_dates[0], 1)
                benchmark_val = initial_capital * (bm_p / bm_first) if bm_first > 0 else None

            # Drawdown
            peak = max((e["portfolio_value"] for e in equity_curve), default=initial_capital)
            peak = max(peak, portfolio_value)
            dd = (portfolio_value - peak) / peak if peak > 0 else 0

            equity_curve.append({
                "date": date,
                "portfolio_value": round(portfolio_value, 2),
                "benchmark_value": round(benchmark_val, 2) if benchmark_val else None,
                "drawdown": round(dd, 4),
                "regime": current_regime,
                "positions_count": len(holdings),
            })

            # ── Record positions snapshot ──
            if i % max(1, len(trading_dates) // 50) == 0 or i == len(trading_dates) - 1:
                positions_history.append({
                    "date": date,
                    "positions": [{"ticker": t, "weight": round(w, 4)} for t, w in holdings.items()],
                    "positions_count": len(holdings),
                })

        # ── Stage 8: Performance Analytics ──
        pv_series = [e["portfolio_value"] for e in equity_curve]
        bm_series = [e["benchmark_value"] for e in equity_curve
                     if e.get("benchmark_value") is not None]

        metrics = _compute_full_metrics(pv_series, bm_series if bm_series else None)

        # Turnover & cost metrics
        n_trades = len(trades)
        n_days = len(trading_dates)
        years = n_days / 252.0 if n_days > 0 else 1.0
        metrics["annualized_turnover"] = round(
            sum(t.get("weight", 0) for t in trades) / max(years, 0.01), 4
        )
        metrics["avg_positions"] = round(
            sum(e["positions_count"] for e in equity_curve) / max(len(equity_curve), 1), 1
        )
        metrics["cost_drag_bps"] = round(
            total_cost_usd / max(initial_capital, 1) * 10000 / max(years, 0.01), 2
        )
        metrics["rebalance_count"] = rebalance_count

        # Regime analysis
        regime_analysis = _compute_regime_analysis(equity_curve)

        # Cost breakdown
        cost_analysis = {
            "total_cost_usd": round(total_cost_usd, 2),
            "total_cost_bps": round(total_cost_usd / max(initial_capital, 1) * 10000, 2),
            "avg_cost_per_trade_bps": round(
                sum(t.get("cost_bps", 0) for t in trades) / max(n_trades, 1), 2
            ),
            "cost_breakdown": {k: round(v, 2) for k, v in cost_components.items()},
            "total_trades": n_trades,
        }

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        return {
            "run_id": run_id,
            "strategy_name": strategy_config.get("name",
                             strategy_config.get("metadata", {}).get("tags", ["unnamed"])[0]
                             if strategy_config.get("metadata", {}).get("tags") else "unnamed"),
            "config_snapshot": strategy_config,
            "period": [trading_dates[0], trading_dates[-1]],
            "trading_days": n_days,
            "initial_capital": initial_capital,
            "final_value": round(portfolio_value, 2),
            "total_return": round((portfolio_value - initial_capital) / initial_capital, 4),
            "metrics": metrics,
            "equity_curve": equity_curve,
            "trades": trades,
            "positions_history": positions_history,
            "regime_analysis": regime_analysis,
            "cost_analysis": cost_analysis,
            "benchmark_comparison": {
                "benchmark_return": metrics.get("benchmark_return"),
                "alpha": metrics.get("alpha"),
                "beta": metrics.get("beta"),
                "information_ratio": metrics.get("information_ratio"),
                "tracking_error": metrics.get("tracking_error"),
            } if bm_series else None,
            "walk_forward": None,  # Filled by caller if needed
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "execution_time_ms": elapsed_ms,
        }


# ── Helper Functions ──────────────────────────────────────────────────────────

def _filter_signals(
    signals: list[dict],
    required_categories: list[str],
    min_strength: float,
    min_conf_val: float,
    strength_map: dict,
) -> list[dict]:
    """Filter signals by category, strength, and confidence."""
    result = signals

    if required_categories:
        result = [s for s in result if s.get("category") in required_categories]

    if min_strength > 0:
        result = [
            s for s in result
            if strength_map.get(s.get("strength", "weak"), 0) >= min_strength
        ]

    if min_conf_val > 0:
        result = [s for s in result if s.get("confidence", 0.0) >= min_conf_val]

    return result


def _build_opportunity(
    ticker: str,
    scores: dict,
    signals: list[dict],
    regime: str,
) -> dict:
    """Build an opportunity dict for RuleEngine evaluation."""
    return {
        "ticker": ticker,
        "case_score": scores.get("case_score", 0),
        "opportunity_score": scores.get("opportunity_score", scores.get("uos", 0)),
        "uos": scores.get("uos", scores.get("opportunity_score", 0)),
        "business_quality": scores.get("business_quality", 0),
        "regime": regime,
        "signal_count": len(signals),
        "crowding_penalty": scores.get("crowding_penalty", 0),
    }


def _build_position(
    ticker: str,
    holdings: dict,
    prices: dict,
    current_date: str,
    dates: list[str],
    scores: dict,
) -> dict:
    """Build a position dict for exit rule evaluation."""
    weight = holdings.get(ticker, 0)
    current_price = prices.get(ticker, {}).get(current_date, 0)

    # Find entry price (first date we had this position — simplified)
    entry_price = current_price  # fallback
    for d in dates:
        if prices.get(ticker, {}).get(d, 0) > 0:
            entry_price = prices[ticker][d]
            break

    unrealized_pnl = ((current_price - entry_price) / entry_price) if entry_price > 0 else 0

    return {
        "ticker": ticker,
        "weight": weight,
        "entry_price": entry_price,
        "current_price": current_price,
        "unrealized_pnl": unrealized_pnl,
        "case_score": scores.get("case_score", 0),
        "regime": scores.get("regime", "unknown"),
    }


def _evaluate_entry_rules(opportunity: dict, rules: list[dict]) -> bool:
    """Evaluate entry rules against an opportunity (simplified inline)."""
    for rule in rules:
        field = rule.get("field", "")
        operator = rule.get("operator", "gte")
        value = rule.get("value", 0)

        actual = opportunity.get(field, 0)

        if operator == "gt" and not (actual > value):
            return False
        elif operator == "gte" and not (actual >= value):
            return False
        elif operator == "lt" and not (actual < value):
            return False
        elif operator == "lte" and not (actual <= value):
            return False
        elif operator == "eq" and actual != value:
            return False
        elif operator == "in" and isinstance(value, list) and actual not in value:
            return False
        elif operator == "not_in" and isinstance(value, list) and actual in value:
            return False

    return True


def _evaluate_exit_rules(position: dict, rules: list[dict]) -> bool:
    """Evaluate exit rules against a position."""
    for rule in rules:
        rule_type = rule.get("rule_type", "")
        params = rule.get("params", {})

        if rule_type == "trailing_stop":
            pct = params.get("pct", 0.15)
            if position.get("unrealized_pnl", 0) < -pct:
                return True

        elif rule_type == "target_reached":
            target = params.get("return_pct", 0.30)
            if position.get("unrealized_pnl", 0) >= target:
                return True

        elif rule_type == "signal_reversal":
            # Simplified: exit if case_score drops below threshold
            if position.get("case_score", 100) < 40:
                return True

    return False


def _get_regime_action(regime: str, rules: list[dict]) -> str:
    """Get action for current regime."""
    for rule in rules:
        if rule.get("regime") == regime:
            return rule.get("action", "full_exposure")
    return "full_exposure"


def _should_rebalance(
    idx: int,
    date: str,
    last_rebalance_idx: int,
    frequency: str,
    trigger_type: str,
    drift_threshold: float,
    holdings: dict,
) -> bool:
    """Determine if we should rebalance at this date."""
    if idx == 0:
        return True

    if trigger_type == "drift_based":
        # Simplified: rebalance if enough days have passed
        n = len(holdings) or 1
        target_w = 1.0 / n
        max_drift = max((abs(w - target_w) for w in holdings.values()), default=0)
        if max_drift >= drift_threshold:
            return True

    # Calendar-based
    freq_days = {
        "daily": 1,
        "weekly": 5,
        "biweekly": 10,
        "monthly": 21,
    }
    interval = freq_days.get(frequency, 5)
    return (idx - last_rebalance_idx) >= interval


def _compute_weight(
    method: str,
    n_positions: int,
    max_single: float,
    signals: list[dict],
    scores: dict,
) -> float:
    """Compute position weight based on sizing method."""
    n = max(n_positions, 1)

    if method == "equal":
        weight = 1.0 / n
    elif method == "rank_weighted":
        score = scores.get("case_score", scores.get("uos", 50))
        weight = max(score / 100, 0.01) / n * 2  # rough rank-weighted
    elif method == "risk_budget":
        weight = 1.0 / n  # simplified
    else:  # vol_parity
        weight = 1.0 / n

    return min(weight, max_single)


def _enforce_constraints(
    holdings: dict[str, float],
    max_single: float,
    max_positions: int,
) -> None:
    """Enforce portfolio constraints in place."""
    # Cap single position
    for t in holdings:
        holdings[t] = min(holdings[t], max_single)

    # Trim excess positions (keep highest weight)
    if len(holdings) > max_positions:
        sorted_h = sorted(holdings.items(), key=lambda x: x[1], reverse=True)
        to_remove = [t for t, _ in sorted_h[max_positions:]]
        for t in to_remove:
            del holdings[t]


def _compute_trade_cost(
    portfolio_value: float,
    weight: float,
    ticker: str,
    liquidity: dict,
    cost_aggregator: Any | None,
    flat_bps: float,
    cost_components: dict,
) -> float:
    """Compute execution cost for a trade."""
    order_value = portfolio_value * weight

    if cost_aggregator and ticker in liquidity:
        adv = liquidity[ticker]
        result = cost_aggregator.estimate_total_cost(order_value, adv)
        cost_components["commission"] += result.get("commission_bps", 0) * order_value / 10000
        cost_components["spread"] += result.get("half_spread_bps", 0) * order_value / 10000
        cost_components["slippage"] += result.get("slippage_bps", 0) * order_value / 10000
        cost_components["impact"] += result.get("market_impact_bps", 0) * order_value / 10000
        return result.get("total_cost_usd", order_value * flat_bps / 10000)

    return order_value * flat_bps / 10000


def _compute_full_metrics(
    portfolio_values: list[float],
    benchmark_values: list[float] | None = None,
    periods_per_year: float = 252.0,
) -> dict:
    """Compute comprehensive performance metrics (19 metrics)."""
    if len(portfolio_values) < 2:
        return _empty_metrics()

    returns = [(portfolio_values[i] - portfolio_values[i - 1]) / portfolio_values[i - 1]
               for i in range(1, len(portfolio_values)) if portfolio_values[i - 1] > 0]
    n = len(returns)
    if n == 0:
        return _empty_metrics()

    # Basic stats
    total_return = (portfolio_values[-1] - portfolio_values[0]) / portfolio_values[0]
    mean_return = sum(returns) / n

    # CAGR
    years = n / periods_per_year
    cagr = (portfolio_values[-1] / portfolio_values[0]) ** (1 / max(years, 0.01)) - 1

    # Volatility
    variance = sum((r - mean_return) ** 2 for r in returns) / max(n - 1, 1)
    std = math.sqrt(variance)
    ann_vol = std * math.sqrt(periods_per_year)
    ann_return = mean_return * periods_per_year

    # Sharpe
    sharpe = ann_return / ann_vol if ann_vol > 0 else 0.0

    # Sortino
    down_returns = [r for r in returns if r < 0]
    if down_returns:
        down_var = sum(r ** 2 for r in down_returns) / len(down_returns)
        downside_dev = math.sqrt(down_var) * math.sqrt(periods_per_year)
        sortino = ann_return / downside_dev if downside_dev > 0 else 0.0
    else:
        sortino = float("inf") if ann_return > 0 else 0.0

    # Max Drawdown + duration
    peak = portfolio_values[0]
    max_dd = 0.0
    dd_start = 0
    dd_end = 0
    peak_idx = 0
    dd_duration_days = 0
    current_dd_start = 0

    for i, v in enumerate(portfolio_values):
        if v > peak:
            peak = v
            peak_idx = i
        dd = (v - peak) / peak if peak > 0 else 0
        if dd < max_dd:
            max_dd = dd
            dd_start = peak_idx
            dd_end = i
            dd_duration_days = i - peak_idx

    # Calmar
    calmar = cagr / abs(max_dd) if max_dd < 0 else float("inf")

    # Win rate + win/loss ratio + profit factor
    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]
    win_rate = len(wins) / n if n > 0 else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 1
    win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf")
    profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else float("inf")

    result = {
        "total_return": round(total_return, 4),
        "cagr": round(cagr, 4),
        "annualized_return": round(ann_return, 4),
        "annualized_volatility": round(ann_vol, 4),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(min(sortino, 99.0), 4),
        "max_drawdown": round(max_dd, 4),
        "max_dd_duration_days": dd_duration_days,
        "max_drawdown_period": [dd_start, dd_end],
        "calmar_ratio": round(min(calmar, 99.0), 4),
        "win_rate": round(win_rate, 4),
        "avg_win_loss_ratio": round(min(win_loss_ratio, 99.0), 4),
        "profit_factor": round(min(profit_factor, 99.0), 4),
        "total_periods": n,
    }

    # Benchmark comparison
    if benchmark_values and len(benchmark_values) >= 2:
        bm_returns = [(benchmark_values[i] - benchmark_values[i - 1]) / benchmark_values[i - 1]
                      for i in range(1, len(benchmark_values)) if benchmark_values[i - 1] > 0]
        bm_total = (benchmark_values[-1] - benchmark_values[0]) / benchmark_values[0]

        alpha = total_return - bm_total
        min_len = min(len(returns), len(bm_returns))
        active_returns = [returns[i] - bm_returns[i] for i in range(min_len)]

        # Beta
        if min_len > 1:
            mean_p = sum(returns[:min_len]) / min_len
            mean_b = sum(bm_returns[:min_len]) / min_len
            cov = sum((returns[i] - mean_p) * (bm_returns[i] - mean_b) for i in range(min_len)) / (min_len - 1)
            var_b = sum((bm_returns[i] - mean_b) ** 2 for i in range(min_len)) / (min_len - 1)
            beta = cov / var_b if var_b > 0 else 1.0
        else:
            beta = 1.0

        # Tracking error + IR
        if active_returns:
            mean_active = sum(active_returns) / len(active_returns)
            te_var = sum((r - mean_active) ** 2 for r in active_returns) / max(len(active_returns) - 1, 1)
            tracking_error = math.sqrt(te_var) * math.sqrt(periods_per_year)
            ir = (mean_active * periods_per_year) / tracking_error if tracking_error > 0 else 0.0
        else:
            tracking_error = 0.0
            ir = 0.0

        result["benchmark_return"] = round(bm_total, 4)
        result["alpha"] = round(alpha, 4)
        result["beta"] = round(beta, 4)
        result["tracking_error"] = round(tracking_error, 4)
        result["information_ratio"] = round(ir, 4)

    return result


def _compute_regime_analysis(equity_curve: list[dict]) -> dict:
    """Compute per-regime performance from equity curve."""
    from collections import defaultdict

    regime_returns: dict[str, list[float]] = defaultdict(list)

    for i in range(1, len(equity_curve)):
        prev_val = equity_curve[i - 1]["portfolio_value"]
        curr_val = equity_curve[i]["portfolio_value"]
        regime = equity_curve[i].get("regime", "unknown")

        if prev_val > 0:
            ret = (curr_val - prev_val) / prev_val
            regime_returns[regime].append(ret)

    regimes = {}
    for regime, rets in regime_returns.items():
        n = len(rets)
        if n == 0:
            continue
        mean_r = sum(rets) / n
        var_r = sum((r - mean_r) ** 2 for r in rets) / max(n - 1, 1)
        std_r = math.sqrt(var_r)
        ann_ret = mean_r * 252
        ann_vol = std_r * math.sqrt(252)
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
        win_rate = sum(1 for r in rets if r > 0) / n

        regimes[regime] = {
            "periods": n,
            "annualized_return": round(ann_ret, 4),
            "annualized_volatility": round(ann_vol, 4),
            "sharpe_ratio": round(sharpe, 4),
            "win_rate": round(win_rate, 4),
            "worst_day": round(min(rets), 6),
            "best_day": round(max(rets), 6),
        }

    sorted_regimes = sorted(regimes.items(), key=lambda x: x[1]["annualized_return"], reverse=True)

    return {
        "regimes": regimes,
        "best_regime": sorted_regimes[0][0] if sorted_regimes else None,
        "worst_regime": sorted_regimes[-1][0] if sorted_regimes else None,
        "regime_count": len(regimes),
    }


def _empty_metrics() -> dict:
    return {
        "total_return": 0.0, "cagr": 0.0, "annualized_return": 0.0,
        "annualized_volatility": 0.0, "sharpe_ratio": 0.0, "sortino_ratio": 0.0,
        "max_drawdown": 0.0, "max_dd_duration_days": 0, "max_drawdown_period": [0, 0],
        "calmar_ratio": 0.0, "win_rate": 0.0, "avg_win_loss_ratio": 0.0,
        "profit_factor": 0.0, "total_periods": 0,
    }
