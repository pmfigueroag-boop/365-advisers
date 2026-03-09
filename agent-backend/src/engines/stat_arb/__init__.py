"""
src/engines/stat_arb/
──────────────────────────────────────────────────────────────────────────────
Statistical Arbitrage / Pairs Trading Engine.

Provides:
  • Engle-Granger cointegration testing
  • Ornstein-Uhlenbeck half-life estimation
  • Z-score tracking and signal generation
  • Universe-level pair scanning
  • Stat-arb strategy engine
"""

from src.engines.stat_arb.models import (
    PairCandidate,
    CointegrationResult,
    PairSpread,
    PairScanResult,
    ZScoreSignal,
)
from src.engines.stat_arb.cointegration import engle_granger_test, estimate_half_life
from src.engines.stat_arb.zscore import compute_spread, compute_zscore, generate_signals
from src.engines.stat_arb.scanner import PairScanner
from src.engines.stat_arb.engine import StatArbEngine

__all__ = [
    "PairCandidate",
    "CointegrationResult",
    "PairSpread",
    "PairScanResult",
    "ZScoreSignal",
    "engle_granger_test",
    "estimate_half_life",
    "compute_spread",
    "compute_zscore",
    "generate_signals",
    "PairScanner",
    "StatArbEngine",
]
