"""
src/engines/validation/statistical_validator.py
──────────────────────────────────────────────────────────────────────────────
Statistical Significance Testing for Alpha Validation (AVS V2).

Tests:
  1. Alpha t-statistic & p-value
  2. Bootstrap resampling (1000 iterations)
  3. Confidence intervals (95% CI)
  4. Noise injection robustness
  5. Parameter perturbation stability
  6. Subsample consistency (by sector, by period, by cap)
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SignificanceResult:
    """Result of a statistical significance test."""
    test_name: str
    n_observations: int = 0
    mean_return: float = 0.0
    std_return: float = 0.0
    t_stat: float = 0.0
    p_value: float = 1.0
    ci_lower: float = 0.0
    ci_upper: float = 0.0
    is_significant: bool = False   # p < 0.05


@dataclass
class BootstrapResult:
    """Result of bootstrap resampling."""
    n_iterations: int = 0
    mean_of_means: float = 0.0
    ci_lower: float = 0.0     # 2.5th percentile
    ci_upper: float = 0.0     # 97.5th percentile
    pct_positive: float = 0.0  # % of bootstraps with positive mean
    is_robust: bool = False    # CI doesn't include zero


@dataclass
class RobustnessResult:
    """Result of a robustness test."""
    test_name: str
    baseline_alpha: float = 0.0
    perturbed_alpha: float = 0.0
    degradation_pct: float = 0.0
    is_robust: bool = False    # degradation < 50%
    details: dict = field(default_factory=dict)


@dataclass
class SubsampleResult:
    """Result of subsample analysis."""
    subsample_name: str
    n_observations: int = 0
    mean_return: float = 0.0
    hit_rate: float = 0.0
    sharpe: float = 0.0
    is_consistent: bool = False  # positive alpha in subsample


@dataclass
class StatisticalReport:
    """Full statistical validation report."""
    # Core significance
    alpha_significance: SignificanceResult | None = None
    excess_significance: SignificanceResult | None = None

    # Bootstrap
    bootstrap: BootstrapResult | None = None

    # Robustness
    noise_injection: RobustnessResult | None = None
    param_perturbation: list[RobustnessResult] = field(default_factory=list)

    # Subsamples
    subsamples: list[SubsampleResult] = field(default_factory=list)

    # Cross-sectional
    quintile_returns: dict[int, float] = field(default_factory=dict)
    long_short_spread: float = 0.0
    monotonicity_score: float = 0.0

    # Decay analysis
    decay_by_horizon: dict[str, float] = field(default_factory=dict)

    # Final verdict
    verdict: str = "UNKNOWN"  # NO_ALPHA, WEAK, VALID, INSTITUTIONAL


class StatisticalValidator:
    """
    Comprehensive statistical validation of alpha.

    Takes the output of InstitutionalBacktest and runs all
    significance and robustness tests.
    """

    def validate(self, report: Any) -> StatisticalReport:
        """Run all statistical tests on an InstitutionalReport."""
        stat = StatisticalReport()

        # Extract OOS buy trade returns
        oos_returns_20d = [
            t.fwd_return_20d for t in report.all_trades
            if t.is_oos and t.composite_score > 0.35 and t.fwd_return_20d is not None
        ]

        # Benchmark returns (all OOS observations)
        all_oos_returns = [
            t.fwd_return_20d for t in report.all_trades
            if t.is_oos and t.fwd_return_20d is not None
        ]

        # Excess returns
        benchmark_mean = sum(all_oos_returns) / len(all_oos_returns) if all_oos_returns else 0.0
        excess_returns = [r - benchmark_mean for r in oos_returns_20d]

        # ── 1. Alpha t-stat / p-value ────────────────────────────────────
        if oos_returns_20d:
            stat.alpha_significance = self._compute_t_test(
                oos_returns_20d, "Alpha (raw OOS returns)",
            )
        if excess_returns:
            stat.excess_significance = self._compute_t_test(
                excess_returns, "Excess Return vs Benchmark",
            )

        # ── 2. Bootstrap resampling ──────────────────────────────────────
        if excess_returns:
            stat.bootstrap = self._bootstrap(excess_returns, n_iter=1000)

        # ── 3. Noise injection ───────────────────────────────────────────
        stat.noise_injection = self._noise_injection_test(report)

        # ── 4. Parameter perturbation ────────────────────────────────────
        stat.param_perturbation = self._param_perturbation_test(report)

        # ── 5. Subsample analysis ────────────────────────────────────────
        stat.subsamples = self._subsample_analysis(report)

        # ── 6. Cross-sectional (quintile) analysis ───────────────────────
        if report.cross_sectional:
            quintiles = self._quintile_analysis(report.cross_sectional)
            stat.quintile_returns = quintiles["returns"]
            stat.long_short_spread = quintiles["long_short_spread"]
            stat.monotonicity_score = quintiles["monotonicity"]

        # ── 7. Decay by horizon ──────────────────────────────────────────
        stat.decay_by_horizon = self._decay_analysis(report)

        # ── 8. Final verdict ─────────────────────────────────────────────
        stat.verdict = self._compute_verdict(stat)

        return stat

    # ── Core Tests ───────────────────────────────────────────────────────────

    @staticmethod
    def _compute_t_test(
        returns: list[float],
        name: str,
    ) -> SignificanceResult:
        """Compute t-statistic and p-value for mean > 0."""
        n = len(returns)
        if n < 2:
            return SignificanceResult(test_name=name, n_observations=n)

        mean_r = sum(returns) / n
        var_r = sum((r - mean_r) ** 2 for r in returns) / (n - 1)
        std_r = var_r ** 0.5

        t_stat = mean_r / (std_r / (n ** 0.5)) if std_r > 0 else 0.0

        # Approximate p-value using normal distribution (valid for n > 30)
        p_value = _norm_sf(abs(t_stat)) * 2  # two-tailed

        # 95% CI
        z_95 = 1.96
        se = std_r / (n ** 0.5)
        ci_lower = mean_r - z_95 * se
        ci_upper = mean_r + z_95 * se

        return SignificanceResult(
            test_name=name,
            n_observations=n,
            mean_return=mean_r,
            std_return=std_r,
            t_stat=t_stat,
            p_value=p_value,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            is_significant=p_value < 0.05,
        )

    @staticmethod
    def _bootstrap(
        returns: list[float],
        n_iter: int = 1000,
        seed: int = 42,
    ) -> BootstrapResult:
        """Bootstrap resampling of mean return."""
        rng = random.Random(seed)
        n = len(returns)
        if n < 5:
            return BootstrapResult()

        means = []
        for _ in range(n_iter):
            sample = [rng.choice(returns) for _ in range(n)]
            means.append(sum(sample) / n)

        means.sort()
        ci_lower = means[int(n_iter * 0.025)]
        ci_upper = means[int(n_iter * 0.975)]
        pct_positive = sum(1 for m in means if m > 0) / n_iter

        return BootstrapResult(
            n_iterations=n_iter,
            mean_of_means=sum(means) / n_iter,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            pct_positive=pct_positive,
            is_robust=ci_lower > 0,  # entire 95% CI is positive
        )

    def _noise_injection_test(self, report: Any) -> RobustnessResult:
        """
        Add Gaussian noise to composite scores and measure alpha degradation.

        Methodology: add N(0, 0.05) to each composite score, re-classify
        trades, and re-compute excess return.
        """
        rng = random.Random(42)
        noise_std = 0.05  # 5% noise

        oos_trades = [t for t in report.all_trades if t.is_oos]
        if not oos_trades:
            return RobustnessResult(test_name="Noise Injection")

        # Baseline alpha
        buy_trades = [t for t in oos_trades if t.composite_score > 0.35]
        baseline_rets = [t.fwd_return_20d for t in buy_trades if t.fwd_return_20d is not None]
        all_rets = [t.fwd_return_20d for t in oos_trades if t.fwd_return_20d is not None]
        bench = sum(all_rets) / len(all_rets) if all_rets else 0.0
        baseline_alpha = (sum(baseline_rets) / len(baseline_rets) - bench) if baseline_rets else 0.0

        # Noisy alpha
        noisy_buy = [
            t for t in oos_trades
            if (t.composite_score + rng.gauss(0, noise_std)) > 0.35
        ]
        noisy_rets = [t.fwd_return_20d for t in noisy_buy if t.fwd_return_20d is not None]
        noisy_alpha = (sum(noisy_rets) / len(noisy_rets) - bench) if noisy_rets else 0.0

        degradation = 0.0
        if baseline_alpha != 0:
            degradation = 1.0 - (noisy_alpha / baseline_alpha)

        return RobustnessResult(
            test_name="Noise Injection (σ=0.05)",
            baseline_alpha=baseline_alpha,
            perturbed_alpha=noisy_alpha,
            degradation_pct=degradation,
            is_robust=abs(degradation) < 0.5,
            details={"noise_std": noise_std, "baseline_trades": len(baseline_rets), "noisy_trades": len(noisy_rets)},
        )

    def _param_perturbation_test(self, report: Any) -> list[RobustnessResult]:
        """Vary BUY threshold ±20% and measure stability."""
        results = []
        base_threshold = 0.35

        oos_trades = [t for t in report.all_trades if t.is_oos]
        all_rets = [t.fwd_return_20d for t in oos_trades if t.fwd_return_20d is not None]
        bench = sum(all_rets) / len(all_rets) if all_rets else 0.0

        # Baseline
        base_buy = [t for t in oos_trades if t.composite_score > base_threshold]
        base_rets = [t.fwd_return_20d for t in base_buy if t.fwd_return_20d is not None]
        baseline_alpha = (sum(base_rets) / len(base_rets) - bench) if base_rets else 0.0

        for delta_pct in [-0.20, -0.10, 0.10, 0.20]:
            perturbed_threshold = base_threshold * (1 + delta_pct)
            pert_buy = [t for t in oos_trades if t.composite_score > perturbed_threshold]
            pert_rets = [t.fwd_return_20d for t in pert_buy if t.fwd_return_20d is not None]
            pert_alpha = (sum(pert_rets) / len(pert_rets) - bench) if pert_rets else 0.0

            degradation = 0.0
            if baseline_alpha != 0:
                degradation = 1.0 - (pert_alpha / baseline_alpha)

            results.append(RobustnessResult(
                test_name=f"Threshold {delta_pct:+.0%} ({perturbed_threshold:.3f})",
                baseline_alpha=baseline_alpha,
                perturbed_alpha=pert_alpha,
                degradation_pct=degradation,
                is_robust=abs(degradation) < 0.5,
                details={"threshold": perturbed_threshold, "n_trades": len(pert_rets)},
            ))

        return results

    def _subsample_analysis(self, report: Any) -> list[SubsampleResult]:
        """Split OOS trades by sector and time period."""
        results = []
        oos_buy = [
            t for t in report.all_trades
            if t.is_oos and t.composite_score > 0.35 and t.fwd_return_20d is not None
        ]

        if not oos_buy:
            return results

        # By sector
        sectors: dict[str, list] = {}
        for t in oos_buy:
            sec = t.sector or "Unknown"
            sectors.setdefault(sec, []).append(t.fwd_return_20d)

        for sec, rets in sorted(sectors.items()):
            if len(rets) < 3:
                continue
            mean_r = sum(rets) / len(rets)
            hit = sum(1 for r in rets if r > 0) / len(rets)
            std_r = (sum((r - mean_r)**2 for r in rets) / max(len(rets) - 1, 1)) ** 0.5
            sharpe = mean_r / std_r if std_r > 0 else 0.0

            results.append(SubsampleResult(
                subsample_name=f"Sector: {sec}",
                n_observations=len(rets),
                mean_return=mean_r,
                hit_rate=hit,
                sharpe=sharpe,
                is_consistent=mean_r > 0,
            ))

        # By time period (first half / second half of OOS)
        sorted_trades = sorted(oos_buy, key=lambda t: t.eval_date)
        mid = len(sorted_trades) // 2
        for label, subset in [("Early OOS", sorted_trades[:mid]), ("Late OOS", sorted_trades[mid:])]:
            rets = [t.fwd_return_20d for t in subset]
            if len(rets) < 3:
                continue
            mean_r = sum(rets) / len(rets)
            hit = sum(1 for r in rets if r > 0) / len(rets)
            std_r = (sum((r - mean_r)**2 for r in rets) / max(len(rets) - 1, 1)) ** 0.5

            results.append(SubsampleResult(
                subsample_name=f"Period: {label}",
                n_observations=len(rets),
                mean_return=mean_r,
                hit_rate=hit,
                sharpe=mean_r / std_r if std_r > 0 else 0.0,
                is_consistent=mean_r > 0,
            ))

        return results

    @staticmethod
    def _quintile_analysis(cross_sectional: list[dict]) -> dict:
        """Analyze returns by quintile rank."""
        quintile_rets: dict[int, list[float]] = {q: [] for q in range(1, 6)}

        for obs in cross_sectional:
            if obs.get("is_oos"):
                q = obs.get("quintile", 0)
                if q in quintile_rets:
                    quintile_rets[q].append(obs.get("fwd_return_20d", 0.0))

        avg_returns = {}
        for q in range(1, 6):
            rets = quintile_rets[q]
            avg_returns[q] = sum(rets) / len(rets) if rets else 0.0

        # Long-short spread: Q1 (best) - Q5 (worst)
        long_short = avg_returns.get(1, 0.0) - avg_returns.get(5, 0.0)

        # Monotonicity: are quintile returns monotonically decreasing?
        vals = [avg_returns.get(q, 0.0) for q in range(1, 6)]
        decreasing_pairs = sum(1 for i in range(4) if vals[i] >= vals[i+1])
        monotonicity = decreasing_pairs / 4.0  # 1.0 = perfect

        return {
            "returns": avg_returns,
            "long_short_spread": long_short,
            "monotonicity": monotonicity,
        }

    @staticmethod
    def _decay_analysis(report: Any) -> dict[str, float]:
        """Measure average return by horizon for BUY trades."""
        oos_buy = [
            t for t in report.all_trades
            if t.is_oos and t.composite_score > 0.35
        ]
        if not oos_buy:
            return {}

        horizons = {
            "T+5": [t.fwd_return_5d for t in oos_buy if t.fwd_return_5d is not None],
            "T+10": [t.fwd_return_10d for t in oos_buy if t.fwd_return_10d is not None],
            "T+20": [t.fwd_return_20d for t in oos_buy if t.fwd_return_20d is not None],
            "T+60": [t.fwd_return_60d for t in oos_buy if t.fwd_return_60d is not None],
        }

        return {
            h: sum(rets) / len(rets) if rets else 0.0
            for h, rets in horizons.items()
        }

    @staticmethod
    def _compute_verdict(stat: StatisticalReport) -> str:
        """
        Compute final verdict based on all statistical evidence.

        Criteria:
          🟢 INSTITUTIONAL: t-stat > 2.5, bootstrap robust, L/S spread > 2%,
                            consistent across subsamples
          ✅ VALID:          t-stat > 2.0, bootstrap robust,
                            positive alpha in most subsamples
          ⚠️ WEAK:          t-stat > 1.5, some positive evidence
          ❌ NO_ALPHA:       t-stat < 1.5 or alpha not significant
        """
        score = 0

        # t-stat contribution
        if stat.excess_significance:
            t = stat.excess_significance.t_stat
            if t > 2.5: score += 3
            elif t > 2.0: score += 2
            elif t > 1.5: score += 1

        # Bootstrap contribution
        if stat.bootstrap and stat.bootstrap.is_robust:
            score += 2
        elif stat.bootstrap and stat.bootstrap.pct_positive > 0.9:
            score += 1

        # Cross-sectional contribution
        if stat.long_short_spread > 0.03:  # 3% L/S spread
            score += 2
        elif stat.long_short_spread > 0.01:
            score += 1

        # Monotonicity
        if stat.monotonicity_score >= 0.75:
            score += 1

        # Subsample consistency
        if stat.subsamples:
            consistent = sum(1 for s in stat.subsamples if s.is_consistent)
            ratio = consistent / len(stat.subsamples)
            if ratio >= 0.8: score += 2
            elif ratio >= 0.6: score += 1

        # Robustness
        if stat.noise_injection and stat.noise_injection.is_robust:
            score += 1

        # Verdict
        if score >= 10:
            return "INSTITUTIONAL"
        elif score >= 7:
            return "VALID"
        elif score >= 4:
            return "WEAK"
        else:
            return "NO_ALPHA"


# ── Helper: Normal distribution survival function ────────────────────────────

def _norm_sf(x: float) -> float:
    """P(Z > x) for standard normal, using error function approximation."""
    return 0.5 * math.erfc(x / math.sqrt(2))
