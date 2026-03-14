"""
src/services/cost_tracker.py
─────────────────────────────────────────────────────────────────────────────
LLM Cost Budgeting — tracks cumulative costs per day/session with
configurable daily budget, alert thresholds, and auto-downgrade.

Architecture:
  - In-memory tracking per model per day
  - Configurable daily budget via DAILY_LLM_BUDGET_USD env var
  - Alert at 80% of budget, auto-downgrade at 100%
  - GET /api/costs exposes real-time cost data
"""

from __future__ import annotations

import time
import logging
from collections import defaultdict
from datetime import datetime, timezone, date
from typing import Any

logger = logging.getLogger("365advisers.costs")

# ── Cost Configuration ────────────────────────────────────────────────────────

# Gemini pricing (per 1K tokens, USD) — 2026-Q1
MODEL_PRICING = {
    "gemini-2.5-flash": {"input": 0.00015, "output": 0.0006},
    "gemini-2.5-pro":   {"input": 0.00125, "output": 0.005},
}

# Budget defaults (override via env)
DEFAULT_DAILY_BUDGET_USD = 5.00
ALERT_THRESHOLD_PCT = 0.80  # Alert at 80% of budget


# ── Cost State ────────────────────────────────────────────────────────────────

class _CostState:
    """Singleton cost tracker state."""
    def __init__(self):
        self.daily_costs: dict[str, dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )  # {date_str: {model: cumulative_cost}}
        self.call_count: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )  # {date_str: {model: count}}
        self.total_tokens: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )  # {date_str: {model: tokens}}
        self.alerts: list[dict] = []
        self._budget_exceeded = False

    def reset(self):
        self.daily_costs.clear()
        self.call_count.clear()
        self.total_tokens.clear()
        self.alerts.clear()
        self._budget_exceeded = False


_state = _CostState()


def _today() -> str:
    return date.today().isoformat()


def _get_budget() -> float:
    try:
        import os
        return float(os.getenv("DAILY_LLM_BUDGET_USD", str(DEFAULT_DAILY_BUDGET_USD)))
    except (ValueError, TypeError):
        return DEFAULT_DAILY_BUDGET_USD


# ── Public API ────────────────────────────────────────────────────────────────

def record_llm_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> dict[str, Any]:
    """
    Record an LLM call's cost.

    Returns budget status after recording.
    """
    today = _today()

    _state.daily_costs[today][model] += cost_usd
    _state.call_count[today][model] += 1
    _state.total_tokens[today][model] += input_tokens + output_tokens

    # Check budget
    total_today = sum(_state.daily_costs[today].values())
    budget = _get_budget()
    usage_pct = (total_today / budget * 100) if budget > 0 else 0

    status = {
        "total_today_usd": round(total_today, 6),
        "budget_usd": budget,
        "usage_pct": round(usage_pct, 1),
        "budget_exceeded": total_today >= budget,
    }

    # Alert at threshold
    if usage_pct >= ALERT_THRESHOLD_PCT * 100 and not _state._budget_exceeded:
        alert = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "budget_warning",
            "message": f"LLM costs at {usage_pct:.0f}% of daily budget (${total_today:.4f}/${budget:.2f})",
            "action": "Consider downgrading to Flash model",
        }
        _state.alerts.append(alert)
        logger.warning(alert["message"])

    if total_today >= budget:
        _state._budget_exceeded = True
        logger.error(f"LLM daily budget EXCEEDED: ${total_today:.4f} >= ${budget:.2f}")

    return status


def should_downgrade_model() -> bool:
    """
    Check if the model should be downgraded to save costs.

    Returns True if daily budget has been exceeded.
    """
    today = _today()
    total = sum(_state.daily_costs[today].values())
    return total >= _get_budget()


def get_recommended_model(preferred: str = "gemini-2.5-pro") -> str:
    """
    Get the recommended model based on budget status.

    If budget exceeded, downgrades Pro → Flash.
    """
    if should_downgrade_model() and preferred == "gemini-2.5-pro":
        logger.info("Auto-downgrading to gemini-2.5-flash (budget exceeded)")
        return "gemini-2.5-flash"
    return preferred


def get_cost_report() -> dict:
    """Generate a comprehensive cost report."""
    today = _today()
    budget = _get_budget()

    daily_total = sum(_state.daily_costs[today].values())
    daily_calls = sum(_state.call_count[today].values())
    daily_tokens = sum(_state.total_tokens[today].values())

    model_breakdown = {}
    for model in set(list(_state.daily_costs[today].keys())):
        model_breakdown[model] = {
            "cost_usd": round(_state.daily_costs[today][model], 6),
            "calls": _state.call_count[today][model],
            "tokens": _state.total_tokens[today][model],
            "avg_cost_per_call": round(
                _state.daily_costs[today][model] / max(1, _state.call_count[today][model]),
                6,
            ),
        }

    return {
        "date": today,
        "budget": {
            "daily_limit_usd": budget,
            "spent_usd": round(daily_total, 6),
            "remaining_usd": round(max(0, budget - daily_total), 6),
            "usage_pct": round(daily_total / budget * 100, 1) if budget > 0 else 0,
            "exceeded": daily_total >= budget,
        },
        "summary": {
            "total_calls": daily_calls,
            "total_tokens": daily_tokens,
            "total_cost_usd": round(daily_total, 6),
        },
        "by_model": model_breakdown,
        "recent_alerts": _state.alerts[-5:],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def reset_tracker():
    """Reset cost tracker (for testing)."""
    _state.reset()
