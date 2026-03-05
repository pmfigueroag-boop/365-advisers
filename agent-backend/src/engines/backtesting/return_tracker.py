"""
src/engines/backtesting/return_tracker.py
──────────────────────────────────────────────────────────────────────────────
Computes benchmark returns and excess returns for signal events.

Takes a list of SignalEvents (with forward_returns already filled) and
enriches them with benchmark-relative metrics.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from src.engines.backtesting.models import SignalEvent

logger = logging.getLogger("365advisers.backtesting.return_tracker")


class ReturnTracker:
    """Enriches SignalEvents with benchmark returns and excess returns."""

    def __init__(self, benchmark_ohlcv: pd.DataFrame) -> None:
        """
        Parameters
        ----------
        benchmark_ohlcv : pd.DataFrame
            OHLCV data for the benchmark (e.g. SPY).
            Index should be DatetimeIndex.
        """
        self.benchmark = benchmark_ohlcv
        if not self.benchmark.empty:
            self._bench_close = self.benchmark["Close"]
        else:
            self._bench_close = pd.Series(dtype=float)

    def enrich(
        self,
        events: list[SignalEvent],
        forward_windows: list[int],
    ) -> list[SignalEvent]:
        """
        Add benchmark_returns and excess_returns to each event.

        Parameters
        ----------
        events : list[SignalEvent]
            Events with forward_returns already computed.
        forward_windows : list[int]
            The T+N windows used.

        Returns
        -------
        list[SignalEvent]
            Same events, enriched with benchmark and excess returns.
        """
        if self._bench_close.empty:
            logger.warning("RETURN-TRACKER: No benchmark data, skipping enrichment")
            return events

        # Build a date → index lookup for the benchmark
        bench_dates = self.benchmark.index
        bench_close_vals = self._bench_close.values

        # Create a fast date lookup
        date_to_idx: dict[str, int] = {}
        for i, dt in enumerate(bench_dates):
            key = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
            date_to_idx[key] = i

        enriched: list[SignalEvent] = []
        for event in events:
            date_str = event.fired_date.isoformat()

            # Find closest benchmark date
            bench_idx = date_to_idx.get(date_str)
            if bench_idx is None:
                # Try nearby dates (±2 trading days)
                for offset in range(1, 4):
                    for delta_days in [offset, -offset]:
                        try:
                            nearby = (event.fired_date + __import__("datetime").timedelta(days=delta_days)).isoformat()
                            bench_idx = date_to_idx.get(nearby)
                            if bench_idx is not None:
                                break
                        except Exception:
                            pass
                    if bench_idx is not None:
                        break

            # Compute benchmark returns
            bench_returns: dict[int, float] = {}
            excess_returns: dict[int, float] = {}

            if bench_idx is not None:
                bench_price = bench_close_vals[bench_idx]
                if bench_price > 0:
                    for w in forward_windows:
                        future_idx = bench_idx + w
                        if future_idx < len(bench_close_vals):
                            br = (bench_close_vals[future_idx] - bench_price) / bench_price
                            bench_returns[w] = round(br, 6)
                            # Excess = signal return - benchmark return
                            sr = event.forward_returns.get(w)
                            if sr is not None:
                                excess_returns[w] = round(sr - br, 6)

            enriched.append(event.model_copy(update={
                "benchmark_returns": bench_returns,
                "excess_returns": excess_returns,
            }))

        logger.info(
            f"RETURN-TRACKER: Enriched {len(enriched)} events with benchmark data"
        )
        return enriched
