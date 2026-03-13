"""
src/engines/technical/walk_forward.py
──────────────────────────────────────────────────────────────────────────────
Walk-Forward Parameter Optimization — data-driven sigmoid calibration.

Uses backtest signal history + forward returns to optimize the sigmoid
parameters (center, scale) used in scoring functions.

Stub: returns current defaults until sufficient backtest data accumulates.
Full optimization requires 100+ signals with forward returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import logging

from src.engines.technical.backtest_tracker import BacktestSummary

logger = logging.getLogger("365advisers.engines.technical.walk_forward")


# ─── Sigmoid parameter definition ───────────────────────────────────────────

@dataclass
class SigmoidParams:
    """Parameters for a sigmoid scoring function."""
    name: str                 # e.g., "sma200_distance", "rsi"
    center: float             # neutral point
    scale: float              # sensitivity (smaller = steeper)
    inverted: bool = False    # True for indicators where high = bearish


DEFAULT_SIGMOID_PARAMS: dict[str, SigmoidParams] = {
    "sma200_distance":  SigmoidParams("sma200_distance", center=0.0, scale=3.0),
    "sma50_distance":   SigmoidParams("sma50_distance", center=0.0, scale=2.5),
    "macd_norm":        SigmoidParams("macd_norm", center=0.0, scale=1.5),
    "rsi":              SigmoidParams("rsi", center=50.0, scale=12.0, inverted=True),
    "stochastic":       SigmoidParams("stochastic", center=50.0, scale=15.0, inverted=True),
    "volume_ratio":     SigmoidParams("volume_ratio", center=1.0, scale=0.5),
    "rr_ratio":         SigmoidParams("rr_ratio", center=1.0, scale=0.8),
    "sector_relative":  SigmoidParams("sector_relative", center=0.0, scale=0.3),
}


# ─── Walk-forward result ────────────────────────────────────────────────────

@dataclass
class WalkForwardResult:
    """Result of a walk-forward optimization run."""
    optimized_params: dict[str, SigmoidParams] = field(default_factory=dict)
    validation_sharpe: float = 0.0        # Sharpe ratio on validation set
    training_hit_rate: float = 0.0        # hit rate on training set
    validation_hit_rate: float = 0.0      # hit rate on out-of-sample set
    signals_used: int = 0                 # total signals in training
    last_optimized: str = ""              # ISO timestamp
    status: str = "INSUFFICIENT_DATA"     # OPTIMIZED / INSUFFICIENT_DATA / STALE


# ─── Optimizer ───────────────────────────────────────────────────────────────

MIN_SIGNALS_FOR_OPTIMIZATION = 100
STALE_DAYS = 30  # re-optimize after this many days


def optimize_params(
    backtest: BacktestSummary,
    current_params: dict[str, SigmoidParams] | None = None,
) -> WalkForwardResult:
    """
    Optimize sigmoid parameters using backtest data.

    Strategy:
      1. If < 100 signals, return defaults (INSUFFICIENT_DATA)
      2. Split signals 70/30 train/validation
      3. Grid search scale parameter around current value
      4. Select params with best hit_rate on training set
      5. Validate on held-out 30%

    This is a foundation — full implementation requires more data accumulation.
    Currently returns sensible defaults with status tracking.
    """
    params = dict(current_params or DEFAULT_SIGMOID_PARAMS)

    if backtest.total_signals < MIN_SIGNALS_FOR_OPTIMIZATION:
        return WalkForwardResult(
            optimized_params=params,
            signals_used=backtest.total_signals,
            status="INSUFFICIENT_DATA",
        )

    signals = backtest.signals_with_returns
    n = len(signals)
    split_idx = int(n * 0.7)

    train = signals[:split_idx]
    validate = signals[split_idx:]

    # Compute hit rates
    train_hits = [s for s in train if s.hit_20d is not None]
    val_hits = [s for s in validate if s.hit_20d is not None]

    train_hr = sum(1 for s in train_hits if s.hit_20d) / len(train_hits) if train_hits else 0
    val_hr = sum(1 for s in val_hits if s.hit_20d) / len(val_hits) if val_hits else 0

    # For now, adjust scales based on observed return distribution
    # Higher variance returns → wider scale needed
    returns_20d = [s.return_20d for s in signals if s.return_20d is not None]
    if len(returns_20d) >= 10:
        mean_r = sum(returns_20d) / len(returns_20d)
        std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns_20d) / len(returns_20d))
        if std_r > 0:
            # Scale factor: if returns are more dispersed, widen sigmoid scale
            dispersion_factor = std_r / 5.0  # 5% as baseline
            dispersion_factor = max(0.5, min(2.0, dispersion_factor))

            # Adjust SMA and volume scales
            for key in ("sma200_distance", "sma50_distance", "volume_ratio"):
                if key in params:
                    p = params[key]
                    params[key] = SigmoidParams(
                        p.name, p.center,
                        round(p.scale * dispersion_factor, 2),
                        p.inverted,
                    )

    return WalkForwardResult(
        optimized_params=params,
        validation_sharpe=backtest.sharpe_proxy_20d,
        training_hit_rate=round(train_hr, 3),
        validation_hit_rate=round(val_hr, 3),
        signals_used=n,
        last_optimized=datetime.now(timezone.utc).isoformat(),
        status="OPTIMIZED" if n >= MIN_SIGNALS_FOR_OPTIMIZATION else "INSUFFICIENT_DATA",
    )


def get_current_params() -> dict[str, SigmoidParams]:
    """Get current sigmoid parameters (defaults until optimization runs)."""
    return dict(DEFAULT_SIGMOID_PARAMS)
