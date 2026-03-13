"""
src/engines/technical/iv_spread.py
──────────────────────────────────────────────────────────────────────────────
Implied Volatility Spread Module — compares IV vs RV for institutional edge.

Stub implementation: activates only when options data is available.
When no IV data is present, returns neutral score (5.0).

Implements TechnicalModule protocol for composable registration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.engines.technical.calibration import AssetContext
from src.engines.technical.math_utils import clamp, normalize_to_score


@dataclass
class IVSpreadResult:
    """IV spread analysis result."""
    iv_current: float | None = None        # current implied vol (annualized %)
    rv_current: float | None = None        # current realized vol (annualized %)
    iv_rv_spread: float | None = None      # IV - RV (positive = market expects more vol)
    iv_percentile: float | None = None     # IV rank 0–100 (where current IV sits in 1yr range)
    put_call_ratio: float | None = None    # put/call volume ratio
    skew: float | None = None              # 25-delta skew (put-call IV diff)
    status: str = "NO_DATA"                # ELEVATED_IV / CHEAP_IV / NORMAL / NO_DATA
    data_available: bool = False


class IVSpreadModule:
    """
    IV Spread Module — institutional volatility edge analysis.

    Scoring logic (when data available):
      - IV >> RV (spread > +5%) → bearish (market expects trouble) → low score
      - IV << RV (spread < -5%) → bullish (cheap protection) → high score
      - IV ~= RV → neutral
      - IV percentile > 80 → historically expensive → caution
      - IV percentile < 20 → historically cheap → opportunity

    When no IV data: returns neutral 5.0 score.
    """

    @property
    def name(self) -> str:
        return "iv_spread"

    @property
    def default_weight(self) -> float:
        return 0.10  # 10% when active

    def compute(
        self,
        price: float,
        indicators: dict,
        ohlcv: list[dict],
        ctx: AssetContext | None = None,
    ) -> IVSpreadResult:
        """
        Compute IV spread from provided options data.

        Expected indicators dict keys:
          - 'iv': float (current implied volatility, annualized %)
          - 'iv_percentile': float (0–100 rank)
          - 'put_call_ratio': float
          - 'skew_25d': float
        """
        iv = indicators.get("iv")
        iv_percentile = indicators.get("iv_percentile")
        pcr = indicators.get("put_call_ratio")
        skew = indicators.get("skew_25d")

        if iv is None:
            return IVSpreadResult()

        # Compute realized vol from OHLCV (20-day annualized)
        rv = None
        if len(ohlcv) >= 21:
            import math
            log_returns = []
            for i in range(1, min(21, len(ohlcv))):
                c_prev = ohlcv[-(i + 1)].get("close", 0)
                c_curr = ohlcv[-i].get("close", 0)
                if c_prev > 0 and c_curr > 0:
                    log_returns.append(math.log(c_curr / c_prev))

            if len(log_returns) >= 10:
                mean = sum(log_returns) / len(log_returns)
                variance = sum((r - mean) ** 2 for r in log_returns) / len(log_returns)
                rv = round(math.sqrt(variance) * math.sqrt(252) * 100, 2)  # annualized %

        spread = round(iv - rv, 2) if rv is not None else None

        # Status
        if spread is not None:
            if spread > 5:
                status = "ELEVATED_IV"
            elif spread < -5:
                status = "CHEAP_IV"
            else:
                status = "NORMAL"
        else:
            status = "NO_DATA" if rv is None else "NORMAL"

        return IVSpreadResult(
            iv_current=iv,
            rv_current=rv,
            iv_rv_spread=spread,
            iv_percentile=iv_percentile,
            put_call_ratio=pcr,
            skew=skew,
            status=status,
            data_available=True,
        )

    def score(
        self,
        result: IVSpreadResult,
        regime: str = "TRANSITIONING",
        ctx: AssetContext | None = None,
    ) -> tuple[float, list[str]]:
        """Score IV spread → 0–10."""
        evidence: list[str] = []

        if not result.data_available:
            evidence.append("IV data not available → neutral (module inactive)")
            return 5.0, evidence

        score = 5.0

        # IV-RV spread component (60% weight)
        if result.iv_rv_spread is not None:
            # Negative spread = cheap IV = bullish, Positive = expensive = bearish
            spread_score = normalize_to_score(-result.iv_rv_spread, center=0, scale=5.0)
            evidence.append(
                f"IV-RV spread: {result.iv_rv_spread:+.1f}% "
                f"(IV={result.iv_current:.1f}%, RV={result.rv_current:.1f}%) → {spread_score:.1f}"
            )
        else:
            spread_score = 5.0

        # IV percentile component (40% weight)
        if result.iv_percentile is not None:
            # Low percentile = cheap IV = opportunity, High = expensive = caution
            pct_score = normalize_to_score(100 - result.iv_percentile, center=50, scale=20)
            evidence.append(
                f"IV percentile: {result.iv_percentile:.0f}th → {pct_score:.1f}"
            )
        else:
            pct_score = 5.0

        score = spread_score * 0.60 + pct_score * 0.40

        if result.put_call_ratio is not None:
            evidence.append(f"Put/Call ratio: {result.put_call_ratio:.2f}")

        return clamp(score), evidence

    def format_details(self, result: IVSpreadResult) -> dict:
        return {
            "iv_current": result.iv_current,
            "rv_current": result.rv_current,
            "iv_rv_spread": result.iv_rv_spread,
            "iv_percentile": result.iv_percentile,
            "put_call_ratio": result.put_call_ratio,
            "skew": result.skew,
            "status": result.status,
            "data_available": result.data_available,
        }
