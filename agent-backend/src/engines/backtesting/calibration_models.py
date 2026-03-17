"""
src/engines/backtesting/calibration_models.py
--------------------------------------------------------------------------
Pydantic contracts for the Adaptive Signal Calibration system.

Design notes
~~~~~~~~~~~~
- ParameterType Enum contains only *continuously calibratable* parameters.
  Boolean parameters (enabled/disabled) are managed by the recalibration
  engine via CalibrationSuggestion (a separate model) and intentionally
  excluded from governor-controlled continuous governance.

- change_pct is always auto-computed as (new_value - old_value) / abs(old_value).
  Any value provided by the caller is silently overwritten during validation.

- PARAMETER_LIMITS is the authoritative source for per-parameter governance.
  The governor resolves limits via PARAMETER_LIMITS[param_type]; if the
  parameter is not found, a default ParameterLimits() is used as fallback.

- CalibrationConfig holds settings consumed by the *calibrator* (not the
  governor), except for min_observations, sharpe_floor, min_stability, and
  min_regime_sample which the governor also reads.  Fields exclusive to the
  calibrator are annotated with "(calibrator-only)".
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator


# ── Enums ────────────────────────────────────────────────────────────────────

class GovernanceAction(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED = "flagged"


class ParameterType(str, Enum):
    """
    Continuously calibratable parameter types.

    Only parameters with meaningful numeric delta logic belong here.
    Boolean parameters (e.g. enabled/disabled) are handled separately by
    the recalibration engine and do not enter the governor's continuous
    governance cascade.
    """
    WEIGHT = "weight"
    HALF_LIFE = "half_life"
    THRESHOLD = "threshold"


# ── Per-Parameter Clamp/Floor Config ─────────────────────────────────────────

class ParameterLimits(BaseModel):
    """
    Clamp, floor, and flag settings for a specific parameter type.

    This is the AUTHORITATIVE source for per-parameter governance limits.
    The governor never falls back to CalibrationConfig for these values;
    it falls back to ParameterLimits() defaults instead.
    """
    max_change_pct: float = 0.20
    absolute_delta_floor: float = 0.1
    clamp_min: float | None = None
    clamp_max: float | None = None
    flag_threshold_pct: float = 0.15


# Authoritative per-parameter limits.
# Governor resolves: PARAMETER_LIMITS[param_type] → fallback ParameterLimits()
PARAMETER_LIMITS: dict[ParameterType, ParameterLimits] = {
    ParameterType.WEIGHT: ParameterLimits(
        max_change_pct=0.20,
        absolute_delta_floor=0.10,  # weights range ~0.3–3.0
        clamp_min=0.3,
        clamp_max=3.0,
        flag_threshold_pct=0.15,
    ),
    ParameterType.HALF_LIFE: ParameterLimits(
        max_change_pct=0.20,
        absolute_delta_floor=1.0,   # half_life in days (5–60)
        clamp_min=2.0,
        clamp_max=120.0,
        flag_threshold_pct=0.15,
    ),
    ParameterType.THRESHOLD: ParameterLimits(
        max_change_pct=0.15,        # thresholds are more sensitive
        absolute_delta_floor=0.5,   # thresholds range ~5–50
        clamp_min=1.0,
        clamp_max=100.0,
        flag_threshold_pct=0.10,    # threshold changes are riskier → lower flag bar
    ),
}


# ── CalibrationConfig ────────────────────────────────────────────────────────

class CalibrationConfig(BaseModel):
    """
    Global configuration for a calibration cycle.

    Field usage by consumer:

    ┌────────────────────┬────────────┬──────────┐
    │ Field              │ Calibrator │ Governor │
    ├────────────────────┼────────────┼──────────┤
    │ lookback_days      │     ✓      │          │
    │ max_change_pct     │     ✓      │          │
    │ min_observations   │            │    ✓     │
    │ min_stability      │            │    ✓     │
    │ sharpe_floor       │            │    ✓     │
    │ weight_clamp_min   │     ✓      │          │
    │ weight_clamp_max   │     ✓      │          │
    │ min_regime_sample  │            │    ✓     │
    └────────────────────┴────────────┴──────────┘
    """
    # ── Calibrator-only fields ───────────────────────────────────────
    lookback_days: int = Field(250, description="Rolling window in trading days (calibrator-only)")
    max_change_pct: float = Field(
        0.20,
        description="Max change % used by calibrator's internal diff reporting (calibrator-only). "
        "Governor uses PARAMETER_LIMITS instead.",
    )
    weight_clamp_min: float = Field(
        0.3, description="Absolute min weight bound (calibrator-only)",
    )
    weight_clamp_max: float = Field(
        3.0, description="Absolute max weight bound (calibrator-only)",
    )

    # ── Governor-consumed fields ─────────────────────────────────────
    min_observations: int = Field(50, description="Min signal firings before governor approves")
    min_stability: float = Field(0.3, ge=0.0, le=1.0, description="Min stability for weight increase")
    sharpe_floor: float = Field(
        0.0,
        description="Don't increase weight if Sharpe below this. "
        "0.0 = reject only negative-edge signals.",
    )
    min_regime_sample: int = Field(
        20, ge=1,
        description="Min events in a regime before trusting its data",
    )


# ── ParameterChange ──────────────────────────────────────────────────────────

class ParameterChange(BaseModel):
    """
    A single proposed parameter change.

    change_pct is always auto-computed as:

        (new_value - old_value) / abs(old_value)

    Any provided value is ignored and overwritten during model validation.
    The sign indicates direction: positive = increase, negative = decrease.
    """
    signal_id: str
    parameter: ParameterType
    old_value: float
    new_value: float
    change_pct: float = 0.0
    evidence: str = ""
    regime: str | None = None

    # Structured metrics — used by Governor for typed validation
    stability: float | None = Field(None, ge=0.0, le=1.0)
    hit_rate: float | None = Field(None, ge=0.0, le=1.0)
    sample_size: int | None = Field(
        None, ge=0,
        description="Number of signal firings (events) in the regime period. "
        "Not trading days — use min_regime_sample for day-based minimums.",
    )
    sharpe: float | None = None  # Sharpe can be any real number
    contribution_score: float | None = Field(
        None,
        description="Marginal alpha contribution from attribution engine. "
        "Negative = signal dilutes system alpha.",
    )
    oos_degradation: float | None = Field(
        None,
        description="Walk-forward OOS degradation ratio. "
        "1 - (test_sharpe / train_sharpe). High (>0.5) = likely overfitted.",
    )
    perturbation_sensitivity: float | None = Field(
        None,
        description="Perturbation robustness CoV. "
        "std(perturbed_sharpes) / |mean|. High (>0.5) = fragile signal.",
    )
    spread_t_stat: float | None = Field(
        None,
        description="Top-Bottom portfolio spread t-statistic. "
        "Negative spread with weight increase = signal ranks backwards.",
    )

    @model_validator(mode="after")
    def _compute_change_pct(self) -> ParameterChange:
        """Auto-compute signed change_pct = (new - old) / abs(old)."""
        if abs(self.old_value) > 1e-9:
            self.change_pct = round(
                (self.new_value - self.old_value) / abs(self.old_value), 6
            )
        else:
            self.change_pct = 0.0
        return self


class GovernanceDecision(BaseModel):
    """Governor's decision on a proposed change."""
    change: ParameterChange
    action: GovernanceAction
    reason: str = ""


# ── Supporting Models ────────────────────────────────────────────────────────

class RegimeWeightTable(BaseModel):
    """
    Per-regime signal weights.

    sample_size here is the number of trading days classified under this
    regime — distinct from ParameterChange.sample_size which counts
    signal firing events.
    """
    regime: str
    weights: dict[str, float] = Field(default_factory=dict)
    sample_size: int = Field(
        0, ge=0,
        description="Number of trading days in this regime classification",
    )
    sharpe_by_signal: dict[str, float] = Field(default_factory=dict)


class CalibratedSignalConfig(BaseModel):
    """Calibrated configuration for a single signal."""
    signal_id: str
    weight: float = Field(1.0, gt=0.0)
    threshold: float | None = None
    strong_threshold: float | None = None
    half_life: float | None = Field(None, gt=0.0)
    confidence_score: float = Field(0.5, ge=0.0, le=1.0)
    enabled: bool = True


class CalibrationVersion(BaseModel):
    """A versioned snapshot of calibrated configuration."""
    version: str = "v1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    lookback_days: int = 250
    universe_name: str = ""
    universe_size: int = 0
    signals_calibrated: int = 0
    changes_applied: list[ParameterChange] = Field(default_factory=list)
    changes_rejected: list[GovernanceDecision] = Field(default_factory=list)
    changes_flagged: list[GovernanceDecision] = Field(default_factory=list)
    signal_configs: list[CalibratedSignalConfig] = Field(default_factory=list)
    regime_weights: list[RegimeWeightTable] = Field(default_factory=list)
    performance_snapshot: dict[str, float] = Field(
        default_factory=dict,
        description="Key metrics at calibration time",
    )


class CalibrationResult(BaseModel):
    """Full output of a calibration cycle."""
    version: CalibrationVersion
    total_proposed: int = 0
    total_approved: int = 0
    total_rejected: int = 0
    total_flagged: int = 0
    governance_decisions: list[GovernanceDecision] = Field(default_factory=list)
    execution_time_seconds: float = 0.0
