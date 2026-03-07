"""
src/engines/concept_drift/detectors.py
──────────────────────────────────────────────────────────────────────────────
Statistical drift detectors.

Three independent detectors:
  1. DistributionShiftDetector — Kolmogorov-Smirnov two-sample test
  2. CorrelationBreakdownDetector — rolling Pearson correlation decay
  3. RegimeShiftDetector — CUSUM change-point detection
"""

from __future__ import annotations

import logging
import math

import numpy as np

from src.engines.concept_drift.models import DetectorType, DriftConfig, DriftDetection

logger = logging.getLogger("365advisers.concept_drift.detectors")


# ── Pure-numpy KS two-sample test ─────────────────────────────────────────────

def _ks_2samp(data1: list[float], data2: list[float]) -> tuple[float, float]:
    """
    Pure-numpy Kolmogorov-Smirnov two-sample test.

    Returns (ks_statistic, p_value_approx).
    """
    a = np.sort(data1)
    b = np.sort(data2)
    n1 = len(a)
    n2 = len(b)

    combined = np.concatenate([a, b])
    combined.sort()

    cdf1 = np.searchsorted(a, combined, side="right") / n1
    cdf2 = np.searchsorted(b, combined, side="right") / n2

    ks_stat = float(np.max(np.abs(cdf1 - cdf2)))

    # Asymptotic p-value (Kolmogorov distribution)
    en = np.sqrt(n1 * n2 / (n1 + n2))
    lam = (en + 0.12 + 0.11 / en) * ks_stat

    if lam < 0.001:
        p = 1.0
    else:
        # Kolmogorov series approximation
        j = np.arange(1, 101)
        p = float(2.0 * np.sum((-1.0) ** (j - 1) * np.exp(-2.0 * j ** 2 * lam ** 2)))
        p = max(0.0, min(1.0, p))

    return ks_stat, p


class DistributionShiftDetector:
    """
    Kolmogorov-Smirnov two-sample test.

    Compares the distribution of recent returns against baseline returns.
    A low p-value indicates the distributions are significantly different.
    """

    def detect(
        self,
        baseline_returns: list[float],
        recent_returns: list[float],
        config: DriftConfig,
    ) -> DriftDetection:
        if len(baseline_returns) < config.min_samples or len(recent_returns) < config.min_samples:
            return DriftDetection(
                detector=DetectorType.DISTRIBUTION_SHIFT.value,
                detected=False,
                detail="Insufficient samples",
            )

        ks_stat, p_value = _ks_2samp(baseline_returns, recent_returns)

        detected = p_value < config.ks_alpha

        detail = f"KS stat={ks_stat:.4f}, p={p_value:.6f}"
        if p_value < config.ks_critical_alpha:
            detail += " [CRITICAL distribution shift]"
        elif detected:
            detail += " [distribution shift detected]"

        return DriftDetection(
            detector=DetectorType.DISTRIBUTION_SHIFT.value,
            detected=detected,
            statistic=round(ks_stat, 6),
            p_value=round(p_value, 8),
            threshold=config.ks_alpha,
            detail=detail,
        )


class CorrelationBreakdownDetector:
    """
    Rolling Pearson correlation decay detector.

    Measures whether the correlation between signal values and
    forward returns has significantly weakened.
    """

    def detect(
        self,
        baseline_signals: list[float],
        baseline_returns: list[float],
        recent_signals: list[float],
        recent_returns: list[float],
        config: DriftConfig,
    ) -> DriftDetection:
        if (
            len(baseline_signals) < config.min_samples
            or len(recent_signals) < config.min_samples
        ):
            return DriftDetection(
                detector=DetectorType.CORRELATION_BREAKDOWN.value,
                detected=False,
                detail="Insufficient samples",
            )

        # Ensure matching lengths
        n_base = min(len(baseline_signals), len(baseline_returns))
        n_recent = min(len(recent_signals), len(recent_returns))

        corr_baseline = self._pearson(
            baseline_signals[:n_base], baseline_returns[:n_base],
        )
        corr_recent = self._pearson(
            recent_signals[:n_recent], recent_returns[:n_recent],
        )

        drop = abs(corr_baseline - corr_recent)
        detected = drop > config.corr_breakdown_threshold

        detail = (
            f"corr_baseline={corr_baseline:.4f}, corr_recent={corr_recent:.4f}, "
            f"drop={drop:.4f}"
        )
        if detected:
            detail += " [correlation breakdown]"

        return DriftDetection(
            detector=DetectorType.CORRELATION_BREAKDOWN.value,
            detected=detected,
            statistic=round(drop, 6),
            threshold=config.corr_breakdown_threshold,
            detail=detail,
        )

    @staticmethod
    def _pearson(x: list[float], y: list[float]) -> float:
        """Compute Pearson correlation coefficient."""
        if len(x) < 3:
            return 0.0
        arr_x = np.array(x)
        arr_y = np.array(y)
        std_x = float(arr_x.std())
        std_y = float(arr_y.std())
        if std_x < 1e-12 or std_y < 1e-12:
            return 0.0
        corr = float(np.corrcoef(arr_x, arr_y)[0, 1])
        return corr if not math.isnan(corr) else 0.0


class RegimeShiftDetector:
    """
    CUSUM (Cumulative Sum) change-point detector.

    Monitors the cumulative deviation of returns from a baseline mean.
    When the CUSUM statistic exceeds the threshold h, a regime shift
    is detected.
    """

    def detect(
        self,
        returns: list[float],
        config: DriftConfig,
    ) -> DriftDetection:
        if len(returns) < config.min_samples:
            return DriftDetection(
                detector=DetectorType.REGIME_SHIFT.value,
                detected=False,
                detail="Insufficient samples",
            )

        arr = np.array(returns)

        # Baseline mean from first half
        n = len(arr)
        split = max(config.min_samples, n // 2)
        mu_0 = float(arr[:split].mean())
        sigma = float(arr[:split].std(ddof=1))

        if sigma < 1e-12:
            return DriftDetection(
                detector=DetectorType.REGIME_SHIFT.value,
                detected=False,
                detail="Zero variance in baseline",
            )

        # Standardised CUSUM
        k = config.cusum_k
        h = config.cusum_h

        s_pos = 0.0
        s_neg = 0.0
        max_s = 0.0
        detected = False

        for i in range(split, n):
            z = (arr[i] - mu_0) / sigma
            s_pos = max(0, s_pos + z - k)
            s_neg = max(0, s_neg - z - k)
            max_s = max(max_s, s_pos, s_neg)
            if s_pos > h or s_neg > h:
                detected = True

        detail = f"CUSUM max={max_s:.4f}, threshold={h}"
        if detected:
            detail += " [regime shift detected]"

        return DriftDetection(
            detector=DetectorType.REGIME_SHIFT.value,
            detected=detected,
            statistic=round(max_s, 6),
            threshold=h,
            detail=detail,
        )
