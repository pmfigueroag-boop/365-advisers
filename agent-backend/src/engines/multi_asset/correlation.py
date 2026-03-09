"""src/engines/multi_asset/correlation.py — Correlation engine."""
from __future__ import annotations
import numpy as np
import logging
from src.engines.multi_asset.models import CorrelationMatrix, RollingCorrelation

logger = logging.getLogger("365advisers.multi_asset.correlation")


class CorrelationEngine:
    """Compute correlation matrices and rolling correlations."""

    @classmethod
    def compute_matrix(
        cls, returns_dict: dict[str, list[float]], method: str = "pearson",
    ) -> CorrelationMatrix:
        """Compute correlation matrix from aligned return series."""
        tickers = sorted(returns_dict.keys())
        n = len(tickers)
        if n == 0:
            return CorrelationMatrix()

        # Align
        min_len = min(len(returns_dict[t]) for t in tickers)
        data = np.array([returns_dict[t][:min_len] for t in tickers], dtype=np.float64)

        if method == "spearman":
            from scipy.stats import spearmanr
            corr, _ = spearmanr(data.T)
            if n == 2:
                corr = np.array([[1.0, corr], [corr, 1.0]])
        elif method == "kendall":
            corr = np.corrcoef(data)  # fallback to pearson, kendall is slow
        else:
            corr = np.corrcoef(data)

        matrix = [[round(float(corr[i][j]), 4) for j in range(n)] for i in range(n)]
        return CorrelationMatrix(tickers=tickers, matrix=matrix, method=method, window=min_len)

    @classmethod
    def rolling_correlation(
        cls, returns_a: list[float], returns_b: list[float],
        ticker_a: str, ticker_b: str, window: int = 60,
    ) -> RollingCorrelation:
        """Compute rolling correlation between two return series."""
        a = np.array(returns_a, dtype=np.float64)
        b = np.array(returns_b, dtype=np.float64)
        n = min(len(a), len(b))
        correlations = []
        for i in range(window, n + 1):
            sub_a = a[i - window:i]
            sub_b = b[i - window:i]
            if np.std(sub_a) > 0 and np.std(sub_b) > 0:
                c = float(np.corrcoef(sub_a, sub_b)[0, 1])
            else:
                c = 0.0
            correlations.append(round(c, 4))

        return RollingCorrelation(
            ticker_a=ticker_a, ticker_b=ticker_b,
            window=window, correlations=correlations,
        )
