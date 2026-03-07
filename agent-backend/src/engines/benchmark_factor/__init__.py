"""
src/engines/benchmark_factor/__init__.py
──────────────────────────────────────────────────────────────────────────────
Benchmark & Factor Neutral Evaluation Model — evaluates signals against
multiple benchmarks and risk factors to isolate pure alpha.
"""

from src.engines.benchmark_factor.engine import BenchmarkFactorEngine
from src.engines.benchmark_factor.models import (
    BenchmarkConfig,
    BenchmarkFactorReport,
    BenchmarkResult,
    FactorExposure,
    FactorTickers,
    SignalBenchmarkProfile,
)

__all__ = [
    "BenchmarkFactorEngine",
    "BenchmarkConfig",
    "BenchmarkFactorReport",
    "BenchmarkResult",
    "FactorExposure",
    "FactorTickers",
    "SignalBenchmarkProfile",
]
