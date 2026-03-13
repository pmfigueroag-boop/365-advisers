"""
src/engines/technical/module_registry.py
──────────────────────────────────────────────────────────────────────────────
Composable Module Registry — plugin system for technical analysis modules.

Each module implements the TechnicalModule protocol:
  - compute(): raw indicator computation
  - score(): continuous 0–10 scoring with evidence
  - format_details(): structured output for API

The registry manages module lifecycle, weight computation, and execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Any, runtime_checkable
import logging

from src.engines.technical.calibration import AssetContext


logger = logging.getLogger("365advisers.engines.technical.registry")


# ─── Protocol ────────────────────────────────────────────────────────────────

@runtime_checkable
class TechnicalModule(Protocol):
    """Interface that every technical analysis module must implement."""

    @property
    def name(self) -> str:
        """Unique module identifier (e.g., 'trend', 'momentum', 'sector_relative')."""
        ...

    @property
    def default_weight(self) -> float:
        """Default weight in aggregate score (0–1). All weights normalized at runtime."""
        ...

    def compute(
        self,
        price: float,
        indicators: dict,
        ohlcv: list[dict],
        ctx: AssetContext | None = None,
    ) -> Any:
        """Compute raw module result from market data."""
        ...

    def score(
        self,
        result: Any,
        regime: str = "TRANSITIONING",
        ctx: AssetContext | None = None,
    ) -> tuple[float, list[str]]:
        """Score the computed result → (0–10 score, evidence list)."""
        ...

    def format_details(self, result: Any) -> dict:
        """Format result into a dict for API output / ModuleScore.details."""
        ...


# ─── Module Result Container ────────────────────────────────────────────────

@dataclass
class ModuleOutput:
    """Output from a single module's compute + score cycle."""
    name: str
    score: float                       # 0–10
    signal: str                        # module-specific signal string
    evidence: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    raw_result: Any = None             # original compute() output


# ─── Registry ────────────────────────────────────────────────────────────────

class ModuleRegistry:
    """
    Registry for composable technical modules.

    Usage:
        registry = ModuleRegistry()
        registry.register(TrendAdapter())
        registry.register(MomentumAdapter())
        registry.register(SectorRelativeModule())  # ← new module, 1 line

        outputs = registry.run_all(price, indicators, ohlcv, regime, ctx)
        weights = registry.get_weights(regime)
    """

    def __init__(self) -> None:
        self._modules: dict[str, TechnicalModule] = {}

    def register(self, module: TechnicalModule) -> None:
        """Register a module. Replaces existing module with same name."""
        if not isinstance(module, TechnicalModule):
            raise TypeError(f"{module} does not implement TechnicalModule protocol")
        self._modules[module.name] = module
        logger.info(f"MODULE_REGISTRY: Registered '{module.name}' (weight={module.default_weight})")

    def unregister(self, name: str) -> None:
        """Remove a module by name."""
        self._modules.pop(name, None)

    @property
    def module_names(self) -> list[str]:
        return list(self._modules.keys())

    @property
    def module_count(self) -> int:
        return len(self._modules)

    def get_weights(self, regime: str = "TRANSITIONING") -> dict[str, float]:
        """
        Get normalized weights for all registered modules.
        Uses each module's default_weight, normalized to sum to 1.0.
        """
        raw = {name: mod.default_weight for name, mod in self._modules.items()}
        total = sum(raw.values())
        if total <= 0:
            # Equal weights fallback
            n = len(raw)
            return {name: 1.0 / n for name in raw} if n > 0 else {}
        return {name: w / total for name, w in raw.items()}

    def run_all(
        self,
        price: float,
        indicators: dict,
        ohlcv: list[dict],
        regime: str = "TRANSITIONING",
        ctx: AssetContext | None = None,
    ) -> list[ModuleOutput]:
        """
        Execute compute + score for every registered module.
        Returns list of ModuleOutput sorted by registration order.
        """
        outputs: list[ModuleOutput] = []

        for name, module in self._modules.items():
            try:
                # Compute
                raw_result = module.compute(price, indicators, ohlcv, ctx)

                # Score
                score_val, evidence = module.score(raw_result, regime, ctx)

                # Format details
                details = module.format_details(raw_result)

                # Extract signal from raw result
                signal = getattr(raw_result, "status", None) \
                    or getattr(raw_result, "condition", None) \
                    or getattr(raw_result, "breakout_direction", None) \
                    or "N/A"

                outputs.append(ModuleOutput(
                    name=name,
                    score=score_val,
                    signal=str(signal),
                    evidence=evidence,
                    details=details,
                    raw_result=raw_result,
                ))

            except Exception as exc:
                logger.error(f"MODULE_REGISTRY: Error in module '{name}': {exc}")
                outputs.append(ModuleOutput(
                    name=name, score=5.0, signal="ERROR",
                    evidence=[f"Module error: {exc}"],
                ))

        return outputs

    def compute_aggregate(
        self,
        outputs: list[ModuleOutput],
        regime: str = "TRANSITIONING",
    ) -> float:
        """Compute weighted aggregate score from module outputs."""
        weights = self.get_weights(regime)
        total_weight = 0.0
        weighted_sum = 0.0

        for out in outputs:
            w = weights.get(out.name, 0.0)
            weighted_sum += out.score * w
            total_weight += w

        if total_weight <= 0:
            return 5.0

        return round(weighted_sum / total_weight, 2)
