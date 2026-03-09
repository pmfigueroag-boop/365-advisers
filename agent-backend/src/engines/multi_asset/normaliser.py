"""src/engines/multi_asset/normaliser.py — Return normalisation."""
from __future__ import annotations
import numpy as np
import logging

logger = logging.getLogger("365advisers.multi_asset.normaliser")


class ReturnNormaliser:
    """Normalise price series to returns."""

    @staticmethod
    def simple_returns(prices: list[float]) -> list[float]:
        """Compute simple returns: (P_t - P_{t-1}) / P_{t-1}."""
        arr = np.array(prices, dtype=np.float64)
        ret = np.diff(arr) / arr[:-1]
        return ret.tolist()

    @staticmethod
    def log_returns(prices: list[float]) -> list[float]:
        """Compute log returns: ln(P_t / P_{t-1})."""
        arr = np.array(prices, dtype=np.float64)
        ret = np.diff(np.log(arr))
        return ret.tolist()

    @staticmethod
    def excess_returns(returns: list[float], risk_free_daily: float = 0.0) -> list[float]:
        """Subtract risk-free rate from returns."""
        return [r - risk_free_daily for r in returns]

    @staticmethod
    def align_series(series_dict: dict[str, list[float]]) -> dict[str, list[float]]:
        """Align multiple return series to the shortest common length."""
        if not series_dict:
            return {}
        min_len = min(len(s) for s in series_dict.values())
        return {k: v[:min_len] for k, v in series_dict.items()}

    @staticmethod
    def currency_adjust(returns: list[float], fx_returns: list[float]) -> list[float]:
        """Adjust returns for FX changes: r_adj ≈ r_asset + r_fx."""
        min_len = min(len(returns), len(fx_returns))
        return [returns[i] + fx_returns[i] for i in range(min_len)]
