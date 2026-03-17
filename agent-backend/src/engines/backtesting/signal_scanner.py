"""
src/engines/backtesting/signal_scanner.py
--------------------------------------------------------------------------
Live Signal Scanner — scheduled scanning of the investment universe to
detect and record alpha signals.

Integrates with:
  - ``DetectorRegistry`` for signal detection (IDEA detectors)
  - ``universes.py`` for stock universe definitions
  - ``SyncManager`` schedule model for cron-compatible scanning
  - ``AlertManager`` for firing notifications on significant events

Flow
~~~~
1. Select universe (test, mega_cap, sp500_100, sp500)
2. For each ticker: run all enabled detectors
3. Convert DetectorResult → SignalEvent
4. Persist events for backfill tracking
5. Notify alert manager for high-conviction signals

Usage::

    scanner = SignalScanner(universe="mega_cap")
    result = scanner.scan()
    print(f"Fired: {result.total_events} events from {result.tickers_scanned} tickers")
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from collections import defaultdict

from pydantic import BaseModel, Field

from src.engines.backtesting.models import SignalEvent, SignalStrength
from src.engines.backtesting.universes import get_universe, list_universes

logger = logging.getLogger("365advisers.backtesting.scanner")


# ── Contracts ────────────────────────────────────────────────────────────────

class ScanConfig(BaseModel):
    """Configuration for a scanner run."""
    universe_name: str = Field(
        "test",
        description="Universe to scan: test, mega_cap, sp500_100, sp500",
    )
    max_tickers: int | None = Field(
        None, description="Cap on number of tickers to scan (None = all)",
    )
    signal_ids: list[str] | None = Field(
        None, description="Restrict to specific signal IDs (None = all)",
    )
    min_confidence: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Minimum confidence to record an event",
    )
    scan_date: date | None = Field(
        None, description="Date to scan (None = today)",
    )


class ScanResult(BaseModel):
    """Output of a scanner run."""
    scan_date: date
    universe_name: str = ""
    tickers_scanned: int = 0
    tickers_with_signals: int = 0
    total_events: int = 0
    events_by_signal: dict[str, int] = Field(default_factory=dict)
    events: list[SignalEvent] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    scanned_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Engine ───────────────────────────────────────────────────────────────────

class SignalScanner:
    """
    Scans an investment universe for alpha signals.

    This is a framework-level scanner that delegates detection to a
    callable detector function. In production, wire this to the
    DetectorRegistry; for testing, inject a simple callable.

    Parameters
    ----------
    detector_fn : callable | None
        Function(ticker, scan_date) -> list[SignalEvent].
        If None, uses a no-op detector.
    config : ScanConfig | None
        Scanner configuration.
    """

    def __init__(
        self,
        detector_fn: callable | None = None,
        config: ScanConfig | None = None,
    ) -> None:
        self.config = config or ScanConfig()
        self._detector_fn = detector_fn or self._noop_detector

    def scan(
        self,
        scan_date: date | None = None,
    ) -> ScanResult:
        """
        Execute a full universe scan.

        Parameters
        ----------
        scan_date : date | None
            Override scan date (default: config.scan_date or today).

        Returns
        -------
        ScanResult
            Complete scan output with events and metadata.
        """
        import time
        start = time.monotonic()

        sd = scan_date or self.config.scan_date or date.today()

        # 1. Get universe
        try:
            universe = get_universe(
                self.config.universe_name,
                max_size=self.config.max_tickers,
            )
        except ValueError as e:
            return ScanResult(
                scan_date=sd,
                errors=[str(e)],
            )

        # 2. Scan each ticker
        all_events: list[SignalEvent] = []
        events_by_signal: dict[str, int] = defaultdict(int)
        tickers_with = 0
        errors: list[str] = []

        for ticker in universe:
            try:
                ticker_events = self._detector_fn(ticker, sd)

                # Apply filters
                filtered = []
                for e in ticker_events:
                    if e.confidence < self.config.min_confidence:
                        continue
                    if self.config.signal_ids and e.signal_id not in self.config.signal_ids:
                        continue
                    filtered.append(e)

                if filtered:
                    tickers_with += 1
                    all_events.extend(filtered)
                    for e in filtered:
                        events_by_signal[e.signal_id] += 1

            except Exception as e:
                errors.append(f"{ticker}: {e}")
                logger.warning("SCANNER: Error scanning %s: %s", ticker, e)

        elapsed = time.monotonic() - start

        logger.info(
            "SCANNER: Scanned %d tickers (%s), %d events from %d tickers "
            "in %.1fs",
            len(universe), self.config.universe_name,
            len(all_events), tickers_with, elapsed,
        )

        return ScanResult(
            scan_date=sd,
            universe_name=self.config.universe_name,
            tickers_scanned=len(universe),
            tickers_with_signals=tickers_with,
            total_events=len(all_events),
            events_by_signal=dict(events_by_signal),
            events=all_events,
            errors=errors,
            duration_seconds=round(elapsed, 3),
        )

    @staticmethod
    def _noop_detector(ticker: str, scan_date: date) -> list[SignalEvent]:
        """No-op detector for testing."""
        return []

    @staticmethod
    def available_universes() -> dict[str, int]:
        """List available universes and their sizes."""
        return list_universes()
