"""
src/engines/backtesting/survivorship_bias.py
--------------------------------------------------------------------------
Survivorship Bias Control — ensures backtests don't use future knowledge
about which companies survived.

Key capabilities:
  - Point-in-time universe: reconstruct what was in the index on any date
  - Delisted/acquired ticker handling
  - Look-ahead bias detection
  - Bias-adjusted backtest wrapper

Without this, every backtest is contaminated:
  "We backtested on today's S&P 500 starting from 2015"
  → This excludes companies that went bankrupt or were acquired
  → Inflates returns by ~2-3% per year (survivorship premium)

Usage::

    controller = SurvivorshipBiasController()
    universe = controller.get_universe_at(date(2020, 3, 15))
    adjusted = controller.adjust_events(events)
"""

from __future__ import annotations

import logging
from datetime import date
from collections import defaultdict

from pydantic import BaseModel, Field

logger = logging.getLogger("365advisers.backtesting.survivorship")


# ── Contracts ────────────────────────────────────────────────────────────────

class DelistedTicker(BaseModel):
    """A ticker that was removed from the universe."""
    ticker: str
    delisted_date: date
    reason: str = ""     # "bankruptcy", "acquired", "merger", "privatization"
    last_price: float = 0.0
    terminal_return: float = 0.0  # Return from last inclusion to delist


class UniverseSnapshot(BaseModel):
    """Universe membership at a point in time."""
    as_of_date: date
    tickers: list[str] = Field(default_factory=list)
    n_tickers: int = 0
    source: str = ""


class BiasReport(BaseModel):
    """Analysis of survivorship bias in a dataset."""
    total_events: int = 0
    events_with_delisted: int = 0
    events_without_delisted: int = 0
    delisted_tickers_found: list[str] = Field(default_factory=list)
    estimated_bias_bps: float = Field(
        0.0, description="Estimated survivorship bias in bps",
    )
    look_ahead_violations: int = 0
    violations: list[str] = Field(default_factory=list)


# ── Engine ───────────────────────────────────────────────────────────────────

class SurvivorshipBiasController:
    """
    Controls for survivorship bias in backtesting.

    Maintains a registry of:
      1. Historical universe snapshots (which tickers were in the index when)
      2. Delisted/acquired tickers and their terminal returns
      3. Universe change events (additions, removals)

    Usage::

        ctrl = SurvivorshipBiasController()
        ctrl.register_delisted("LUMN", date(2023, 6, 1), "acquired", -0.95)
        ctrl.register_snapshot(date(2020, 1, 1), ["AAPL", "MSFT", "LUMN", ...])

        # Get universe as it was on a specific date
        universe = ctrl.get_universe_at(date(2020, 3, 15))

        # Check for bias
        report = ctrl.analyze_bias(backtest_events)
    """

    def __init__(self) -> None:
        self._snapshots: dict[date, UniverseSnapshot] = {}
        self._delisted: dict[str, DelistedTicker] = {}
        self._current_universe: list[str] = []

    def register_snapshot(
        self,
        as_of_date: date,
        tickers: list[str],
        source: str = "manual",
    ) -> UniverseSnapshot:
        """Register a point-in-time universe snapshot."""
        snapshot = UniverseSnapshot(
            as_of_date=as_of_date,
            tickers=sorted(tickers),
            n_tickers=len(tickers),
            source=source,
        )
        self._snapshots[as_of_date] = snapshot

        logger.info(
            "SURVIVORSHIP: Registered snapshot for %s (%d tickers)",
            as_of_date, len(tickers),
        )
        return snapshot

    def register_delisted(
        self,
        ticker: str,
        delisted_date: date,
        reason: str = "unknown",
        terminal_return: float = 0.0,
        last_price: float = 0.0,
    ) -> DelistedTicker:
        """Register a delisted/acquired ticker."""
        entry = DelistedTicker(
            ticker=ticker,
            delisted_date=delisted_date,
            reason=reason,
            terminal_return=terminal_return,
            last_price=last_price,
        )
        self._delisted[ticker] = entry

        logger.info(
            "SURVIVORSHIP: Registered delisted %s (%s on %s, "
            "terminal_return=%.2f%%)",
            ticker, reason, delisted_date, terminal_return * 100,
        )
        return entry

    def set_current_universe(self, tickers: list[str]) -> None:
        """Set the current (live) universe."""
        self._current_universe = sorted(tickers)

    def get_universe_at(self, as_of_date: date) -> list[str]:
        """
        Get the universe as it existed on a specific date.

        Uses the closest snapshot on or before the requested date.
        Falls back to current universe if no snapshots available.
        """
        # Find closest snapshot on or before the date
        valid_dates = [d for d in self._snapshots if d <= as_of_date]

        if valid_dates:
            closest = max(valid_dates)
            snapshot = self._snapshots[closest]

            # Add back delisted tickers that were still active on as_of_date
            universe = set(snapshot.tickers)
            for ticker, entry in self._delisted.items():
                if entry.delisted_date > as_of_date:
                    universe.add(ticker)

            return sorted(universe)

        # Fallback: current universe + delisted that were active
        universe = set(self._current_universe)
        for ticker, entry in self._delisted.items():
            if entry.delisted_date > as_of_date:
                universe.add(ticker)

        return sorted(universe)

    def is_delisted(self, ticker: str) -> bool:
        """Check if a ticker has been delisted."""
        return ticker in self._delisted

    def was_active_on(self, ticker: str, check_date: date) -> bool:
        """Check if a ticker was active (not yet delisted) on a given date."""
        if ticker not in self._delisted:
            return True
        return self._delisted[ticker].delisted_date > check_date

    def analyze_bias(
        self,
        events: list,
        current_universe: list[str] | None = None,
    ) -> BiasReport:
        """
        Analyze a set of backtest events for survivorship bias.

        Checks:
          1. Are delisted tickers missing from the backtest?
          2. Are there look-ahead violations (using future universe)?
          3. Estimated bias magnitude

        Parameters
        ----------
        events : list
            SignalEvent objects to analyze.
        current_universe : list[str] | None
            Current universe for comparison.
        """
        current = set(current_universe or self._current_universe)
        violations: list[str] = []

        # Collect all tickers in the backtest
        backtest_tickers: set[str] = set()
        event_dates: dict[str, list[date]] = defaultdict(list)

        for e in events:
            ticker = getattr(e, "ticker", None)
            fired_date = getattr(e, "fired_date", None)
            if ticker:
                backtest_tickers.add(ticker)
            if ticker and fired_date:
                event_dates[ticker].append(fired_date)

        # Check 1: delisted tickers missing from backtest
        delisted_in_backtest = backtest_tickers & set(self._delisted.keys())
        delisted_missing = set(self._delisted.keys()) - backtest_tickers

        # Estimate bias: missing delisted tickers tend to be losers
        # Average survivorship bias ≈ 1-3% annually
        bias_estimate = 0.0
        if delisted_missing and current:
            # Rough estimate based on proportion of missing delisted
            n_missing = len(delisted_missing)
            # Weight by terminal returns of missing delisted
            avg_terminal = sum(
                self._delisted[t].terminal_return
                for t in delisted_missing
            ) / max(n_missing, 1)
            bias_estimate = abs(avg_terminal) * n_missing / max(len(current), 1)

        # Check 2: look-ahead violations
        look_ahead = 0
        for ticker, dates in event_dates.items():
            if ticker in current and ticker not in self._delisted:
                continue
            if ticker in self._delisted:
                delist_date = self._delisted[ticker].delisted_date
                for d in dates:
                    if d > delist_date:
                        look_ahead += 1
                        violations.append(
                            f"{ticker}: event on {d} but delisted on {delist_date}"
                        )

        events_with = sum(1 for e in events if getattr(e, "ticker", "") in delisted_in_backtest)
        events_without = len(events) - events_with

        return BiasReport(
            total_events=len(events),
            events_with_delisted=events_with,
            events_without_delisted=events_without,
            delisted_tickers_found=sorted(delisted_in_backtest),
            estimated_bias_bps=round(bias_estimate * 10_000, 2),
            look_ahead_violations=look_ahead,
            violations=violations,
        )

    def get_delisted_tickers(self) -> list[DelistedTicker]:
        """Get all registered delisted tickers."""
        return list(self._delisted.values())

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)

    @property
    def delisted_count(self) -> int:
        return len(self._delisted)
