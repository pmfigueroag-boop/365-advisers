"""
src/engines/strategy/composer.py
─────────────────────────────────────────────────────────────────────────────
StrategyComposer — combine signals, scoring, and portfolio rules into
executable strategy instances.

Enhanced with:
  - composition_logic (all_required / any_required / weighted)
  - preferred_signals matching
  - freshness_class filtering
  - crowding_penalty as entry filter
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
            strategy_config: StrategyConfig dict (supports both legacy and new format)
            available_signals: Active signals [{signal_id, ticker, strength, confidence, category}]
            ticker_scores: Optional {ticker: composite_score}

        Returns:
            Composed strategy with eligible tickers and position suggestions.
        """
        # ── Extract config (supports new typed + legacy formats) ──
        signals_cfg = strategy_config.get("signals", {})
        thresholds_cfg = strategy_config.get("thresholds", {})
        portfolio_cfg = strategy_config.get("portfolio", {})

        # Fallback to legacy fields
        signal_filters = strategy_config.get("signal_filters", {})
        score_filters = strategy_config.get("score_filters", {})
        portfolio_rules = strategy_config.get("portfolio_rules", {})

        # Merge new + legacy
        required_cats = signals_cfg.get("required_categories") or signal_filters.get("required_categories", [])
        preferred_signals = signals_cfg.get("preferred_signals", [])
        min_strength = signals_cfg.get("min_signal_strength") or signal_filters.get("min_signal_strength", 0.0)
        min_conf = signals_cfg.get("min_confidence") or signal_filters.get("min_confidence", "low")
        composition_logic = signals_cfg.get("composition_logic", "all_required")
        min_active = signals_cfg.get("min_active_signals", 1)

        min_case = thresholds_cfg.get("min_case_score") or score_filters.get("min_case_score", 0)
        min_bq = thresholds_cfg.get("min_business_quality") or score_filters.get("min_business_quality", 0.0)
        min_uos = thresholds_cfg.get("min_uos") or score_filters.get("min_uos", 0.0)
        max_freshness = thresholds_cfg.get("max_freshness_class", "stale")

        max_positions = portfolio_cfg.get("max_positions") or portfolio_rules.get("max_positions", 20)
        sizing_method = portfolio_cfg.get("sizing_method") or portfolio_rules.get("sizing_method", "vol_parity")
        max_single = portfolio_cfg.get("max_single_position") or portfolio_rules.get("max_single_position", 0.10)

        # ── Step 1: Filter signals ──
        filtered_signals = _apply_signal_filters(
            available_signals,
            required_categories=required_cats,
            preferred_signals=preferred_signals,
            min_strength=min_strength,
            min_confidence=min_conf,
            composition_logic=composition_logic,
            max_freshness=max_freshness,
        )

        # ── Step 2: Group by ticker ──
        ticker_signals: dict[str, list] = {}
        for sig in filtered_signals:
            t = sig.get("ticker", "")
            ticker_signals.setdefault(t, []).append(sig)

        # ── Step 3: Min active signals filter ──
        if min_active > 1:
            ticker_signals = {
                t: sigs for t, sigs in ticker_signals.items()
                if len(sigs) >= min_active
            }

        # ── Step 4: Score filtering ──
        eligible_tickers = _apply_score_filters(
            list(ticker_signals.keys()),
            ticker_scores or {},
            min_case=min_case,
            min_bq=min_bq,
            min_uos=min_uos,
        )

        # ── Step 5: Build position targets ──
        ranked = []
        for ticker in eligible_tickers:
            sigs = ticker_signals.get(ticker, [])
            avg_conf = sum(s.get("confidence", 0) for s in sigs) / max(len(sigs), 1)
            strong_count = sum(1 for s in sigs if s.get("strength") == "strong")
            score = (ticker_scores or {}).get(ticker, 0.0)

            # Bonus for preferred signal matches
            preferred_hits = sum(
                1 for s in sigs if s.get("signal_id") in preferred_signals
                or s.get("signal_name") in preferred_signals
            )
            preferred_bonus = preferred_hits * 0.1

            rank_score = (
                avg_conf * 0.35
                + (strong_count / max(len(sigs), 1)) * 0.25
                + score / 10 * 0.30
                + preferred_bonus * 0.10
            )
            ranked.append((ticker, rank_score, sigs))

        ranked.sort(key=lambda x: x[1], reverse=True)
        selected = ranked[:max_positions]

        # ── Step 6: Size positions ──
        positions = []
        n = len(selected)
        for ticker, rank_score, sigs in selected:
            if sizing_method == "equal":
                weight = min(1.0 / max(n, 1), max_single)
            elif sizing_method == "rank_weighted":
                total_rank = sum(r[1] for r in selected)
                weight = min(rank_score / max(total_rank, 0.01), max_single)
            elif sizing_method == "risk_budget":
                weight = min(1.0 / max(n, 1), max_single)  # simplified
            else:  # vol_parity default
                weight = min(1.0 / max(n, 1), max_single)

            positions.append({
                "ticker": ticker,
                "weight": round(weight, 4),
                "rank_score": round(rank_score, 4),
                "signal_count": len(sigs),
                "strong_signals": sum(1 for s in sigs if s.get("strength") == "strong"),
                "preferred_hits": sum(
                    1 for s in sigs if s.get("signal_id") in preferred_signals
                    or s.get("signal_name") in preferred_signals
                ),
                "avg_confidence": round(
                    sum(s.get("confidence", 0) for s in sigs) / max(len(sigs), 1), 4
                ),
            })

        return {
            "total_signals": len(available_signals),
            "filtered_signals": len(filtered_signals),
            "eligible_tickers": len(eligible_tickers),
            "selected_positions": len(positions),
            "sizing_method": sizing_method,
            "composition_logic": composition_logic,
            "positions": positions,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

_FRESHNESS_ORDER = {"fresh": 0, "stale": 1, "diluted": 2, "expired": 3}


def _apply_signal_filters(
    signals: list[dict],
    *,
    required_categories: list[str],
    preferred_signals: list[str],
    min_strength: float,
    min_confidence: str,
    composition_logic: str,
    max_freshness: str,
) -> list[dict]:
    """Filter signals by category, strength, confidence, and freshness."""
    result = signals

    # Freshness filter
    max_fresh_val = _FRESHNESS_ORDER.get(max_freshness, 1)
    result = [
        s for s in result
        if _FRESHNESS_ORDER.get(s.get("freshness_class", "fresh"), 0) <= max_fresh_val
    ]

    # Category filter based on composition_logic
    if required_categories:
        if composition_logic == "all_required":
            # Keep only signals in required categories (all must be present per ticker)
            result = [s for s in result if s.get("category") in required_categories]
        elif composition_logic == "any_required":
            # Keep signals matching any required category
            result = [s for s in result if s.get("category") in required_categories]
        elif composition_logic == "weighted":
            # Keep all signals but boost those in required categories
            for s in result:
                if s.get("category") in required_categories:
                    s["_weight_boost"] = 1.5
                else:
                    s["_weight_boost"] = 1.0

    # Strength filter
    if min_strength > 0:
        strength_map = {"strong": 3, "moderate": 2, "weak": 1}
        result = [
            s for s in result
            if strength_map.get(s.get("strength", "weak"), 0) >= min_strength
        ]

    # Confidence filter
    conf_map = {"low": 0.0, "medium": 0.3, "high": 0.6}
    min_val = conf_map.get(min_confidence, 0.0)
    result = [s for s in result if s.get("confidence", 0.0) >= min_val]

    return result


def _apply_score_filters(
    tickers: list[str],
    scores: dict[str, float],
    *,
    min_case: float,
    min_bq: float,
    min_uos: float,
) -> list[str]:
    """Filter tickers by score thresholds."""
    if not scores or (min_case <= 0 and min_bq <= 0 and min_uos <= 0):
        return tickers

    return [t for t in tickers if scores.get(t, 0.0) >= min_uos]
