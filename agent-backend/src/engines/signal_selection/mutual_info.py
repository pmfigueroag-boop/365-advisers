"""
src/engines/signal_selection/mutual_info.py
──────────────────────────────────────────────────────────────────────────────
Mutual Information estimator using histogram binning.

Captures non-linear dependencies between signal return series
that Pearson correlation cannot detect.
"""

from __future__ import annotations

import logging
import math

import numpy as np

logger = logging.getLogger("365advisers.signal_selection.mutual_info")


class MutualInfoEstimator:
    """
    Estimates normalised mutual information via histogram binning.

    NMI(A, B) = MI(A, B) / min(H(A), H(B))

    Returns value in [0, 1] where 1 = perfect dependence.
    """

    def __init__(self, n_bins: int = 20) -> None:
        self._n_bins = n_bins

    def estimate(
        self,
        returns_a: np.ndarray,
        returns_b: np.ndarray,
    ) -> float:
        """
        Compute normalised mutual information between two return series.

        Parameters
        ----------
        returns_a, returns_b : np.ndarray
            Equal-length arrays of paired returns.

        Returns
        -------
        float
            NMI in [0, 1].
        """
        if len(returns_a) < 5 or len(returns_a) != len(returns_b):
            return 0.0

        n = len(returns_a)
        n_bins = min(self._n_bins, max(3, int(math.sqrt(n))))

        # Build 2D histogram
        hist_2d, edges_a, edges_b = np.histogram2d(
            returns_a, returns_b, bins=n_bins,
        )

        # Marginals
        p_xy = hist_2d / n
        p_x = p_xy.sum(axis=1)
        p_y = p_xy.sum(axis=0)

        # Entropies
        h_x = self._entropy(p_x)
        h_y = self._entropy(p_y)
        h_xy = self._entropy(p_xy.ravel())

        # MI = H(X) + H(Y) - H(X,Y)
        mi = h_x + h_y - h_xy

        # Normalise
        min_h = min(h_x, h_y)
        if min_h < 1e-12:
            return 0.0

        nmi = mi / min_h
        return round(max(0.0, min(nmi, 1.0)), 6)

    @staticmethod
    def _entropy(probs: np.ndarray) -> float:
        """Shannon entropy H = -Σ p log(p)."""
        mask = probs > 0
        if not mask.any():
            return 0.0
        return float(-np.sum(probs[mask] * np.log(probs[mask])))

    def estimate_batch(
        self,
        pairs: list[tuple[np.ndarray, np.ndarray]],
    ) -> list[float]:
        """Estimate NMI for a batch of return pairs."""
        return [self.estimate(a, b) for a, b in pairs]
