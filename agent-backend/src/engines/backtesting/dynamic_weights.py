"""
src/engines/backtesting/dynamic_weights.py
──────────────────────────────────────────────────────────────────────────────
Dynamic Weight Engine — continuous, evidence-based signal weight model.

Replaces the discrete tier system (A/B/C/D) with a mathematically
grounded formula:

    Dynamic Weight = P(s) × C(s) × R(s)

    P(s) = Performance Score [0.2, 2.0]  — Sharpe + Hit Rate blend
    C(s) = Confidence Score  [0.3, 1.0]  — sample size + p-value
    R(s) = Recency Factor    [0.5, 1.0]  — exponential decay
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from src.engines.backtesting.repository import BacktestRepository

logger = logging.getLogger("365advisers.backtesting.dynamic_weights")


# ─── Configuration ───────────────────────────────────────────────────────────

class DynamicWeightConfig(BaseModel):
    """Tunable parameters for the weight model."""
    alpha: float = Field(0.6, description="Sharpe vs HitRate blend (0=all HR, 1=all Sharpe)")
    sharpe_ceiling: float = Field(1.5, description="Sharpe normalization cap")
    hit_rate_floor: float = Field(0.40, description="Hit rate normalization floor")
    hit_rate_ceiling: float = Field(0.70, description="Hit rate normalization ceiling")
    n_target: int = Field(100, description="Sample size target for full confidence")
    recency_half_life_days: int = Field(90, description="Recency exponential half-life")
    min_weight: float = Field(0.2, description="Performance score floor")
    max_weight: float = Field(2.0, description="Performance score cap")
    confidence_floor: float = Field(0.3, description="Confidence score floor")
    recency_floor: float = Field(0.5, description="Recency factor floor")


# ─── Output Models ───────────────────────────────────────────────────────────

class DynamicSignalWeight(BaseModel):
    """Computed dynamic weight for a single signal."""
    signal_id: str
    signal_name: str = ""
    performance_score: float        # P(s)
    confidence_score: float         # C(s)
    recency_factor: float           # R(s)
    dynamic_weight: float           # P × C × R
    components: dict[str, float] = Field(
        default_factory=dict,
        description="Breakdown: sharpe_norm, hr_norm, c_n, c_p, days_since",
    )


class DynamicWeightProfile(BaseModel):
    """Complete set of dynamic weights for all signals."""
    weights: dict[str, float] = Field(
        default_factory=dict,
        description="{signal_id → multiplier}",
    )
    details: list[DynamicSignalWeight] = Field(default_factory=list)
    signal_count: int = 0
    computed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    config: DynamicWeightConfig = Field(default_factory=DynamicWeightConfig)


# ─── Engine ──────────────────────────────────────────────────────────────────

class DynamicWeightEngine:
    """
    Computes continuous dynamic weights for all signals with backtest data.

    Usage
    -----
    engine = DynamicWeightEngine()
    profile = engine.compute_all()
    weights = profile.weights  # {signal_id: multiplier}
    """

    def __init__(self, config: DynamicWeightConfig | None = None) -> None:
        self.config = config or DynamicWeightConfig()
        self._repo = BacktestRepository

    # ── Public API ────────────────────────────────────────────────────────

    def compute_all(self) -> DynamicWeightProfile:
        """Compute dynamic weights for all signals with backtest data."""
        from src.engines.alpha_signals.registry import registry

        weights: dict[str, float] = {}
        details: list[DynamicSignalWeight] = []

        for sig in registry.get_enabled():
            result = self.compute_one(sig.id, sig.name)
            if result:
                weights[sig.id] = result.dynamic_weight
                details.append(result)

        logger.info(
            f"DYN-WEIGHTS: Computed weights for {len(weights)} signals"
        )

        return DynamicWeightProfile(
            weights=weights,
            details=details,
            signal_count=len(weights),
            config=self.config,
        )

    def compute_one(
        self,
        signal_id: str,
        signal_name: str = "",
    ) -> DynamicSignalWeight | None:
        """Compute dynamic weight for a single signal."""
        record = self._repo.get_signal_latest(signal_id)
        if not record or record.total_firings < 10:
            return None

        cfg = self.config
        ref_window = 20

        # ── Extract metrics ───────────────────────────────────────────
        sharpe = record.sharpe_ratio.get(ref_window, 0.0)
        hit_rate = record.hit_rate.get(ref_window, 0.0)
        n = record.sample_size
        p_value = min(record.p_value.values()) if record.p_value else 1.0
        days_since = (
            datetime.now(timezone.utc) - record.backtest_date
        ).days if record.backtest_date else 0

        # ── P(s): Performance Score ───────────────────────────────────
        p_score = self._performance_score(sharpe, hit_rate)

        # ── C(s): Confidence Score ────────────────────────────────────
        c_score = self._confidence_score(n, p_value)

        # ── R(s): Recency Factor ──────────────────────────────────────
        r_factor = self._recency_factor(days_since)

        # ── Final weight ──────────────────────────────────────────────
        dynamic_weight = round(p_score * c_score * r_factor, 4)

        # Compute debug components
        sharpe_norm = self._clip(sharpe / cfg.sharpe_ceiling, 0.0, 1.0)
        hr_norm = self._clip(
            (hit_rate - cfg.hit_rate_floor) /
            (cfg.hit_rate_ceiling - cfg.hit_rate_floor),
            0.0, 1.0,
        )
        c_n = self._clip(n / cfg.n_target, cfg.confidence_floor, 1.0)
        c_p = 1.0 - 0.7 * self._clip(p_value, 0.0, 1.0)

        return DynamicSignalWeight(
            signal_id=signal_id,
            signal_name=signal_name,
            performance_score=round(p_score, 4),
            confidence_score=round(c_score, 4),
            recency_factor=round(r_factor, 4),
            dynamic_weight=dynamic_weight,
            components={
                "sharpe_raw": round(sharpe, 4),
                "sharpe_norm": round(sharpe_norm, 4),
                "hit_rate_raw": round(hit_rate, 4),
                "hit_rate_norm": round(hr_norm, 4),
                "sample_size": float(n),
                "p_value": round(p_value, 6),
                "c_n": round(c_n, 4),
                "c_p": round(c_p, 4),
                "days_since_backtest": float(days_since),
            },
        )

    def get_weight_dict(self) -> dict[str, float]:
        """Convenience: return just the {signal_id: weight} dict."""
        return self.compute_all().weights

    # ── Scoring Functions ─────────────────────────────────────────────────

    def _performance_score(self, sharpe: float, hit_rate: float) -> float:
        """
        P(s) = min_weight + (max_weight − min_weight) × blend

        blend = α × Sharpe_norm + (1 − α) × HitRate_norm
        """
        cfg = self.config

        sharpe_norm = self._clip(sharpe / cfg.sharpe_ceiling, 0.0, 1.0)
        hr_norm = self._clip(
            (hit_rate - cfg.hit_rate_floor) /
            (cfg.hit_rate_ceiling - cfg.hit_rate_floor),
            0.0, 1.0,
        )

        blend = cfg.alpha * sharpe_norm + (1 - cfg.alpha) * hr_norm
        return cfg.min_weight + (cfg.max_weight - cfg.min_weight) * blend

    def _confidence_score(self, n: int, p_value: float) -> float:
        """
        C(s) = c_n × c_p

        c_n = clip(n / N_target, floor, 1.0)
        c_p = 1.0 − 0.7 × clip(p_value, 0, 1)
        """
        cfg = self.config

        c_n = self._clip(n / cfg.n_target, cfg.confidence_floor, 1.0)
        c_p = 1.0 - 0.7 * self._clip(p_value, 0.0, 1.0)

        return max(cfg.confidence_floor, c_n * c_p)

    def _recency_factor(self, days_since: int) -> float:
        """
        R(s) = max(floor, exp(−λ × days))

        λ = ln(2) / T_half
        """
        cfg = self.config

        if days_since <= 0:
            return 1.0

        lam = math.log(2) / cfg.recency_half_life_days
        raw = math.exp(-lam * days_since)

        return max(cfg.recency_floor, raw)

    # ── Utility ───────────────────────────────────────────────────────────

    @staticmethod
    def _clip(value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, value))
