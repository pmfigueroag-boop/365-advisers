"""
tests/test_module_registry.py
──────────────────────────────────────────────────────────────────────────────
Tests for the Composable Module Registry and pluggable module system.
"""

from __future__ import annotations

import pytest
from dataclasses import dataclass
from typing import Any

from src.engines.technical.module_registry import (
    ModuleRegistry,
    ModuleOutput,
    TechnicalModule,
)
from src.engines.technical.calibration import AssetContext


# ─── Mock modules ────────────────────────────────────────────────────────────

@dataclass
class MockResult:
    value: float = 7.0
    status: str = "BULLISH"


class MockModuleA:
    @property
    def name(self) -> str:
        return "mock_a"

    @property
    def default_weight(self) -> float:
        return 0.6

    def compute(self, price, indicators, ohlcv, ctx=None) -> MockResult:
        return MockResult(value=price / 10)

    def score(self, result, regime="TRANSITIONING", ctx=None) -> tuple[float, list[str]]:
        return min(result.value, 10.0), [f"Mock A score: {result.value}"]

    def format_details(self, result) -> dict:
        return {"value": result.value}


class MockModuleB:
    @property
    def name(self) -> str:
        return "mock_b"

    @property
    def default_weight(self) -> float:
        return 0.4

    def compute(self, price, indicators, ohlcv, ctx=None) -> MockResult:
        return MockResult(value=5.0, status="NEUTRAL")

    def score(self, result, regime="TRANSITIONING", ctx=None) -> tuple[float, list[str]]:
        return 5.0, ["Mock B: neutral"]

    def format_details(self, result) -> dict:
        return {"value": result.value}


class ErrorModule:
    @property
    def name(self) -> str:
        return "error_module"

    @property
    def default_weight(self) -> float:
        return 0.1

    def compute(self, price, indicators, ohlcv, ctx=None):
        raise RuntimeError("Simulated error")

    def score(self, result, regime="TRANSITIONING", ctx=None):
        return 5.0, []

    def format_details(self, result) -> dict:
        return {}


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestModuleRegistry:

    def test_register_and_count(self):
        reg = ModuleRegistry()
        reg.register(MockModuleA())
        assert reg.module_count == 1
        reg.register(MockModuleB())
        assert reg.module_count == 2

    def test_module_names(self):
        reg = ModuleRegistry()
        reg.register(MockModuleA())
        reg.register(MockModuleB())
        assert "mock_a" in reg.module_names
        assert "mock_b" in reg.module_names

    def test_unregister(self):
        reg = ModuleRegistry()
        reg.register(MockModuleA())
        reg.unregister("mock_a")
        assert reg.module_count == 0

    def test_weights_sum_to_one(self):
        reg = ModuleRegistry()
        reg.register(MockModuleA())
        reg.register(MockModuleB())
        weights = reg.get_weights()
        assert abs(sum(weights.values()) - 1.0) < 0.001

    def test_weights_normalized(self):
        reg = ModuleRegistry()
        reg.register(MockModuleA())  # weight=0.6
        reg.register(MockModuleB())  # weight=0.4
        weights = reg.get_weights()
        assert abs(weights["mock_a"] - 0.6) < 0.001
        assert abs(weights["mock_b"] - 0.4) < 0.001

    def test_run_all_produces_outputs(self):
        reg = ModuleRegistry()
        reg.register(MockModuleA())
        reg.register(MockModuleB())
        outputs = reg.run_all(100.0, {}, [])
        assert len(outputs) == 2
        assert all(isinstance(o, ModuleOutput) for o in outputs)

    def test_run_all_scores(self):
        reg = ModuleRegistry()
        reg.register(MockModuleA())
        outputs = reg.run_all(70.0, {}, [])
        assert outputs[0].score == 7.0  # 70 / 10

    def test_compute_aggregate(self):
        reg = ModuleRegistry()
        reg.register(MockModuleA())  # weight=0.6, score=7.0
        reg.register(MockModuleB())  # weight=0.4, score=5.0
        outputs = reg.run_all(70.0, {}, [])
        agg = reg.compute_aggregate(outputs)
        expected = 7.0 * 0.6 + 5.0 * 0.4
        assert abs(agg - expected) < 0.01

    def test_error_module_returns_neutral(self):
        reg = ModuleRegistry()
        reg.register(ErrorModule())
        outputs = reg.run_all(100.0, {}, [])
        assert len(outputs) == 1
        assert outputs[0].score == 5.0
        assert outputs[0].signal == "ERROR"

    def test_adding_sixth_module(self):
        """Adding a new module doesn't require modifying existing code."""
        reg = ModuleRegistry()
        reg.register(MockModuleA())
        reg.register(MockModuleB())
        assert reg.module_count == 2

        # Add a third module — no code changes needed
        class NewModule:
            @property
            def name(self):
                return "new_module"
            @property
            def default_weight(self):
                return 0.3
            def compute(self, price, indicators, ohlcv, ctx=None):
                return MockResult(value=8.0)
            def score(self, result, regime="TRANSITIONING", ctx=None):
                return 8.0, ["New module: high"]
            def format_details(self, result):
                return {}

        reg.register(NewModule())
        assert reg.module_count == 3
        weights = reg.get_weights()
        assert abs(sum(weights.values()) - 1.0) < 0.001
        outputs = reg.run_all(100, {}, [])
        assert len(outputs) == 3

    def test_replace_module(self):
        """Registering same name replaces existing module."""
        reg = ModuleRegistry()
        reg.register(MockModuleA())

        class ReplacementA:
            @property
            def name(self):
                return "mock_a"
            @property
            def default_weight(self):
                return 0.9
            def compute(self, price, indicators, ohlcv, ctx=None):
                return MockResult(value=9.0)
            def score(self, result, regime="TRANSITIONING", ctx=None):
                return 9.0, []
            def format_details(self, result):
                return {}

        reg.register(ReplacementA())
        assert reg.module_count == 1
        weights = reg.get_weights()
        assert abs(weights["mock_a"] - 1.0) < 0.001
