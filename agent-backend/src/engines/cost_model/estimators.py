"""
src/engines/cost_model/estimators.py
──────────────────────────────────────────────────────────────────────────────
Bid-ask spread and market impact estimators.

Provides:
  - Corwin-Schultz High-Low spread estimator (from OHLCV)
  - Empirical fallback spread estimator (from ADV)
  - Square-root market impact model (Almgren-Chriss simplified)
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd

logger = logging.getLogger("365advisers.cost_model.estimators")


class SpreadEstimator:
    """
    Estimate bid-ask spread from OHLCV data.

    Primary method: Corwin-Schultz High-Low estimator.
    Fallback: empirical estimate from average daily volume.
    """

    @staticmethod
    def corwin_schultz(
        ohlcv: pd.DataFrame,
        idx: int,
        lookback: int = 20,
    ) -> float:
        """
        Corwin-Schultz (2012) High-Low spread estimator.

        Uses the relationship between high-low ranges over 1-day and
        2-day windows to infer effective spread.

        Parameters
        ----------
        ohlcv : pd.DataFrame
            Must contain 'High' and 'Low' columns.
        idx : int
            Current position in the DataFrame.
        lookback : int
            Number of days to average over.

        Returns
        -------
        float
            Estimated spread as a fraction (e.g. 0.002 = 20 bps).
        """
        start = max(0, idx - lookback)
        if idx - start < 2:
            return SpreadEstimator.empirical_fallback(0)

        highs = ohlcv["High"].values[start:idx + 1]
        lows = ohlcv["Low"].values[start:idx + 1]

        if len(highs) < 3:
            return SpreadEstimator.empirical_fallback(0)

        # β: average of (ln(H/L))² over single days
        log_hl = np.log(highs / np.maximum(lows, 1e-10))
        beta = float(np.mean(log_hl[:-1] ** 2))

        # γ: (ln(H₂/L₂))² using 2-day high/low
        h2 = np.maximum(highs[1:], highs[:-1])
        l2 = np.minimum(lows[1:], lows[:-1])
        log_hl2 = np.log(h2 / np.maximum(l2, 1e-10))
        gamma = float(np.mean(log_hl2 ** 2))

        # Corwin-Schultz formula
        denom = 3 - 2 * math.sqrt(2)
        if denom == 0:
            return SpreadEstimator.empirical_fallback(0)

        alpha = (math.sqrt(2 * beta) - math.sqrt(beta)) / denom - math.sqrt(gamma / denom)

        if alpha <= 0:
            # Negative spread estimate → use fallback
            return SpreadEstimator.empirical_fallback(0)

        spread = 2 * (math.exp(alpha) - 1) / (1 + math.exp(alpha))
        # Clamp to reasonable range [1 bps, 500 bps]
        return max(0.0001, min(spread, 0.05))

    @staticmethod
    def empirical_fallback(adv_dollars: float) -> float:
        """
        Empirical spread estimate based on average daily volume.

        Larger-cap / higher-volume stocks have tighter spreads.

        Parameters
        ----------
        adv_dollars : float
            Average daily dollar volume (price × volume).

        Returns
        -------
        float
            Estimated spread as a fraction.
        """
        adv_millions = max(adv_dollars / 1e6, 0.01)
        # Heuristic: spread_bps ≈ 200 / √(ADV_millions), floor at 3 bps
        spread_bps = max(3.0, 200.0 / math.sqrt(adv_millions))
        # Cap at 200 bps for very illiquid names
        spread_bps = min(spread_bps, 200.0)
        return spread_bps / 10_000

    def estimate(
        self,
        ohlcv: pd.DataFrame,
        idx: int,
        method: str = "auto",
        fixed_bps: float = 10.0,
    ) -> float:
        """
        Estimate spread using the configured method.

        Parameters
        ----------
        ohlcv : pd.DataFrame
            OHLCV data.
        idx : int
            Current bar index.
        method : str
            "auto" (Corwin-Schultz) or "fixed".
        fixed_bps : float
            Fixed spread in basis points (used when method="fixed").

        Returns
        -------
        float
            Estimated half-spread as a fraction for one side.
        """
        if method == "fixed":
            return fixed_bps / 10_000

        # Try Corwin-Schultz
        spread = self.corwin_schultz(ohlcv, idx)

        # If CS returns very small, supplement with empirical
        if spread < 0.0001 and "Volume" in ohlcv.columns:
            price = ohlcv["Close"].values[idx]
            vol = ohlcv["Volume"].values[idx]
            adv_dollars = price * vol
            spread = max(spread, self.empirical_fallback(adv_dollars))

        return spread


class ImpactEstimator:
    """
    Square-root market impact model (Almgren-Chriss simplified).

    Impact = η × σ_daily × √(participation_rate)
    participation_rate = trade_shares / ADV_shares
    """

    @staticmethod
    def compute(
        daily_volatility: float,
        adv_shares: float,
        trade_usd: float,
        price: float,
        eta: float = 0.1,
    ) -> float:
        """
        Compute expected market impact.

        Parameters
        ----------
        daily_volatility : float
            Daily return volatility (e.g. 0.02 = 2%).
        adv_shares : float
            Average daily volume in shares.
        trade_usd : float
            Notional trade size in USD.
        price : float
            Current price per share.
        eta : float
            Impact coefficient (typically 0.05–0.20).

        Returns
        -------
        float
            Market impact as a fraction of price.
        """
        if price <= 0 or adv_shares <= 0:
            return 0.0

        trade_shares = trade_usd / price
        participation_rate = trade_shares / adv_shares

        # Clamp participation rate (extremely large trades are unrealistic)
        participation_rate = min(participation_rate, 1.0)

        impact = eta * daily_volatility * math.sqrt(participation_rate)

        # Clamp to reasonable range [0, 500 bps]
        return max(0.0, min(impact, 0.05))
