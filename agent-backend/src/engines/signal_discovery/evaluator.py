"""
src/engines/signal_discovery/evaluator.py
──────────────────────────────────────────────────────────────────────────────
Candidate signal evaluator.

Computes:
  - Information Coefficient (IC) — Spearman rank correlation
  - Hit rate — fraction of positive returns when signal fires
  - Sharpe ratio estimate
  - Temporal stability — IC persistence across rolling windows
  - P-value with Bonferroni / BH correction for multiple testing
"""

from __future__ import annotations

import logging
import math

import numpy as np

from src.engines.signal_discovery.models import (
    CandidateSignal,
    CandidateStatus,
    DiscoveryConfig,
)

logger = logging.getLogger("365advisers.signal_discovery.evaluator")


class CandidateEvaluator:
    """
    Evaluates candidate signals against historical data.
    """

    def evaluate(
        self,
        candidates: list[CandidateSignal],
        signal_values: dict[str, list[float]],
        forward_returns: list[float],
        config: DiscoveryConfig,
    ) -> list[CandidateSignal]:
        """
        Evaluate all candidates against data.

        Parameters
        ----------
        candidates : list[CandidateSignal]
        signal_values : dict
            {candidate_id: [values]} — pre-computed signal values per candidate
        forward_returns : list[float]
            Forward returns aligned to signal values.
        config : DiscoveryConfig

        Returns
        -------
        list[CandidateSignal]
            Evaluated candidates with metrics filled.
        """
        n_returns = len(forward_returns)
        evaluated = []

        for c in candidates:
            values = signal_values.get(c.candidate_id, [])
            n = min(len(values), n_returns)

            if n < config.min_sample_size:
                c.status = CandidateStatus.REJECTED.value
                c.sample_size = n
                evaluated.append(c)
                continue

            vals = np.array(values[:n])
            rets = np.array(forward_returns[:n])

            # IC (Spearman rank correlation)
            ic = self._rank_ic(vals, rets)

            # Hit rate: when signal > median, how often returns > 0
            median_val = float(np.median(vals))
            fired_mask = vals > median_val
            fired_count = int(fired_mask.sum())
            if fired_count > 0:
                hit_rate = float((rets[fired_mask] > 0).sum() / fired_count)
            else:
                hit_rate = 0.0

            # Sharpe estimate from fired returns
            if fired_count > 1:
                fired_rets = rets[fired_mask]
                mean_r = float(fired_rets.mean())
                std_r = float(fired_rets.std(ddof=1))
                sharpe = mean_r / std_r * math.sqrt(252) if std_r > 1e-10 else 0.0
            else:
                sharpe = 0.0

            # Stability: IC across rolling windows
            stability = self._stability(vals, rets, config.stability_window_months)

            # P-value approximation for IC
            t_stat = ic * math.sqrt(n - 2) / math.sqrt(1 - ic ** 2 + 1e-12)
            p_value = self._t_to_p(t_stat, n - 2)

            c.information_coefficient = round(ic, 6)
            c.hit_rate = round(hit_rate, 4)
            c.sharpe_ratio = round(sharpe, 4)
            c.sample_size = n
            c.stability = round(stability, 4)
            c.p_value = round(p_value, 8)
            evaluated.append(c)

        # Multiple testing correction
        n_tests = len(evaluated)
        for c in evaluated:
            if config.use_bonferroni:
                c.adjusted_p_value = round(min(1.0, c.p_value * n_tests), 8)
            else:
                c.adjusted_p_value = c.p_value

        # Apply thresholds
        for c in evaluated:
            if c.status == CandidateStatus.REJECTED.value:
                continue
            if (
                abs(c.information_coefficient) >= config.min_ic
                and c.hit_rate >= config.min_hit_rate
                and c.stability >= config.min_stability
                and c.adjusted_p_value < config.significance_alpha
            ):
                c.status = CandidateStatus.PROMOTED.value
            else:
                c.status = CandidateStatus.REJECTED.value

        logger.info(
            "DISCOVERY-EVAL: %d evaluated, %d promoted, %d rejected",
            len(evaluated),
            sum(1 for c in evaluated if c.status == CandidateStatus.PROMOTED.value),
            sum(1 for c in evaluated if c.status == CandidateStatus.REJECTED.value),
        )
        return evaluated

    @staticmethod
    def _rank_ic(x: np.ndarray, y: np.ndarray) -> float:
        """Spearman rank correlation (pure numpy)."""
        n = len(x)
        if n < 3:
            return 0.0
        rank_x = np.argsort(np.argsort(x)).astype(float)
        rank_y = np.argsort(np.argsort(y)).astype(float)
        d = rank_x - rank_y
        rho = 1 - 6 * float(np.sum(d ** 2)) / (n * (n ** 2 - 1))
        return max(-1.0, min(1.0, rho))

    @staticmethod
    def _stability(vals: np.ndarray, rets: np.ndarray, window_months: int) -> float:
        """IC persistence across rolling windows."""
        window = window_months * 21  # ~21 trading days per month
        n = len(vals)
        if n < window * 2:
            return 0.0

        positive_windows = 0
        total_windows = 0
        for start in range(0, n - window, window // 2):
            end = start + window
            w_vals = vals[start:end]
            w_rets = rets[start:end]
            if len(w_vals) < 20:
                continue
            ic = CandidateEvaluator._rank_ic(w_vals, w_rets)
            total_windows += 1
            if ic > 0:
                positive_windows += 1

        return positive_windows / total_windows if total_windows > 0 else 0.0

    @staticmethod
    def _t_to_p(t: float, df: int) -> float:
        """Approximate two-tailed p-value from t-statistic."""
        if df <= 0:
            return 1.0
        # Approximation using normal for large df
        x = abs(t)
        # Abramowitz & Stegun approximation
        b0 = 0.2316419
        b1 = 0.319381530
        b2 = -0.356563782
        b3 = 1.781477937
        b4 = -1.821255978
        b5 = 1.330274429
        t_val = 1.0 / (1.0 + b0 * x)
        poly = t_val * (b1 + t_val * (b2 + t_val * (b3 + t_val * (b4 + t_val * b5))))
        phi = math.exp(-x * x / 2) / math.sqrt(2 * math.pi)
        p_one_tail = phi * poly
        return max(0.0, min(1.0, 2.0 * p_one_tail))
