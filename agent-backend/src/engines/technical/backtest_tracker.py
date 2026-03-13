"""
src/engines/technical/backtest_tracker.py
──────────────────────────────────────────────────────────────────────────────
Backtest Tracker — computes forward returns and hit rates from logged signals.

Takes signal history + OHLCV data to compute empirical validation metrics:
  - Forward returns at 1d/5d/20d
  - Hit rate by signal type
  - Best setup_quality threshold
  - Sharpe proxy
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import logging
from datetime import datetime

from src.engines.technical.signal_logger import SignalRecord

logger = logging.getLogger("365advisers.engines.technical.backtest")


@dataclass
class ForwardReturns:
    """Forward returns after a signal emission."""
    ticker: str
    signal_date: str
    signal: str
    score: float
    setup_quality: float
    price_at_signal: float
    return_1d: float | None = None    # % return
    return_5d: float | None = None
    return_20d: float | None = None
    hit_1d: bool | None = None         # True if return direction matches signal
    hit_5d: bool | None = None
    hit_20d: bool | None = None


@dataclass
class BacktestSummary:
    """Aggregate backtesting statistics."""
    total_signals: int = 0
    buy_signals: int = 0
    sell_signals: int = 0
    hit_rate_5d: float = 0.0           # % of signals where direction matched
    hit_rate_20d: float = 0.0
    avg_return_5d: float = 0.0         # average % return
    avg_return_20d: float = 0.0
    sharpe_proxy_20d: float = 0.0      # mean/std of 20d returns
    best_quality_threshold: float = 0.5  # setup_quality threshold with best hit rate
    signals_with_returns: list[ForwardReturns] = field(default_factory=list)


def compute_forward_returns(
    record: SignalRecord,
    future_ohlcv: list[dict],
) -> ForwardReturns:
    """
    Compute forward returns from a signal record + future price data.

    Args:
        record: The signal record to evaluate.
        future_ohlcv: OHLCV data AFTER the signal date (index 0 = next day).

    Returns:
        ForwardReturns with 1d/5d/20d returns and hit flags.
    """
    price = record.price_at_signal
    is_buy = record.signal in ("STRONG_BUY", "BUY")
    is_sell = record.signal in ("STRONG_SELL", "SELL")

    def _return_at(days: int) -> tuple[float | None, bool | None]:
        if days > len(future_ohlcv) or price <= 0:
            return None, None
        close = future_ohlcv[days - 1].get("close", 0) if days <= len(future_ohlcv) else None
        if close is None or close <= 0:
            return None, None
        ret = ((close - price) / price) * 100
        hit = None
        if is_buy:
            hit = ret > 0
        elif is_sell:
            hit = ret < 0
        return round(ret, 2), hit

    r1d, h1d = _return_at(1)
    r5d, h5d = _return_at(5)
    r20d, h20d = _return_at(20)

    return ForwardReturns(
        ticker=record.ticker,
        signal_date=record.timestamp,
        signal=record.signal,
        score=record.score,
        setup_quality=record.setup_quality,
        price_at_signal=price,
        return_1d=r1d, return_5d=r5d, return_20d=r20d,
        hit_1d=h1d, hit_5d=h5d, hit_20d=h20d,
    )


def compute_backtest_summary(
    signals_with_returns: list[ForwardReturns],
) -> BacktestSummary:
    """
    Compute aggregate backtesting statistics from a list of forward returns.
    """
    if not signals_with_returns:
        return BacktestSummary()

    total = len(signals_with_returns)
    buy_count = sum(1 for s in signals_with_returns if s.signal in ("STRONG_BUY", "BUY"))
    sell_count = sum(1 for s in signals_with_returns if s.signal in ("STRONG_SELL", "SELL"))

    # Hit rates
    hits_5d = [s.hit_5d for s in signals_with_returns if s.hit_5d is not None]
    hits_20d = [s.hit_20d for s in signals_with_returns if s.hit_20d is not None]

    hit_rate_5d = sum(1 for h in hits_5d if h) / len(hits_5d) if hits_5d else 0.0
    hit_rate_20d = sum(1 for h in hits_20d if h) / len(hits_20d) if hits_20d else 0.0

    # Average returns
    returns_5d = [s.return_5d for s in signals_with_returns if s.return_5d is not None]
    returns_20d = [s.return_20d for s in signals_with_returns if s.return_20d is not None]

    avg_5d = sum(returns_5d) / len(returns_5d) if returns_5d else 0.0
    avg_20d = sum(returns_20d) / len(returns_20d) if returns_20d else 0.0

    # Sharpe proxy: mean/std of directional returns
    sharpe = 0.0
    if len(returns_20d) >= 3:
        mean = avg_20d
        std = math.sqrt(sum((r - mean) ** 2 for r in returns_20d) / len(returns_20d))
        if std > 0:
            sharpe = round(mean / std, 2)

    # Best quality threshold: scan 0.3–0.9 and find threshold with best 20d hit rate
    best_threshold = 0.5
    best_hr = 0.0
    for thresh in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        filtered = [
            s for s in signals_with_returns
            if s.setup_quality >= thresh and s.hit_20d is not None
        ]
        if len(filtered) >= 3:
            hr = sum(1 for s in filtered if s.hit_20d) / len(filtered)
            if hr > best_hr:
                best_hr = hr
                best_threshold = thresh

    return BacktestSummary(
        total_signals=total,
        buy_signals=buy_count,
        sell_signals=sell_count,
        hit_rate_5d=round(hit_rate_5d, 3),
        hit_rate_20d=round(hit_rate_20d, 3),
        avg_return_5d=round(avg_5d, 2),
        avg_return_20d=round(avg_20d, 2),
        sharpe_proxy_20d=sharpe,
        best_quality_threshold=best_threshold,
        signals_with_returns=signals_with_returns,
    )
