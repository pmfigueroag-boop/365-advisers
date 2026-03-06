"""
src/engines/backtesting/rolling_analyzer.py
──────────────────────────────────────────────────────────────────────────────
Rolling-window performance analyzer with degradation detection.

Computes metrics over sliding windows (30d, 90d, 252d) and detects
significant performance degradation relative to historical peaks.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from src.engines.backtesting.models import SignalPerformanceEvent
from src.engines.backtesting.regime_detector import MarketRegime

logger = logging.getLogger("365advisers.backtesting.rolling_analyzer")


# ─── Output Models ───────────────────────────────────────────────────────────

class RollingPerformanceSnapshot(BaseModel):
    """Point-in-time performance snapshot for a signal."""
    signal_id: str
    window_days: int
    as_of_date: date
    hit_rate: float = 0.0
    sharpe: float = 0.0
    avg_return: float = 0.0
    avg_excess_return: float = 0.0
    sample_size: int = 0
    regime: MarketRegime | None = None


class DegradationSeverity(str, Enum):
    WARNING = "warning"      # 20-40% decline
    CRITICAL = "critical"    # >40% decline


class DegradationReport(BaseModel):
    """Alert when a signal's performance degrades significantly."""
    signal_id: str
    signal_name: str = ""
    metric: str
    peak_value: float
    current_value: float
    decline_pct: float
    peak_date: date
    severity: DegradationSeverity = DegradationSeverity.WARNING
    recommendation: str = "monitor"
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ─── Constants ───────────────────────────────────────────────────────────────

_TRADING_DAYS_YEAR = 252
_DEFAULT_WINDOWS = [30, 90, 252]
_REF_FORWARD_WINDOW = 20  # T+20 as reference for Sharpe & hit rate


# ─── Rolling Analyzer ────────────────────────────────────────────────────────

class RollingAnalyzer:
    """
    Computes rolling performance metrics and detects degradation.

    Usage::

        analyzer = RollingAnalyzer()
        snapshots = analyzer.compute_rolling_metrics("value.fcf_yield_high", events)
        report = analyzer.detect_degradation("value.fcf_yield_high", events)
    """

    def __init__(
        self,
        windows: list[int] | None = None,
        degradation_threshold: float = 0.20,
        critical_threshold: float = 0.40,
    ) -> None:
        self.windows = windows or _DEFAULT_WINDOWS
        self.degradation_threshold = degradation_threshold
        self.critical_threshold = critical_threshold

    def compute_rolling_metrics(
        self,
        signal_id: str,
        events: list[SignalPerformanceEvent],
        regime: MarketRegime | None = None,
    ) -> list[RollingPerformanceSnapshot]:
        """
        Compute performance snapshots over each rolling window.

        Parameters
        ----------
        signal_id : str
            Signal identifier.
        events : list[SignalPerformanceEvent]
            Historical signal firing events with forward returns.
        regime : MarketRegime | None
            Optional regime filter tag for the snapshot.

        Returns
        -------
        list[RollingPerformanceSnapshot]
        """
        if not events:
            return []

        # Sort events by fired date
        sorted_events = sorted(events, key=lambda e: e.fired_date)

        snapshots: list[RollingPerformanceSnapshot] = []

        for window in self.windows:
            if len(sorted_events) < 5:
                continue

            # Use the last N events (approximation for N trading days)
            window_events = sorted_events[-window:] if len(sorted_events) >= window else sorted_events

            hit_rate = self._compute_hit_rate(window_events)
            sharpe = self._compute_sharpe(window_events)
            avg_ret = self._compute_avg_return(window_events)
            avg_excess = self._compute_avg_excess_return(window_events)

            latest_date = self._parse_date(sorted_events[-1].fired_date)

            snapshots.append(RollingPerformanceSnapshot(
                signal_id=signal_id,
                window_days=window,
                as_of_date=latest_date,
                hit_rate=round(hit_rate, 4),
                sharpe=round(sharpe, 4),
                avg_return=round(avg_ret, 6),
                avg_excess_return=round(avg_excess, 6),
                sample_size=len(window_events),
                regime=regime,
            ))

        return snapshots

    def detect_degradation(
        self,
        signal_id: str,
        events: list[SignalPerformanceEvent],
        signal_name: str = "",
    ) -> list[DegradationReport]:
        """
        Detect performance degradation by comparing recent vs. historical.

        Compares 30D rolling Sharpe and hit rate against the 252D
        (full history) values. Flags if decline exceeds thresholds.

        Returns
        -------
        list[DegradationReport]
            Empty if no degradation detected.
        """
        if len(events) < 30:
            return []

        sorted_events = sorted(events, key=lambda e: e.fired_date)
        reports: list[DegradationReport] = []

        # Full-history metrics (peak reference)
        full_sharpe = self._compute_sharpe(sorted_events)
        full_hit = self._compute_hit_rate(sorted_events)

        # Recent window (last 30 events)
        recent = sorted_events[-30:]
        recent_sharpe = self._compute_sharpe(recent)
        recent_hit = self._compute_hit_rate(recent)

        peak_date = self._parse_date(sorted_events[0].fired_date)

        # Check Sharpe degradation
        if full_sharpe > 0.1:
            decline = (full_sharpe - recent_sharpe) / full_sharpe
            if decline >= self.degradation_threshold:
                severity = (
                    DegradationSeverity.CRITICAL
                    if decline >= self.critical_threshold
                    else DegradationSeverity.WARNING
                )
                recommendation = (
                    "disable" if decline >= 0.60
                    else "reduce_weight" if decline >= self.critical_threshold
                    else "monitor"
                )
                reports.append(DegradationReport(
                    signal_id=signal_id,
                    signal_name=signal_name,
                    metric="sharpe",
                    peak_value=round(full_sharpe, 4),
                    current_value=round(recent_sharpe, 4),
                    decline_pct=round(-decline, 4),
                    peak_date=peak_date,
                    severity=severity,
                    recommendation=recommendation,
                ))

        # Check Hit Rate degradation
        if full_hit > 0.40:
            decline = (full_hit - recent_hit) / full_hit
            if decline >= self.degradation_threshold:
                severity = (
                    DegradationSeverity.CRITICAL
                    if decline >= self.critical_threshold
                    else DegradationSeverity.WARNING
                )
                recommendation = (
                    "disable" if recent_hit < 0.35
                    else "reduce_weight" if decline >= self.critical_threshold
                    else "monitor"
                )
                reports.append(DegradationReport(
                    signal_id=signal_id,
                    signal_name=signal_name,
                    metric="hit_rate",
                    peak_value=round(full_hit, 4),
                    current_value=round(recent_hit, 4),
                    decline_pct=round(-decline, 4),
                    peak_date=peak_date,
                    severity=severity,
                    recommendation=recommendation,
                ))

        if reports:
            logger.warning(
                "ROLLING-ANALYZER: Degradation detected for '%s' — %d alerts",
                signal_id, len(reports),
            )

        return reports

    # ── Metric Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _compute_hit_rate(events: list[SignalPerformanceEvent]) -> float:
        """Hit rate from T+20 forward returns."""
        returns = []
        for e in events:
            fr = e.forward_returns or {}
            val = fr.get(_REF_FORWARD_WINDOW) or fr.get(str(_REF_FORWARD_WINDOW))
            if val is not None:
                returns.append(float(val))
        if not returns:
            return 0.0
        return sum(1 for r in returns if r > 0) / len(returns)

    @staticmethod
    def _compute_sharpe(events: list[SignalPerformanceEvent]) -> float:
        """Annualised Sharpe from T+20 excess returns."""
        excess = []
        for e in events:
            er = e.excess_returns or {}
            val = er.get(_REF_FORWARD_WINDOW) or er.get(str(_REF_FORWARD_WINDOW))
            if val is not None:
                excess.append(float(val))
        if len(excess) < 5:
            return 0.0
        import numpy as np
        arr = np.array(excess)
        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1))
        if std < 1e-9:
            return 0.0
        annualisation = (_TRADING_DAYS_YEAR / _REF_FORWARD_WINDOW) ** 0.5
        return (mean / std) * annualisation

    @staticmethod
    def _compute_avg_return(events: list[SignalPerformanceEvent]) -> float:
        """Average T+20 forward return."""
        returns = []
        for e in events:
            fr = e.forward_returns or {}
            val = fr.get(_REF_FORWARD_WINDOW) or fr.get(str(_REF_FORWARD_WINDOW))
            if val is not None:
                returns.append(float(val))
        return sum(returns) / len(returns) if returns else 0.0

    @staticmethod
    def _compute_avg_excess_return(events: list[SignalPerformanceEvent]) -> float:
        """Average T+20 excess return."""
        excess = []
        for e in events:
            er = e.excess_returns or {}
            val = er.get(_REF_FORWARD_WINDOW) or er.get(str(_REF_FORWARD_WINDOW))
            if val is not None:
                excess.append(float(val))
        return sum(excess) / len(excess) if excess else 0.0

    @staticmethod
    def _parse_date(d) -> date:
        """Convert a date-like value to date."""
        if isinstance(d, date):
            return d
        return date.fromisoformat(str(d)[:10])
