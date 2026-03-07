"""
src/engines/strategy/composer.py
─────────────────────────────────────────────────────────────────────────────
StrategyComposer — combine signals, scoring, and portfolio rules into
executable strategy instances.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("365advisers.strategy.composer")


class StrategyComposer:
    """Compose a strategy from signals + scoring + portfolio rules."""

    @staticmethod
    def compose(
        strategy_config: dict[str, Any],
        available_signals: list[dict],
        ticker_scores: dict[str, float] | None = None,
    ) -> dict:
        """Compose a strategy instance from config and market data.

        Args:
            strategy_config: StrategyConfig dict (signal_filters, score_filters, portfolio_rules)
            available_signals: Active signals [{signal_id, ticker, strength, confidence, category}]
            ticker_scores: Optional {ticker: composite_score}

        Returns:
            Composed strategy with eligible tickers and position suggestions.
        """
        signal_filters = strategy_config.get("signal_filters", {})
        score_filters = strategy_config.get("score_filters", {})
        portfolio_rules = strategy_config.get("portfolio_rules", {})

        # Step 1: Filter signals
        filtered_signals = _apply_signal_filters(available_signals, signal_filters)

        # Step 2: Group by ticker
        ticker_signals: dict[str, list] = {}
        for sig in filtered_signals:
            t = sig.get("ticker", "")
            ticker_signals.setdefault(t, []).append(sig)

        # Step 3: Score filtering
        eligible_tickers = _apply_score_filters(
            list(ticker_signals.keys()), ticker_scores or {}, score_filters
        )

        # Step 4: Build position targets
        max_positions = portfolio_rules.get("max_positions", 20)
        sizing_method = portfolio_rules.get("sizing_method", "equal")
        max_single = portfolio_rules.get("max_single_position", 0.10)

        # Rank by signal strength
        ranked = []
        for ticker in eligible_tickers:
            sigs = ticker_signals.get(ticker, [])
            avg_conf = sum(s.get("confidence", 0) for s in sigs) / max(len(sigs), 1)
            strong_count = sum(1 for s in sigs if s.get("strength") == "strong")
            score = (ticker_scores or {}).get(ticker, 0.0)
            rank_score = avg_conf * 0.4 + (strong_count / max(len(sigs), 1)) * 0.3 + score / 10 * 0.3
            ranked.append((ticker, rank_score, sigs))

        ranked.sort(key=lambda x: x[1], reverse=True)
        selected = ranked[:max_positions]

        # Step 5: Size positions
        positions = []
        n = len(selected)
        for ticker, rank_score, sigs in selected:
            if sizing_method == "equal":
                weight = min(1.0 / max(n, 1), max_single)
            elif sizing_method == "rank_weighted":
                total_rank = sum(r[1] for r in selected)
                weight = min(rank_score / max(total_rank, 0.01), max_single)
            else:
                weight = min(1.0 / max(n, 1), max_single)

            positions.append({
                "ticker": ticker,
                "weight": round(weight, 4),
                "rank_score": round(rank_score, 4),
                "signal_count": len(sigs),
                "strong_signals": sum(1 for s in sigs if s.get("strength") == "strong"),
                "avg_confidence": round(sum(s.get("confidence", 0) for s in sigs) / max(len(sigs), 1), 4),
            })

        return {
            "total_signals": len(available_signals),
            "filtered_signals": len(filtered_signals),
            "eligible_tickers": len(eligible_tickers),
            "selected_positions": len(positions),
            "sizing_method": sizing_method,
            "positions": positions,
        }


def _apply_signal_filters(signals: list[dict], filters: dict) -> list[dict]:
    """Filter signals by category, strength, confidence."""
    result = signals
    required_cats = filters.get("required_categories", [])
    if required_cats:
        result = [s for s in result if s.get("category") in required_cats]

    min_strength = filters.get("min_signal_strength", 0.0)
    if min_strength > 0:
        strength_map = {"strong": 3, "moderate": 2, "weak": 1}
        result = [s for s in result if strength_map.get(s.get("strength", "weak"), 0) >= min_strength]

    min_conf = filters.get("min_confidence", "low")
    conf_map = {"low": 0.0, "medium": 0.3, "high": 0.6}
    min_val = conf_map.get(min_conf, 0.0)
    result = [s for s in result if s.get("confidence", 0.0) >= min_val]

    return result


def _apply_score_filters(tickers: list[str], scores: dict[str, float], filters: dict) -> list[str]:
    """Filter tickers by score thresholds."""
    min_uos = filters.get("min_uos", 0.0)
    min_bq = filters.get("min_business_quality", 0.0)
    min_case = filters.get("min_case_score", 0)

    if not scores or (min_uos <= 0 and min_bq <= 0 and min_case <= 0):
        return tickers

    return [t for t in tickers if scores.get(t, 0.0) >= min_uos]
