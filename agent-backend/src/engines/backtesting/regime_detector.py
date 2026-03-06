"""
src/engines/backtesting/regime_detector.py
──────────────────────────────────────────────────────────────────────────────
Market-regime classifier for regime-conditional backtesting.

Segments historical trading days into Bull / Bear / Range-Bound / High-Vol
regimes so that signal performance can be evaluated per environment.
"""

from __future__ import annotations

import logging
from datetime import date
from enum import Enum

import numpy as np
import pandas as pd

logger = logging.getLogger("365advisers.backtesting.regime_detector")


# ─── Regime Enumeration ──────────────────────────────────────────────────────

class MarketRegime(str, Enum):
    BULL = "bull"
    BEAR = "bear"
    RANGE_BOUND = "range"
    HIGH_VOL = "high_vol"


# ─── Configuration ───────────────────────────────────────────────────────────

class RegimeConfig:
    """Tunable parameters for regime classification."""

    def __init__(
        self,
        sma_period: int = 200,
        bb_period: int = 20,
        bb_width_threshold: float = 0.04,
        atr_period: int = 14,
        atr_expansion_mult: float = 1.8,
    ) -> None:
        self.sma_period = sma_period
        self.bb_period = bb_period
        self.bb_width_threshold = bb_width_threshold
        self.atr_period = atr_period
        self.atr_expansion_mult = atr_expansion_mult


# ─── Detector ────────────────────────────────────────────────────────────────

class RegimeDetector:
    """
    Classify each trading day into a market regime.

    Logic hierarchy (first match wins):
        1. HIGH_VOL  — ATR(14) > median(ATR) × expansion_mult
        2. RANGE     — BB Width(20) < threshold
        3. BULL      — Close > SMA(200)
        4. BEAR      — Close ≤ SMA(200)
    """

    def __init__(self, config: RegimeConfig | None = None) -> None:
        self.cfg = config or RegimeConfig()

    # ── Public API ────────────────────────────────────────────────────────

    def classify(
        self, benchmark_ohlcv: pd.DataFrame
    ) -> dict[date, MarketRegime]:
        """
        Assign a regime label to each trading day.

        Parameters
        ----------
        benchmark_ohlcv : pd.DataFrame
            OHLCV DataFrame (index = DatetimeIndex).

        Returns
        -------
        dict[date, MarketRegime]
            Mapping from date → regime.
        """
        if benchmark_ohlcv.empty or len(benchmark_ohlcv) < self.cfg.sma_period:
            logger.warning(
                "REGIME-DETECTOR: Insufficient data (%d rows, need %d)",
                len(benchmark_ohlcv), self.cfg.sma_period,
            )
            return {}

        close = benchmark_ohlcv["Close"].values.astype(float)
        high = benchmark_ohlcv["High"].values.astype(float)
        low = benchmark_ohlcv["Low"].values.astype(float)

        sma = self._rolling_mean(close, self.cfg.sma_period)
        bb_width = self._bollinger_width(close, self.cfg.bb_period)
        atr = self._atr(high, low, close, self.cfg.atr_period)
        atr_median = float(np.nanmedian(atr[atr > 0])) if np.any(atr > 0) else 1.0
        atr_threshold = atr_median * self.cfg.atr_expansion_mult

        regimes: dict[date, MarketRegime] = {}
        dates = benchmark_ohlcv.index

        for i in range(self.cfg.sma_period, len(close)):
            dt = dates[i]
            day_key = dt.date() if hasattr(dt, "date") else dt

            if atr[i] > atr_threshold:
                regime = MarketRegime.HIGH_VOL
            elif bb_width[i] < self.cfg.bb_width_threshold:
                regime = MarketRegime.RANGE_BOUND
            elif close[i] > sma[i]:
                regime = MarketRegime.BULL
            else:
                regime = MarketRegime.BEAR

            regimes[day_key] = regime

        # Log distribution
        counts = {}
        for r in regimes.values():
            counts[r.value] = counts.get(r.value, 0) + 1
        logger.info("REGIME-DETECTOR: Classified %d days — %s", len(regimes), counts)

        return regimes

    def segment_events(
        self,
        events: list,
        regimes: dict[date, MarketRegime],
    ) -> dict[MarketRegime, list]:
        """
        Split signal events by the regime active on their fired_date.

        Parameters
        ----------
        events : list[SignalEvent]
            Signal events from the backtesting engine.
        regimes : dict[date, MarketRegime]
            Output of classify().

        Returns
        -------
        dict[MarketRegime, list[SignalEvent]]
        """
        segmented: dict[MarketRegime, list] = {r: [] for r in MarketRegime}

        for event in events:
            fired = event.fired_date
            regime = regimes.get(fired)
            if regime is None:
                # Try to find nearest date within ±3 days
                from datetime import timedelta
                for offset in range(1, 4):
                    for delta in (offset, -offset):
                        nearby = fired + timedelta(days=delta)
                        regime = regimes.get(nearby)
                        if regime is not None:
                            break
                    if regime is not None:
                        break

            if regime is not None:
                segmented[regime].append(event)

        for r, evts in segmented.items():
            if evts:
                logger.debug("REGIME-DETECTOR: %s → %d events", r.value, len(evts))

        return segmented

    # ── Technical Indicator Helpers ────────────────────────────────────────

    @staticmethod
    def _rolling_mean(data: np.ndarray, period: int) -> np.ndarray:
        """Simple moving average with NaN fill for warm-up."""
        result = np.full_like(data, np.nan)
        cumsum = np.cumsum(data)
        result[period - 1:] = (cumsum[period - 1:] - np.concatenate(([0], cumsum[:-period]))) / period
        return result

    @staticmethod
    def _bollinger_width(close: np.ndarray, period: int) -> np.ndarray:
        """BB Width = (Upper - Lower) / Middle = 4 × StdDev / SMA."""
        result = np.full_like(close, np.nan)
        for i in range(period - 1, len(close)):
            window = close[i - period + 1: i + 1]
            sma = np.mean(window)
            if sma > 0:
                std = np.std(window, ddof=1)
                result[i] = (4.0 * std) / sma
            else:
                result[i] = 0.0
        return result

    @staticmethod
    def _atr(
        high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int
    ) -> np.ndarray:
        """Average True Range."""
        n = len(close)
        tr = np.zeros(n)
        tr[0] = high[0] - low[0]
        for i in range(1, n):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )
        atr = np.full(n, np.nan)
        if n >= period:
            atr[period - 1] = np.mean(tr[:period])
            alpha = 1.0 / period
            for i in range(period, n):
                atr[i] = atr[i - 1] * (1 - alpha) + tr[i] * alpha
        return atr
