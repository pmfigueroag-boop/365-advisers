"""
src/engines/backtesting/calibration_governor.py
--------------------------------------------------------------------------
Calibration Governor -- validates and constrains auto-calibration changes.

Only continuously calibratable parameters (weight, half_life, threshold)
are supported.  Parameters not present in PARAMETER_LIMITS are explicitly
rejected — no silent fallback.

Rule cascade:
  0. Unsupported parameter type → REJECT
  1. No performance record → REJECT
  2. Low-sample regime → accumulate warning (continue evaluating)
  3. abs(change_pct) > per-parameter max → CLAMP + FLAG
  4. Insufficient observations → REJECT
  5. Weight increase + failed quality gate → REJECT/FLAG
  5b. Weight increase + negative alpha contribution → FLAG
  5c. Weight increase + high OOS degradation → FLAG
  5d. Weight increase + high perturbation sensitivity → FLAG
  5e. Weight increase + negative top-bottom spread → FLAG
  6. Weight increase + unstable → REJECT
  7. Weight decrease + strong long-horizon HR → FLAG
  8. abs(change_pct) > per-parameter flag_threshold → FLAG
  9. All hard rules passed + pending warnings → FLAG; else APPROVE
"""

from __future__ import annotations

import logging
import math

from src.engines.backtesting.calibration_models import (
    CalibrationConfig,
    GovernanceAction,
    GovernanceDecision,
    ParameterChange,
    ParameterLimits,
    ParameterType,
    PARAMETER_LIMITS,
)
from src.engines.backtesting.models import SignalPerformanceRecord

logger = logging.getLogger("365advisers.calibrator.governor")

# Parameters that the governor's continuous governance cascade can handle.
# Any ParameterType not in this set is rejected with an explicit reason.
_SUPPORTED_PARAMETERS: frozenset[ParameterType] = frozenset(PARAMETER_LIMITS.keys())


class CalibrationGovernor:
    """
    Validates proposed calibration changes against governance rules.

    Usage::

        governor = CalibrationGovernor(config)
        decisions = governor.review(proposed_changes, signal_records)
    """

    def __init__(self, config: CalibrationConfig | None = None) -> None:
        self.config = config or CalibrationConfig()

    # ── Public API ───────────────────────────────────────────────────────

    def review(
        self,
        changes: list[ParameterChange],
        records: dict[str, SignalPerformanceRecord],
    ) -> list[GovernanceDecision]:
        """Review all proposed changes and return governance decisions."""
        decisions: list[GovernanceDecision] = []

        for change in changes:
            decision = self._review_single(change, records.get(change.signal_id))
            decisions.append(decision)

        approved = sum(1 for d in decisions if d.action == GovernanceAction.APPROVED)
        rejected = sum(1 for d in decisions if d.action == GovernanceAction.REJECTED)
        flagged = sum(1 for d in decisions if d.action == GovernanceAction.FLAGGED)

        logger.info(
            "GOVERNOR: Reviewed %d changes — %d approved, %d rejected, %d flagged",
            len(decisions), approved, rejected, flagged,
        )

        return decisions

    # ── Core Rule Logic ──────────────────────────────────────────────────

    def _review_single(
        self,
        change: ParameterChange,
        record: SignalPerformanceRecord | None,
    ) -> GovernanceDecision:
        """
        Apply governance rules to a single change.

        Low-sample regime is tracked as a warning but does NOT short-circuit.
        All rules run; if the change would otherwise be APPROVED, a pending
        regime warning upgrades it to FLAGGED.
        """
        # Accumulate warnings that downgrade APPROVED → FLAGGED
        warnings: list[str] = []

        # ── Rule 0: Unsupported parameter type → reject ─────────────────
        if change.parameter not in _SUPPORTED_PARAMETERS:
            return GovernanceDecision(
                change=change,
                action=GovernanceAction.REJECTED,
                reason=(
                    f"Parameter type '{change.parameter.value}' is not supported by "
                    f"continuous governance. Supported: "
                    f"{sorted(p.value for p in _SUPPORTED_PARAMETERS)}"
                ),
            )

        # ── Rule 1: No record → reject ──────────────────────────────────
        if record is None:
            return GovernanceDecision(
                change=change,
                action=GovernanceAction.REJECTED,
                reason="No performance record — cannot calibrate without evidence",
            )

        # ── Rule 2: Low-sample regime → warn (continue evaluating) ──────
        if change.regime is not None and change.sample_size is not None:
            if change.sample_size < self.config.min_regime_sample:
                warnings.append(
                    f"Low-confidence regime '{change.regime}': "
                    f"{change.sample_size} events < {self.config.min_regime_sample} min"
                )

        # ── Rule 3: Per-parameter magnitude clamp ───────────────────────
        limits = PARAMETER_LIMITS[change.parameter]
        if abs(change.change_pct) > limits.max_change_pct:
            return self._clamp_and_flag(change, limits, warnings)

        # ── Rule 4: Min observations ────────────────────────────────────
        if record.total_firings < self.config.min_observations:
            return GovernanceDecision(
                change=change,
                action=GovernanceAction.REJECTED,
                reason=(
                    f"Insufficient observations: {record.total_firings} firings "
                    f"< {self.config.min_observations} required"
                ),
            )

        # ── Rule 5: Multi-metric quality gate for weight increases ──────
        if change.parameter == ParameterType.WEIGHT and change.new_value > change.old_value:
            rejection = self._check_quality_gate(change, record)
            if rejection is not None:
                return rejection

        # ── Rule 5b: Alpha dilution protection ──────────────────────────
        if (change.parameter == ParameterType.WEIGHT
                and change.new_value > change.old_value
                and change.contribution_score is not None
                and change.contribution_score < 0):
            return GovernanceDecision(
                change=change,
                action=GovernanceAction.FLAGGED,
                reason=(
                    f"Alpha dilution: contribution={change.contribution_score:+.4f}. "
                    f"Signal does not add marginal alpha to the system."
                ),
            )

        # ── Rule 5c: OOS overfit protection ────────────────────────────
        if (change.parameter == ParameterType.WEIGHT
                and change.new_value > change.old_value
                and change.oos_degradation is not None
                and change.oos_degradation > 0.50):
            return GovernanceDecision(
                change=change,
                action=GovernanceAction.FLAGGED,
                reason=(
                    f"OOS overfit risk: degradation={change.oos_degradation:.0%}. "
                    f"Signal performance degrades >50% out-of-sample."
                ),
            )

        # ── Rule 5d: Perturbation fragility protection ─────────────────
        if (change.parameter == ParameterType.WEIGHT
                and change.new_value > change.old_value
                and change.perturbation_sensitivity is not None
                and change.perturbation_sensitivity > 0.50):
            return GovernanceDecision(
                change=change,
                action=GovernanceAction.FLAGGED,
                reason=(
                    f"Fragile signal: perturbation_sensitivity="
                    f"{change.perturbation_sensitivity:.2f}. "
                    f"Sharpe is unstable under ±2% return noise."
                ),
            )

        # ── Rule 5e: Negative top-bottom spread protection ─────────────
        if (change.parameter == ParameterType.WEIGHT
                and change.new_value > change.old_value
                and change.spread_t_stat is not None
                and change.spread_t_stat < -2.0):
            return GovernanceDecision(
                change=change,
                action=GovernanceAction.FLAGGED,
                reason=(
                    f"Inverse signal: spread t-stat={change.spread_t_stat:+.2f}. "
                    f"High-confidence picks underperform low-confidence picks."
                ),
            )

        # ── Rule 6: Stability check for weight increases ────────────────
        if change.parameter == ParameterType.WEIGHT and change.new_value > change.old_value:
            stability = change.stability
            if stability is not None and stability < self.config.min_stability:
                return GovernanceDecision(
                    change=change,
                    action=GovernanceAction.REJECTED,
                    reason=(
                        f"Unstable signal: stability={stability:.2f} "
                        f"< threshold={self.config.min_stability:.2f}"
                    ),
                )

        # ── Rule 7: Downside protection ─────────────────────────────────
        if change.parameter == ParameterType.WEIGHT and change.new_value < change.old_value:
            hr_60 = record.hit_rate.get(60, 0.0)
            if hr_60 > 0.60 and record.total_firings > 80:
                return GovernanceDecision(
                    change=change,
                    action=GovernanceAction.FLAGGED,
                    reason=(
                        f"Downside protection: HR@60d={hr_60:.0%}, "
                        f"n={record.total_firings}. Reduction may be temporary noise."
                    ),
                )

        # ── Rule 8: Per-parameter flag threshold ───────────────────────
        if abs(change.change_pct) > limits.flag_threshold_pct:
            return GovernanceDecision(
                change=change,
                action=GovernanceAction.FLAGGED,
                reason=(
                    f"Change {change.change_pct:+.1%} exceeds "
                    f"{change.parameter.value} flag threshold "
                    f"({limits.flag_threshold_pct:.0%})"
                ),
            )

        # ── Rule 9: All hard rules passed ──────────────────────────────
        if warnings:
            return GovernanceDecision(
                change=change,
                action=GovernanceAction.FLAGGED,
                reason="; ".join(warnings),
            )

        return GovernanceDecision(
            change=change,
            action=GovernanceAction.APPROVED,
            reason="All governance checks passed",
        )

    # ── Clamp & Flag ─────────────────────────────────────────────────────

    def _clamp_and_flag(
        self,
        change: ParameterChange,
        limits: ParameterLimits,
        warnings: list[str] | None = None,
    ) -> GovernanceDecision:
        """Clamp a change to per-parameter limits and flag for review."""
        max_delta = max(
            abs(change.old_value) * limits.max_change_pct,
            limits.absolute_delta_floor,
        )
        direction = 1 if change.new_value > change.old_value else -1
        clamped = change.old_value + (direction * max_delta)

        # Apply parameter-level hard clamps if defined
        if limits.clamp_min is not None:
            clamped = max(clamped, limits.clamp_min)
        if limits.clamp_max is not None:
            clamped = min(clamped, limits.clamp_max)

        # change_pct is auto-computed by model_validator (signed)
        clamped_change = ParameterChange(
            signal_id=change.signal_id,
            parameter=change.parameter,
            old_value=change.old_value,
            new_value=round(clamped, 4),
            evidence=change.evidence + f" [CLAMPED from {change.new_value:.4f}]",
            regime=change.regime,
            stability=change.stability,
            hit_rate=change.hit_rate,
            sample_size=change.sample_size,
            sharpe=change.sharpe,
        )

        reason_parts = list(warnings or [])
        reason_parts.append(
            f"Clamped {change.parameter.value}: "
            f"requested {change.change_pct:+.1%}, "
            f"allowed {clamped_change.change_pct:+.1%} "
            f"(max ±{limits.max_change_pct:.0%})"
        )

        return GovernanceDecision(
            change=clamped_change,
            action=GovernanceAction.FLAGGED,
            reason="; ".join(reason_parts),
        )

    # ── Multi-Metric Quality Gate ────────────────────────────────────────

    def _check_quality_gate(
        self,
        change: ParameterChange,
        record: SignalPerformanceRecord,
    ) -> GovernanceDecision | None:
        """
        Multi-metric quality gate for weight increases.

        Checks:
          - Sharpe floor
          - Significance proxy (Sharpe × √n > 1.65)
          - Hit rate above random (> 52%)

        Returns GovernanceDecision if rejected/flagged, None if passed.
        """
        sharpe = record.sharpe_ratio.get(20, 0.0)
        hr = record.hit_rate.get(20, 0.5)
        n = record.total_firings

        # Gate 1: Sharpe floor
        if sharpe < self.config.sharpe_floor:
            return GovernanceDecision(
                change=change,
                action=GovernanceAction.REJECTED,
                reason=(
                    f"Sharpe gate: Sharpe@20d={sharpe:.2f} "
                    f"< floor={self.config.sharpe_floor:.2f}"
                ),
            )

        # Gate 2: Significance proxy (Sharpe × √n)
        # Not a formal t-test — a practical proxy for sample adequacy.
        sig_proxy = sharpe * math.sqrt(n) if n > 0 else 0.0
        if sharpe > 0 and sig_proxy < 1.65:
            return GovernanceDecision(
                change=change,
                action=GovernanceAction.FLAGGED,
                reason=(
                    f"Below significance proxy: "
                    f"Sharpe×√n={sig_proxy:.2f} < 1.65 "
                    f"(Sharpe={sharpe:.2f}, n={n})"
                ),
            )

        # Gate 3: Hit rate above random
        if hr < 0.52:
            return GovernanceDecision(
                change=change,
                action=GovernanceAction.FLAGGED,
                reason=(
                    f"Hit rate near random: HR@20d={hr:.1%} < 52%. "
                    f"Sharpe may be driven by outlier returns."
                ),
            )

        return None  # All quality gates passed

    # ── Decision Extractors ──────────────────────────────────────────────

    def get_approved(
        self, decisions: list[GovernanceDecision]
    ) -> list[ParameterChange]:
        """
        Extract only APPROVED changes.

        FLAGGED changes are NOT included — they require human review
        via --approve-flagged or manual intervention.
        """
        return [
            d.change for d in decisions
            if d.action == GovernanceAction.APPROVED
        ]

    def get_flagged(
        self, decisions: list[GovernanceDecision]
    ) -> list[ParameterChange]:
        """Extract changes that need human review before applying."""
        return [
            d.change for d in decisions
            if d.action == GovernanceAction.FLAGGED
        ]

    def get_rejected(
        self, decisions: list[GovernanceDecision]
    ) -> list[GovernanceDecision]:
        """Extract rejected decisions with full reason audit trail."""
        return [d for d in decisions if d.action == GovernanceAction.REJECTED]
