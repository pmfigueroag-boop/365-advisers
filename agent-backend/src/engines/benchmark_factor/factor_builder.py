"""
src/engines/benchmark_factor/factor_builder.py
──────────────────────────────────────────────────────────────────────────────
Constructs factor return series from ETF proxy data.

Factors:
  MKT  = R_SPY (market excess return; risk-free ≈ 0)
  SMB  = R_IWM − R_SPY   (Small Minus Big)
  HML  = R_IWD − R_IWF   (High Minus Low: Value − Growth)
  UMD  = R_MTUM − R_SPY  (Momentum minus Market)
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.engines.benchmark_factor.models import FactorTickers

logger = logging.getLogger("365advisers.benchmark_factor.factor_builder")


class FactorBuilder:
    """
    Build daily factor return series from ETF OHLCV data.

    Usage::

        builder = FactorBuilder()
        factor_df = builder.build(ohlcv_data, tickers)
    """

    def build(
        self,
        ohlcv_data: dict[str, pd.DataFrame],
        tickers: FactorTickers | None = None,
    ) -> pd.DataFrame:
        """
        Construct factor return matrix.

        Parameters
        ----------
        ohlcv_data : dict[str, pd.DataFrame]
            OHLCV data keyed by ticker.
        tickers : FactorTickers | None
            ETF proxy configuration.

        Returns
        -------
        pd.DataFrame
            Columns: MKT, SMB, HML, UMD. Index: DatetimeIndex.
            Each value is a daily return.
        """
        t = tickers or FactorTickers()
        returns = self._compute_returns(ohlcv_data)

        r_market = returns.get(t.market, pd.Series(dtype=float))
        r_small = returns.get(t.small_cap, pd.Series(dtype=float))
        r_value = returns.get(t.value, pd.Series(dtype=float))
        r_growth = returns.get(t.growth, pd.Series(dtype=float))
        r_momentum = returns.get(t.momentum, pd.Series(dtype=float))

        # Align all series to common dates
        all_series = {
            "MKT": r_market,
            "SMB_small": r_small,
            "SMB_big": r_market,
            "HML_value": r_value,
            "HML_growth": r_growth,
            "UMD_mom": r_momentum,
            "UMD_market": r_market,
        }
        df = pd.DataFrame(all_series).dropna()

        if df.empty:
            logger.warning("FACTOR-BUILDER: No overlapping dates for factor construction")
            return pd.DataFrame(columns=["MKT", "SMB", "HML", "UMD"])

        factor_df = pd.DataFrame({
            "MKT": df["MKT"],
            "SMB": df["SMB_small"] - df["SMB_big"],
            "HML": df["HML_value"] - df["HML_growth"],
            "UMD": df["UMD_mom"] - df["UMD_market"],
        }, index=df.index)

        logger.info(
            "FACTOR-BUILDER: Built %d-day factor matrix (%d → %s)",
            len(factor_df),
            len(factor_df),
            factor_df.index[-1].strftime("%Y-%m-%d") if len(factor_df) > 0 else "N/A",
        )
        return factor_df

    @staticmethod
    def _compute_returns(
        ohlcv_data: dict[str, pd.DataFrame],
    ) -> dict[str, pd.Series]:
        """Compute daily returns from Close prices."""
        returns: dict[str, pd.Series] = {}
        for ticker, df in ohlcv_data.items():
            if df is not None and not df.empty and "Close" in df.columns:
                r = df["Close"].pct_change().dropna()
                if not r.empty:
                    returns[ticker] = r
        return returns

    def get_factor_at_date(
        self,
        factor_df: pd.DataFrame,
        target_date: object,
        window: int = 20,
    ) -> dict[str, float] | None:
        """
        Get cumulative factor returns over a forward window starting at date.

        Parameters
        ----------
        factor_df : pd.DataFrame
            Factor return matrix.
        target_date : date-like
            Start date.
        window : int
            Number of trading days forward.

        Returns
        -------
        dict[str, float] | None
            {MKT: cum_return, SMB: ..., HML: ..., UMD: ...}
        """
        ts = pd.Timestamp(target_date)
        idx = factor_df.index.get_indexer([ts], method="pad")
        if len(idx) == 0 or idx[0] < 0:
            return None

        start = int(idx[0])
        end = min(start + window, len(factor_df))
        if end <= start:
            return None

        chunk = factor_df.iloc[start:end]
        cum = {}
        for col in ["MKT", "SMB", "HML", "UMD"]:
            if col in chunk.columns:
                cum[col] = float((1 + chunk[col]).prod() - 1)
            else:
                cum[col] = 0.0
        return cum
