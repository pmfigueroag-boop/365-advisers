"""
src/engines/backtesting/perturbation_validator.py
--------------------------------------------------------------------------
Perturbation Robustness Test (PRT) — Noise Sensitivity Analysis.

Injects controlled Gaussian noise into signal excess returns and measures
how much the signal's Sharpe@20d changes.  Fragile signals (high
sensitivity) are likely overfit to specific return magnitudes.

Method
~~~~~~
1. For each signal, collect excess_returns@20d
2. Run N trials:
   - Add noise ~ N(0, noise_pct × std(returns)) to each return
   - Recompute Sharpe on perturbed returns
3. Sensitivity = CoV(perturbed_sharpes) = std / |mean|
4. High sensitivity (> 0.50) → fragile signal

Integration
~~~~~~~~~~~
Produces ``perturbation_sensitivity`` field that can be attached to
``ParameterChange`` for governor gating (Rule 5d).
"""

from __future__ import annotations

import logging
import math
import random
from collections import defaultdict
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from src.engines.backtesting.models import SignalEvent

logger = logging.getLogger("365advisers.backtesting.perturbation")


# ── Contracts ────────────────────────────────────────────────────────────────

class SignalPerturbationResult(BaseModel):
    """Perturbation robustness result for a single signal."""
    signal_id: str
    signal_name: str = ""
    total_events: int = 0
    n_trials: int = 0
    noise_pct: float = 0.0

    # Metrics
    base_sharpe: float = Field(
        0.0, description="Original Sharpe@20d without perturbation",
    )
    mean_perturbed_sharpe: float = Field(
        0.0, description="Mean Sharpe across perturbed trials",
    )
    std_perturbed_sharpe: float = Field(
        0.0, description="StdDev of Sharpe across perturbed trials",
    )
    perturbation_sensitivity: float = Field(
        0.0,
        description="Coefficient of Variation of perturbed Sharpes: "
        "std / |mean|. Higher = more fragile. >0.50 = likely fragile.",
    )
    sharpe_retention: float = Field(
        0.0,
        description="mean_perturbed_sharpe / base_sharpe. "
        "1.0 = robust, <0.5 = fragile.",
    )
    is_fragile: bool = Field(
        False,
        description="True if perturbation_sensitivity > threshold",
    )


class PerturbationReport(BaseModel):
    """Full perturbation robustness test output."""
    signal_results: list[SignalPerturbationResult] = Field(default_factory=list)
    n_trials: int = 0
    noise_pct: float = 0.0
    total_signals: int = 0
    fragile_count: int = Field(0, ge=0)
    robust_count: int = Field(0, ge=0)
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Engine ───────────────────────────────────────────────────────────────────

_REF_WINDOW = 20
_FRAGILE_THRESHOLD = 0.50  # CoV > 50% = fragile
_MIN_EVENTS = 10  # Min events to run perturbation


class PerturbationValidator:
    """
    Perturbation Robustness Test engine.

    Usage::

        validator = PerturbationValidator(n_trials=30, noise_pct=0.02)
        report = validator.validate(events, signal_meta)
    """

    def __init__(
        self,
        n_trials: int = 30,
        noise_pct: float = 0.02,
        fragile_threshold: float = _FRAGILE_THRESHOLD,
        seed: int | None = None,
    ) -> None:
        """
        Parameters
        ----------
        n_trials : int
            Number of noise injection trials per signal.
        noise_pct : float
            Noise magnitude as fraction of return std deviation.
        fragile_threshold : float
            Sensitivity above this → signal flagged as fragile.
        seed : int | None
            RNG seed for reproducibility.
        """
        if n_trials < 5:
            raise ValueError("n_trials must be >= 5")
        if not (0.001 <= noise_pct <= 0.50):
            raise ValueError("noise_pct must be between 0.001 and 0.50")

        self.n_trials = n_trials
        self.noise_pct = noise_pct
        self.fragile_threshold = fragile_threshold
        self.rng = random.Random(seed)

    def validate(
        self,
        events: list[SignalEvent],
        signal_meta: dict[str, str] | None = None,
    ) -> PerturbationReport:
        """
        Run perturbation robustness test on backtest events.

        Parameters
        ----------
        events : list[SignalEvent]
            All signal events from a completed backtest.
        signal_meta : dict[str, str] | None
            Optional signal_id → signal_name mapping.
        """
        if not events:
            return PerturbationReport(
                n_trials=self.n_trials,
                noise_pct=self.noise_pct,
            )

        signal_meta = signal_meta or {}

        # Group by signal
        by_signal: dict[str, list[SignalEvent]] = defaultdict(list)
        for e in events:
            by_signal[e.signal_id].append(e)

        results: list[SignalPerturbationResult] = []

        for sig_id in sorted(by_signal.keys()):
            sig_events = by_signal[sig_id]

            # Extract excess returns
            returns = [
                e.excess_returns.get(_REF_WINDOW, 0.0)
                for e in sig_events
                if _REF_WINDOW in e.excess_returns
            ]

            if len(returns) < _MIN_EVENTS:
                results.append(SignalPerturbationResult(
                    signal_id=sig_id,
                    signal_name=signal_meta.get(sig_id, sig_id),
                    total_events=len(returns),
                    n_trials=self.n_trials,
                    noise_pct=self.noise_pct,
                ))
                continue

            # Base Sharpe (no perturbation)
            base_sharpe = self._sharpe(returns)

            # Return volatility for noise scaling
            ret_std = self._std(returns)
            noise_scale = self.noise_pct * ret_std if ret_std > 1e-9 else self.noise_pct * 0.01

            # Run trials
            trial_sharpes: list[float] = []
            for _ in range(self.n_trials):
                perturbed = [
                    r + self.rng.gauss(0.0, noise_scale)
                    for r in returns
                ]
                trial_sharpes.append(self._sharpe(perturbed))

            # Sensitivity = CoV(trial_sharpes)
            mean_sharpe = sum(trial_sharpes) / len(trial_sharpes)
            std_sharpe = self._std(trial_sharpes)

            if abs(mean_sharpe) > 1e-9:
                sensitivity = std_sharpe / abs(mean_sharpe)
            else:
                sensitivity = 1.0 if std_sharpe > 1e-9 else 0.0

            # Retention: how much Sharpe survives perturbation
            if abs(base_sharpe) > 1e-9:
                retention = mean_sharpe / base_sharpe
            else:
                retention = 1.0 if abs(mean_sharpe) < 1e-9 else 0.0

            results.append(SignalPerturbationResult(
                signal_id=sig_id,
                signal_name=signal_meta.get(sig_id, sig_id),
                total_events=len(returns),
                n_trials=self.n_trials,
                noise_pct=self.noise_pct,
                base_sharpe=round(base_sharpe, 4),
                mean_perturbed_sharpe=round(mean_sharpe, 4),
                std_perturbed_sharpe=round(std_sharpe, 4),
                perturbation_sensitivity=round(sensitivity, 4),
                sharpe_retention=round(retention, 4),
                is_fragile=sensitivity > self.fragile_threshold,
            ))

        fragile_count = sum(1 for r in results if r.is_fragile)

        report = PerturbationReport(
            signal_results=results,
            n_trials=self.n_trials,
            noise_pct=self.noise_pct,
            total_signals=len(results),
            fragile_count=fragile_count,
            robust_count=len(results) - fragile_count,
        )

        logger.info(
            "PERTURBATION: %d signals tested — %d robust, %d fragile "
            "(%d trials, %.1f%% noise)",
            report.total_signals, report.robust_count, report.fragile_count,
            self.n_trials, self.noise_pct * 100,
        )

        return report

    # ── Internal ─────────────────────────────────────────────────────────

    @staticmethod
    def _sharpe(returns: list[float]) -> float:
        """Sharpe ratio from a list of returns."""
        if len(returns) < 5:
            return 0.0
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / len(returns)
        std = math.sqrt(var) if var > 0 else 1e-9
        return mean / std

    @staticmethod
    def _std(values: list[float]) -> float:
        """Standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / len(values)
        return math.sqrt(var) if var > 0 else 0.0
