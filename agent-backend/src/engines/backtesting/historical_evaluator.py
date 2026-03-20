"""
src/engines/backtesting/historical_evaluator.py
──────────────────────────────────────────────────────────────────────────────
Walk-forward signal evaluation over historical data.

Slides a daily window across OHLCV history, reconstructs feature sets, and
evaluates each AlphaSignalDefinition at every date using the existing
SignalEvaluator machinery.  Records signal firing events with cooldown.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd

from src.engines.alpha_signals.models import (
    AlphaSignalDefinition,
    SignalDirection,
    SignalStrength,
)
from src.engines.backtesting.models import SignalEvent

logger = logging.getLogger("365advisers.backtesting.historical_evaluator")


# ─── Feature reconstruction ─────────────────────────────────────────────────

def _build_technical_snapshot(
    ohlcv: pd.DataFrame, idx: int
) -> dict[str, float]:
    """
    Build a minimal technical feature dict from OHLCV at position `idx`.

    Uses the slice ohlcv[:idx+1] (inclusive) so there is no look-ahead.
    Returns indicator values that match the feature_path format
    'technical.<attr>'.
    """
    window = ohlcv.iloc[: idx + 1]
    close = window["Close"].iloc[-1]
    volume = window["Volume"].iloc[-1] if "Volume" in window.columns else 0

    # SMA
    sma_50 = window["Close"].rolling(50).mean().iloc[-1] if len(window) >= 50 else close
    sma_200 = window["Close"].rolling(200).mean().iloc[-1] if len(window) >= 200 else close
    ema_20 = window["Close"].ewm(span=20, adjust=False).mean().iloc[-1] if len(window) >= 20 else close

    # RSI (14)
    rsi = 50.0
    if len(window) >= 15:
        delta = window["Close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean().iloc[-1]
        loss = (-delta.clip(upper=0)).rolling(14).mean().iloc[-1]
        if loss != 0:
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
        else:
            rsi = 100.0

    # MACD
    macd = 0.0
    macd_signal = 0.0
    macd_hist = 0.0
    if len(window) >= 26:
        ema12 = window["Close"].ewm(span=12, adjust=False).mean()
        ema26 = window["Close"].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        macd_signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd = macd_line.iloc[-1]
        macd_signal = macd_signal_line.iloc[-1]
        macd_hist = macd - macd_signal

    # Bollinger Bands
    bb_basis = close
    bb_upper = close
    bb_lower = close
    if len(window) >= 20:
        bb_basis = window["Close"].rolling(20).mean().iloc[-1]
        bb_std = window["Close"].rolling(20).std().iloc[-1]
        bb_upper = bb_basis + 2 * bb_std
        bb_lower = bb_basis - 2 * bb_std

    # ATR (14)
    atr = 0.0
    if len(window) >= 15 and "High" in window.columns and "Low" in window.columns:
        high = window["High"]
        low = window["Low"]
        prev_close = window["Close"].shift(1)
        tr = pd.concat([
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]

    # Stochastic
    stoch_k = 50.0
    stoch_d = 50.0
    if len(window) >= 14 and "High" in window.columns and "Low" in window.columns:
        high_14 = window["High"].rolling(14).max().iloc[-1]
        low_14 = window["Low"].rolling(14).min().iloc[-1]
        if high_14 != low_14:
            stoch_k = (close - low_14) / (high_14 - low_14) * 100

    # Volume avg 20
    volume_avg_20 = 0.0
    if len(window) >= 20 and "Volume" in window.columns:
        volume_avg_20 = window["Volume"].rolling(20).mean().iloc[-1]

    # OBV (simplified)
    obv = 0.0
    if len(window) >= 2 and "Volume" in window.columns:
        close_diff = window["Close"].diff()
        sign = close_diff.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        obv = (sign * window["Volume"]).cumsum().iloc[-1]

    # ── Derived metrics required by signal definitions ────────────────────

    # SMA 50/200 spread (for Golden Cross / Death Cross signals)
    sma_50_200_spread = 0.0
    if sma_200 != 0:
        sma_50_200_spread = (sma_50 - sma_200) / sma_200

    # Mean reversion z-score (price vs 50-day SMA, normalized by std)
    mean_reversion_z = 0.0
    if len(window) >= 50:
        std_50 = window["Close"].rolling(50).std().iloc[-1]
        if std_50 > 0:
            mean_reversion_z = (close - sma_50) / std_50

    # Percentage from 52-week high
    pct_from_52w_high = 0.0
    if len(window) >= 252 and "High" in window.columns:
        high_52w = window["High"].tail(252).max()
        if high_52w > 0:
            pct_from_52w_high = (close - high_52w) / high_52w
    elif "High" in window.columns:
        high_all = window["High"].max()
        if high_all > 0:
            pct_from_52w_high = (close - high_all) / high_all

    # Volume surprise (current volume / 20-day average)
    volume_surprise = 0.0
    if volume_avg_20 > 0:
        volume_surprise = volume / volume_avg_20

    # ADX (Average Directional Index, simplified 14-period)
    adx = 25.0  # Neutral default
    if len(window) >= 28 and "High" in window.columns and "Low" in window.columns:
        try:
            high = window["High"]
            low = window["Low"]
            prev_close = window["Close"].shift(1)
            plus_dm = (high - high.shift(1)).clip(lower=0)
            minus_dm = (low.shift(1) - low).clip(lower=0)
            # Zero out when other DM is larger
            plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
            minus_dm = minus_dm.where(minus_dm > plus_dm, 0)
            tr = pd.concat([
                (high - low),
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ], axis=1).max(axis=1)
            atr_14 = tr.rolling(14).mean()
            plus_di = 100.0 * (plus_dm.rolling(14).mean() / atr_14)
            minus_di = 100.0 * (minus_dm.rolling(14).mean() / atr_14)
            dx = 100.0 * ((plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10))
            adx = dx.rolling(14).mean().iloc[-1]
            if pd.isna(adx):
                adx = 25.0
        except Exception:
            adx = 25.0

    # Realized volatility (20-day annualized)
    realized_vol_20d = 0.0
    if len(window) >= 21:
        daily_returns = window["Close"].pct_change().tail(20)
        realized_vol_20d = daily_returns.std() * (252 ** 0.5)
        if pd.isna(realized_vol_20d):
            realized_vol_20d = 0.0

    return {
        "current_price": close,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "ema_20": ema_20,
        "rsi": rsi,
        "stoch_k": stoch_k,
        "stoch_d": stoch_d,
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "bb_basis": bb_basis,
        "atr": atr,
        "volume": volume,
        "obv": obv,
        "volume_avg_20": volume_avg_20,
        # Derived metrics
        "sma_50_200_spread": sma_50_200_spread,
        "mean_reversion_z": mean_reversion_z,
        "pct_from_52w_high": pct_from_52w_high,
        "volume_surprise": volume_surprise,
        "adx": adx,
        "realized_vol_20d": realized_vol_20d,
    }


def _resolve_feature_value(
    feature_path: str,
    technical_snap: dict[str, float],
    fundamental_snap: dict[str, float] | None,
) -> float | None:
    """
    Resolve a dot-path like 'technical.rsi' to a numeric value.
    """
    parts = feature_path.split(".", 1)
    if len(parts) != 2:
        return None

    domain, attr = parts
    if domain == "technical":
        return technical_snap.get(attr)
    elif domain == "fundamental" and fundamental_snap:
        return fundamental_snap.get(attr)
    return None


def _check_fired(signal: AlphaSignalDefinition, value: float) -> bool:
    """Check if a signal condition is met."""
    if signal.direction == SignalDirection.ABOVE:
        return value > signal.threshold
    elif signal.direction == SignalDirection.BELOW:
        return value < signal.threshold
    elif signal.direction == SignalDirection.BETWEEN:
        upper = signal.upper_threshold or signal.threshold
        return signal.threshold <= value <= upper
    return False


def _compute_strength(signal: AlphaSignalDefinition, value: float) -> SignalStrength:
    """Classify signal strength based on distance from threshold."""
    if signal.strong_threshold is not None:
        if signal.direction == SignalDirection.ABOVE and value >= signal.strong_threshold:
            return SignalStrength.STRONG
        elif signal.direction == SignalDirection.BELOW and value <= signal.strong_threshold:
            return SignalStrength.STRONG

    # Check moderate threshold (midpoint between threshold and strong)
    if signal.strong_threshold is not None:
        mid = (signal.threshold + signal.strong_threshold) / 2
        if signal.direction == SignalDirection.ABOVE and value >= mid:
            return SignalStrength.MODERATE
        elif signal.direction == SignalDirection.BELOW and value <= mid:
            return SignalStrength.MODERATE

    return SignalStrength.WEAK


def _compute_confidence(signal: AlphaSignalDefinition, value: float) -> float:
    """Compute confidence as 0.0–1.0 based on signal decisiveness."""
    if signal.strong_threshold is None or signal.strong_threshold == signal.threshold:
        return 0.5

    progress = abs(value - signal.threshold) / abs(signal.strong_threshold - signal.threshold)
    return min(max(progress, 0.0), 1.0)


# ─── Main Walk-Forward Evaluator ─────────────────────────────────────────────

class HistoricalEvaluator:
    """
    Walk-forward evaluator that scans historical OHLCV data and fires
    signals at each date, returning a list of SignalEvents.
    """

    def __init__(self, cooldown_factor: float = 0.5) -> None:
        self.cooldown_factor = cooldown_factor

    def evaluate(
        self,
        ticker: str,
        ohlcv: pd.DataFrame,
        signals: list[AlphaSignalDefinition],
        fundamental_snapshots: dict[str, dict[str, float]] | None = None,
        forward_windows: list[int] | None = None,
    ) -> list[SignalEvent]:
        """
        Run walk-forward evaluation on a single ticker's historical data.

        Parameters
        ----------
        ticker : str
            Symbol being evaluated.
        ohlcv : pd.DataFrame
            Historical data with columns: Open, High, Low, Close, Volume.
            Index should be DatetimeIndex.
        signals : list[AlphaSignalDefinition]
            Signals to evaluate at each date.
        fundamental_snapshots : dict | None
            Optional: {date_str: {metric: value}} for fundamental features.
        forward_windows : list[int]
            T+N windows for forward return calculation.

        Returns
        -------
        list[SignalEvent]
            All signal firing events with forward returns.
        """
        if forward_windows is None:
            forward_windows = [1, 5, 10, 20, 60]

        if ohlcv.empty or len(ohlcv) < 60:
            logger.warning(f"BACKTEST: Insufficient data for {ticker} ({len(ohlcv)} bars)")
            return []

        events: list[SignalEvent] = []
        max_window = max(forward_windows)

        # Track cooldowns per signal: signal_id → last_fire_idx
        cooldowns: dict[str, int] = {}

        # Need at least 200 bars for SMA200 warm-up
        start_idx = min(200, len(ohlcv) - max_window - 1)
        end_idx = len(ohlcv) - max_window  # Stop before we run out of forward data

        if start_idx >= end_idx:
            logger.warning(f"BACKTEST: Not enough forward data for {ticker}")
            return []

        dates = ohlcv.index
        closes = ohlcv["Close"].values

        for idx in range(start_idx, end_idx):
            current_date = dates[idx]
            date_str = (
                current_date.strftime("%Y-%m-%d")
                if hasattr(current_date, "strftime")
                else str(current_date)[:10]
            )

            # Build technical snapshot at this point
            tech_snap = _build_technical_snapshot(ohlcv, idx)

            # Get fundamental snapshot for this date (if available)
            fund_snap = None
            if fundamental_snapshots:
                fund_snap = fundamental_snapshots.get(date_str)

            # Evaluate each signal
            for signal in signals:
                # Check cooldown
                cooldown_days = int(max_window * self.cooldown_factor)
                last_fire = cooldowns.get(signal.id, -999)
                if (idx - last_fire) < cooldown_days:
                    continue

                # Resolve feature value
                value = _resolve_feature_value(signal.feature_path, tech_snap, fund_snap)
                if value is None:
                    continue

                # Check if signal fires
                if not _check_fired(signal, value):
                    continue

                # Signal fired — compute forward returns
                price_at_fire = closes[idx]
                if price_at_fire <= 0:
                    continue

                fwd_returns: dict[int, float] = {}
                for w in forward_windows:
                    future_idx = idx + w
                    if future_idx < len(closes):
                        fwd_returns[w] = (closes[future_idx] - price_at_fire) / price_at_fire

                strength = _compute_strength(signal, value)
                confidence = _compute_confidence(signal, value)

                events.append(SignalEvent(
                    signal_id=signal.id,
                    ticker=ticker,
                    fired_date=date.fromisoformat(date_str),
                    strength=strength,
                    confidence=confidence,
                    value=round(value, 6),
                    price_at_fire=round(price_at_fire, 4),
                    forward_returns={k: round(v, 6) for k, v in fwd_returns.items()},
                    benchmark_returns={},  # Filled in by return_tracker
                    excess_returns={},
                ))

                # Set cooldown
                cooldowns[signal.id] = idx

        logger.info(
            f"BACKTEST: {ticker} → {len(events)} signal events "
            f"from {len(signals)} signals over {end_idx - start_idx} days"
        )
        return events
