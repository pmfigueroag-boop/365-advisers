"""
src/engines/backtesting/metrics.py
──────────────────────────────────────────────────────────────────────────────
Statistical metrics calculator for backtesting results.

Core metrics: Hit Rate, Average Return, Sharpe, Sortino, Max Drawdown,
Empirical Half-Life, Alpha Decay Curve, Statistical Confidence.
"""

from __future__ import annotations

import math
import logging
from statistics import median

from src.engines.backtesting.models import SignalEvent

logger = logging.getLogger("365advisers.backtesting.metrics")


# ─── Annualisation constant ──────────────────────────────────────────────────
_TRADING_DAYS_YEAR = 252


def compute_hit_rate(
    events: list[SignalEvent],
    windows: list[int],
) -> dict[int, float]:
    """Fraction of events with positive forward return per window."""
    result: dict[int, float] = {}
    for w in windows:
        returns = [e.forward_returns[w] for e in events if w in e.forward_returns]
        if returns:
            hits = sum(1 for r in returns if r > 0)
            result[w] = round(hits / len(returns), 4)
        else:
            result[w] = 0.0
    return result


def compute_avg_return(
    events: list[SignalEvent],
    windows: list[int],
) -> dict[int, float]:
    """Arithmetic mean of forward returns per window."""
    result: dict[int, float] = {}
    for w in windows:
        returns = [e.forward_returns[w] for e in events if w in e.forward_returns]
        if returns:
            result[w] = round(sum(returns) / len(returns), 6)
        else:
            result[w] = 0.0
    return result


def compute_avg_excess_return(
    events: list[SignalEvent],
    windows: list[int],
) -> dict[int, float]:
    """Mean of excess returns (signal − benchmark) per window."""
    result: dict[int, float] = {}
    for w in windows:
        returns = [e.excess_returns[w] for e in events if w in e.excess_returns]
        if returns:
            result[w] = round(sum(returns) / len(returns), 6)
        else:
            result[w] = 0.0
    return result


def compute_median_return(
    events: list[SignalEvent],
    windows: list[int],
) -> dict[int, float]:
    """Median of forward returns per window."""
    result: dict[int, float] = {}
    for w in windows:
        returns = [e.forward_returns[w] for e in events if w in e.forward_returns]
        if returns:
            result[w] = round(median(returns), 6)
        else:
            result[w] = 0.0
    return result


def compute_sharpe(
    events: list[SignalEvent],
    windows: list[int],
) -> dict[int, float]:
    """Annualised Sharpe ratio on excess returns per window."""
    result: dict[int, float] = {}
    for w in windows:
        returns = [e.excess_returns.get(w, e.forward_returns.get(w, 0.0)) for e in events
                   if w in e.forward_returns]
        if len(returns) < 2:
            result[w] = 0.0
            continue
        mean_r = sum(returns) / len(returns)
        var_r = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std_r = math.sqrt(var_r) if var_r > 0 else 0.0
        if std_r > 0:
            annualisation = math.sqrt(_TRADING_DAYS_YEAR / max(w, 1))
            result[w] = round((mean_r / std_r) * annualisation, 4)
        else:
            result[w] = 0.0
    return result


def compute_sortino(
    events: list[SignalEvent],
    windows: list[int],
) -> dict[int, float]:
    """Annualised Sortino ratio (downside-only risk) per window."""
    result: dict[int, float] = {}
    for w in windows:
        returns = [e.excess_returns.get(w, e.forward_returns.get(w, 0.0)) for e in events
                   if w in e.forward_returns]
        if len(returns) < 2:
            result[w] = 0.0
            continue
        mean_r = sum(returns) / len(returns)
        neg_returns = [r for r in returns if r < 0]
        if not neg_returns:
            result[w] = round(10.0, 4)  # All positive → capped high value
            continue
        downside_var = sum(r ** 2 for r in neg_returns) / len(neg_returns)
        downside_std = math.sqrt(downside_var)
        if downside_std > 0:
            annualisation = math.sqrt(_TRADING_DAYS_YEAR / max(w, 1))
            result[w] = round((mean_r / downside_std) * annualisation, 4)
        else:
            result[w] = 0.0
    return result


def compute_max_drawdown(events: list[SignalEvent]) -> float:
    """
    Max drawdown from a cumulative equity curve of signal returns.

    Uses T+20 returns sorted chronologically.
    """
    sorted_events = sorted(events, key=lambda e: e.fired_date)
    returns = [e.forward_returns.get(20, e.forward_returns.get(10, 0.0))
               for e in sorted_events]

    if not returns:
        return 0.0

    # Build cumulative equity
    equity = 1.0
    peak = 1.0
    max_dd = 0.0

    for r in returns:
        equity *= (1 + r)
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, drawdown)

    return round(max_dd, 6)


def compute_alpha_decay_curve(
    events: list[SignalEvent],
    max_days: int = 60,
) -> list[float]:
    """
    Average daily excess return curve from T+1 to T+max_days.

    This requires forward_returns to include keys 1..max_days,
    but typically we only have the configured windows. We interpolate
    from the available windows.
    """
    if not events:
        return [0.0] * max_days

    # Collect available windows and their average excess returns
    windows_available: dict[int, list[float]] = {}
    for e in events:
        for w, ret in e.excess_returns.items():
            windows_available.setdefault(w, []).append(ret)

    # Average excess return per available window
    avg_by_window: dict[int, float] = {}
    for w, vals in windows_available.items():
        avg_by_window[w] = sum(vals) / len(vals) if vals else 0.0

    if not avg_by_window:
        return [0.0] * max_days

    # Linear interpolation between known points
    sorted_windows = sorted(avg_by_window.keys())
    curve: list[float] = []

    for day in range(1, max_days + 1):
        # Find surrounding known points
        lower = max((w for w in sorted_windows if w <= day), default=sorted_windows[0])
        upper = min((w for w in sorted_windows if w >= day), default=sorted_windows[-1])

        if lower == upper:
            curve.append(round(avg_by_window.get(lower, 0.0), 6))
        elif lower in avg_by_window and upper in avg_by_window:
            # Linear interpolation
            frac = (day - lower) / (upper - lower) if upper != lower else 0
            val = avg_by_window[lower] + frac * (avg_by_window[upper] - avg_by_window[lower])
            curve.append(round(val, 6))
        else:
            curve.append(0.0)

    return curve


def compute_empirical_half_life(decay_curve: list[float]) -> float | None:
    """
    Find the day at which the avg excess return decays to 50% of day-1 value.

    Returns None if the curve is flat, negative, or never decays that far.
    """
    if not decay_curve or len(decay_curve) < 2:
        return None

    initial = decay_curve[0]
    if initial <= 0:
        return None

    half = initial / 2.0

    for day_idx, val in enumerate(decay_curve[1:], start=2):
        if val <= half:
            return float(day_idx)

    # Never decayed to 50% within the curve window
    return None


def compute_t_statistic(
    events: list[SignalEvent],
    windows: list[int],
) -> tuple[dict[int, float], dict[int, float]]:
    """
    One-sample t-test: H0: mean excess return = 0.

    Returns (t_statistics, p_values) per window.
    """
    t_stats: dict[int, float] = {}
    p_vals: dict[int, float] = {}

    for w in windows:
        returns = [e.excess_returns.get(w, 0.0) for e in events if w in e.excess_returns]
        n = len(returns)

        if n < 3:
            t_stats[w] = 0.0
            p_vals[w] = 1.0
            continue

        mean_r = sum(returns) / n
        var_r = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
        se = math.sqrt(var_r / n) if var_r > 0 else 0.0

        if se > 0:
            t = mean_r / se
            t_stats[w] = round(t, 4)
            # Approximate p-value using normal distribution for large n
            # For small n this is an approximation; scipy would be more precise
            p = 2 * (1 - _normal_cdf(abs(t)))
            p_vals[w] = round(max(p, 1e-10), 6)
        else:
            t_stats[w] = 0.0
            p_vals[w] = 1.0

    return t_stats, p_vals


def classify_confidence(
    p_values: dict[int, float],
    sample_size: int,
) -> str:
    """
    Classify statistical confidence level.

    - HIGH: p < 0.01 AND n >= 100
    - MEDIUM: p < 0.05 AND n >= 50
    - LOW: otherwise
    """
    if not p_values:
        return "LOW"

    # Use the best (lowest) p-value across windows
    min_p = min(p_values.values())

    if min_p < 0.01 and sample_size >= 100:
        return "HIGH"
    elif min_p < 0.05 and sample_size >= 50:
        return "MEDIUM"
    return "LOW"


def find_optimal_hold_period(sharpe_ratios: dict[int, float]) -> int | None:
    """Find the forward window with the highest Sharpe ratio."""
    if not sharpe_ratios:
        return None
    best_window = max(sharpe_ratios, key=sharpe_ratios.get)  # type: ignore
    return best_window if sharpe_ratios[best_window] > 0 else None


# ─── Normal CDF approximation ───────────────────────────────────────────────

def _normal_cdf(x: float) -> float:
    """
    Approximate standard normal CDF using the Horner form of the
    rational approximation (Abramowitz & Stegun 26.2.17).
    """
    if x < -8.0:
        return 0.0
    if x > 8.0:
        return 1.0

    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = 1
    if x < 0:
        sign = -1
    x = abs(x) / math.sqrt(2)

    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)

    return 0.5 * (1.0 + sign * y)
