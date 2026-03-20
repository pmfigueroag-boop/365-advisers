"""
src/engines/validation/data_loader.py
──────────────────────────────────────────────────────────────────────────────
Fetches and caches historical data for the Alpha Validation System.

Provides:
  - 2Y daily OHLCV via yfinance
  - PIT quarterly fundamental snapshots via FundamentalProvider
  - Rolling technical indicator computation from raw OHLCV (no external deps)
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from src.engines.backtesting.fundamental_provider import FundamentalProvider

logger = logging.getLogger("365advisers.validation.data_loader")


class ValidationDataLoader:
    """
    Loads and prepares all data needed for the AVS signal IC screen.

    Usage::

        loader = ValidationDataLoader()
        data = loader.load("AAPL", years=2)
        # data = {
        #   "ohlcv": pd.DataFrame,
        #   "fundamentals": {date_str: {attr: val}},
        #   "indicators": {date_str: {indicator_name: val}},
        # }
    """

    def __init__(self) -> None:
        self._funda_provider = FundamentalProvider(cache_enabled=True)
        self._cache: dict[str, dict] = {}

    def load(
        self,
        ticker: str,
        years: int = 2,
        end_date: date | None = None,
    ) -> dict:
        """
        Load OHLCV, fundamentals, and compute rolling indicators.

        Parameters
        ----------
        ticker : str
            Stock symbol.
        years : int
            Years of history to fetch.
        end_date : date | None
            End date (defaults to today).
        """
        if ticker in self._cache:
            return self._cache[ticker]

        end = end_date or date.today()
        # Fetch extra history for indicator warm-up (SMA200 needs 200 bars)
        start = end - timedelta(days=int(years * 365) + 250)

        logger.info(f"AVS: Loading {ticker} from {start} to {end}")

        # ── 1. OHLCV ────────────────────────────────────────────────────────
        ohlcv = self._fetch_ohlcv(ticker, start, end)
        if ohlcv.empty:
            logger.warning(f"AVS: No OHLCV data for {ticker}")
            return {"ohlcv": ohlcv, "fundamentals": {}, "indicators": {}}

        # ── 2. Fundamentals (PIT) ────────────────────────────────────────────
        eval_start = end - timedelta(days=int(years * 365))
        fundamentals = self._funda_provider.get_snapshots(
            ticker, eval_start, end, ohlcv,
        )

        # ── 3. Rolling Indicators ────────────────────────────────────────────
        indicators = self._compute_rolling_indicators(ohlcv, eval_start, end)

        result = {
            "ohlcv": ohlcv,
            "fundamentals": fundamentals,
            "indicators": indicators,
        }
        self._cache[ticker] = result
        return result

    # ── Private ──────────────────────────────────────────────────────────────

    def _fetch_ohlcv(
        self, ticker: str, start: date, end: date,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV from yfinance."""
        try:
            df = yf.download(
                ticker, start=start.isoformat(), end=end.isoformat(),
                progress=False, auto_adjust=True,
            )
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df
        except Exception as exc:
            logger.error(f"AVS: yfinance error for {ticker}: {exc}")
            return pd.DataFrame()

    def _compute_rolling_indicators(
        self,
        ohlcv: pd.DataFrame,
        eval_start: date,
        eval_end: date,
    ) -> dict[str, dict[str, float]]:
        """
        Compute all technical indicators at each date in [eval_start, eval_end].

        Returns {date_str: {indicator_name: value}}.
        No lookahead: indicators at date T use only data up to T.
        """
        result: dict[str, dict[str, float]] = {}

        closes = ohlcv["Close"].values.tolist()
        highs = ohlcv["High"].values.tolist()
        lows = ohlcv["Low"].values.tolist()
        volumes = ohlcv["Volume"].values.tolist()
        dates = ohlcv.index.tolist()

        for i in range(200, len(closes)):  # Need 200 bars for SMA200
            dt = dates[i]
            day = dt.date() if hasattr(dt, "date") else dt
            if day < eval_start or day > eval_end:
                continue

            price = closes[i]
            if price <= 0:
                continue

            # SMA
            sma_50 = sum(closes[i-49:i+1]) / 50
            sma_200 = sum(closes[i-199:i+1]) / 200

            # EMA 20
            ema_20 = self._compute_ema(closes[:i+1], 20)

            # RSI 14
            rsi = self._compute_rsi(closes[:i+1], 14)

            # MACD (12, 26, 9)
            macd, macd_signal, macd_hist = self._compute_macd(closes[:i+1])

            # Bollinger Bands (20, 2)
            bb_basis, bb_upper, bb_lower = self._compute_bb(closes[:i+1], 20, 2.0)

            # ATR 14
            atr = self._compute_atr(highs[:i+1], lows[:i+1], closes[:i+1], 14)

            # Stochastic (14, 3)
            stoch_k, stoch_d = self._compute_stochastic(
                highs[:i+1], lows[:i+1], closes[:i+1], 14, 3,
            )

            # Volume features
            vol_avg_20 = sum(volumes[max(0,i-19):i+1]) / min(20, i+1)
            vol_current = volumes[i]
            volume_surprise = 0.0
            relative_volume = 1.0
            if i >= 20:
                recent_vols = volumes[i-19:i+1]
                mean_v = sum(recent_vols) / len(recent_vols)
                std_v = (sum((v - mean_v)**2 for v in recent_vols) / len(recent_vols)) ** 0.5
                if std_v > 0 and vol_current > 0:
                    volume_surprise = (vol_current - mean_v) / std_v
                if mean_v > 0 and vol_current > 0:
                    relative_volume = vol_current / mean_v

            # OBV
            obv = 0.0
            for j in range(1, i+1):
                if closes[j] > closes[j-1]:
                    obv += volumes[j]
                elif closes[j] < closes[j-1]:
                    obv -= volumes[j]

            # SMA 50/200 spread
            sma_spread = (sma_50 / sma_200 - 1.0) if sma_200 > 0 else 0.0

            # %from 52w high
            lookback = min(252, i+1)
            high_52w = max(highs[i-lookback+1:i+1])
            pct_52w = (price - high_52w) / high_52w if high_52w > 0 else 0.0

            # Mean reversion z (log)
            log_closes = [math.log(c) for c in closes[max(0,i-251):i+1] if c > 0]
            mr_z = None
            if len(log_closes) >= 50:
                avg_lp = sum(log_closes) / len(log_closes)
                std_lp = (sum((lp - avg_lp)**2 for lp in log_closes) / len(log_closes)) ** 0.5
                if std_lp > 0:
                    mr_z = (math.log(price) - avg_lp) / std_lp

            # ADX proxy (simplified — use SMA spread strength)
            adx = min(50, abs(sma_spread) * 200 + 15)

            # Build OHLCV list for the last 60 bars (for structure analysis)
            ohlcv_bars = []
            for j in range(max(0, i-59), i+1):
                ohlcv_bars.append({
                    "open": ohlcv.iloc[j].get("Open", closes[j]) if hasattr(ohlcv.iloc[j], "get") else closes[j],
                    "high": highs[j],
                    "low": lows[j],
                    "close": closes[j],
                    "volume": volumes[j],
                })

            result[day.isoformat()] = {
                "current_price": price,
                "sma_50": round(sma_50, 4),
                "sma_200": round(sma_200, 4),
                "ema_20": round(ema_20, 4),
                "rsi": round(rsi, 2),
                "stoch_k": round(stoch_k, 2),
                "stoch_d": round(stoch_d, 2),
                "macd": round(macd, 4),
                "macd_signal": round(macd_signal, 4),
                "macd_hist": round(macd_hist, 4),
                "bb_upper": round(bb_upper, 4),
                "bb_lower": round(bb_lower, 4),
                "bb_basis": round(bb_basis, 4),
                "atr": round(atr, 4),
                "volume": vol_current,
                "obv": round(obv, 2),
                "volume_avg_20": round(vol_avg_20, 2),
                "volume_surprise": round(volume_surprise, 4),
                "relative_volume": round(relative_volume, 4),
                "sma_50_200_spread": round(sma_spread, 6),
                "pct_from_52w_high": round(pct_52w, 6),
                "mean_reversion_z": round(mr_z, 4) if mr_z is not None else None,
                "adx": round(adx, 2),
                "plus_di": 25.0 if sma_spread > 0 else 15.0,
                "minus_di": 15.0 if sma_spread > 0 else 25.0,
                "tv_recommendation": "UNKNOWN",
                "ohlcv_bars": ohlcv_bars,
            }

        logger.info(f"AVS: Computed indicators for {len(result)} days")
        return result

    # ── Indicator math ───────────────────────────────────────────────────────

    @staticmethod
    def _compute_ema(prices: list[float], period: int) -> float:
        """Exponential Moving Average — last value."""
        if len(prices) < period:
            return prices[-1] if prices else 0.0
        mult = 2.0 / (period + 1)
        ema = sum(prices[:period]) / period  # SMA seed
        for p in prices[period:]:
            ema = p * mult + ema * (1 - mult)
        return ema

    @staticmethod
    def _compute_rsi(prices: list[float], period: int = 14) -> float:
        """Relative Strength Index."""
        if len(prices) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        if len(gains) < period:
            return 50.0
        avg_g = sum(gains[:period]) / period
        avg_l = sum(losses[:period]) / period
        for i in range(period, len(gains)):
            avg_g = (avg_g * (period - 1) + gains[i]) / period
            avg_l = (avg_l * (period - 1) + losses[i]) / period
        if avg_l == 0:
            return 100.0
        rs = avg_g / avg_l
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _compute_macd(
        prices: list[float],
    ) -> tuple[float, float, float]:
        """MACD(12, 26, 9)."""
        def ema_series(data: list[float], period: int) -> list[float]:
            if not data:
                return []
            result = [sum(data[:period]) / period if len(data) >= period else data[0]]
            mult = 2.0 / (period + 1)
            for i in range(period if len(data) >= period else 1, len(data)):
                result.append(data[i] * mult + result[-1] * (1 - mult))
            return result

        if len(prices) < 26:
            return 0.0, 0.0, 0.0
        ema12 = ema_series(prices, 12)
        ema26 = ema_series(prices, 26)
        min_len = min(len(ema12), len(ema26))
        macd_line = [ema12[-(min_len-i)] - ema26[-(min_len-i)] for i in range(min_len)]
        if not macd_line:
            return 0.0, 0.0, 0.0
        signal = ema_series(macd_line, 9)
        macd_val = macd_line[-1]
        signal_val = signal[-1] if signal else 0.0
        return macd_val, signal_val, macd_val - signal_val

    @staticmethod
    def _compute_bb(
        prices: list[float], period: int = 20, std_mult: float = 2.0,
    ) -> tuple[float, float, float]:
        """Bollinger Bands → (basis, upper, lower)."""
        if len(prices) < period:
            p = prices[-1] if prices else 0.0
            return p, p, p
        window = prices[-period:]
        basis = sum(window) / period
        std = (sum((x - basis)**2 for x in window) / period) ** 0.5
        return basis, basis + std_mult * std, basis - std_mult * std

    @staticmethod
    def _compute_atr(
        highs: list[float], lows: list[float], closes: list[float], period: int = 14,
    ) -> float:
        """Average True Range."""
        if len(closes) < period + 1:
            return 0.0
        trs = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1]),
            )
            trs.append(tr)
        if len(trs) < period:
            return sum(trs) / len(trs) if trs else 0.0
        return sum(trs[-period:]) / period

    @staticmethod
    def _compute_stochastic(
        highs: list[float], lows: list[float], closes: list[float],
        k_period: int = 14, d_period: int = 3,
    ) -> tuple[float, float]:
        """Stochastic Oscillator (%K, %D)."""
        if len(closes) < k_period:
            return 50.0, 50.0
        k_values = []
        for i in range(k_period - 1, len(closes)):
            window_h = highs[i - k_period + 1:i + 1]
            window_l = lows[i - k_period + 1:i + 1]
            hh = max(window_h)
            ll = min(window_l)
            if hh - ll > 0:
                k_values.append(100 * (closes[i] - ll) / (hh - ll))
            else:
                k_values.append(50.0)
        if not k_values:
            return 50.0, 50.0
        k = k_values[-1]
        d = sum(k_values[-d_period:]) / min(d_period, len(k_values))
        return k, d
