"""
src/engines/technical/sector_relative.py
──────────────────────────────────────────────────────────────────────────────
Sector-Relative Strength Module — compares asset performance vs sector ETF.

Plugs into the ModuleRegistry as an optional module. Computes relative
return, relative momentum, and relative volume to determine if the asset
is outperforming or underperforming its sector.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.engines.technical.calibration import AssetContext
from src.engines.technical.math_utils import clamp, normalize_to_score


# ─── Sector ETF mapping ─────────────────────────────────────────────────────

SECTOR_ETF_MAP: dict[str, str] = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial Services": "XLF",
    "Financials": "XLF",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Basic Materials": "XLB",
}

# Direct ticker → sector mapping for common stocks (fallback)
_KNOWN_SECTORS: dict[str, str] = {
    "AAPL": "XLK", "MSFT": "XLK", "GOOGL": "XLK", "AMZN": "XLY",
    "META": "XLC", "NVDA": "XLK", "TSLA": "XLY", "JPM": "XLF",
    "JNJ": "XLV", "V": "XLF", "PG": "XLP", "UNH": "XLV",
    "HD": "XLY", "MA": "XLF", "DIS": "XLC", "BAC": "XLF",
    "XOM": "XLE", "CVX": "XLE", "PFE": "XLV", "KO": "XLP",
    "PEP": "XLP", "ABBV": "XLV", "TMO": "XLV", "COST": "XLP",
    "MRK": "XLV", "AVGO": "XLK", "LLY": "XLV", "WMT": "XLP",
    "NFLX": "XLC", "ADBE": "XLK", "CRM": "XLK", "AMD": "XLK",
    "INTC": "XLK", "CSCO": "XLK", "ACN": "XLK", "ORCL": "XLK",
}


def get_sector_etf(ticker: str, sector_name: str = "") -> str | None:
    """Resolve sector ETF for a ticker."""
    upper = ticker.upper()
    if upper in _KNOWN_SECTORS:
        return _KNOWN_SECTORS[upper]
    if sector_name and sector_name in SECTOR_ETF_MAP:
        return SECTOR_ETF_MAP[sector_name]
    return None


# ─── Result dataclass ────────────────────────────────────────────────────────

@dataclass
class SectorRelativeResult:
    sector_etf: str | None = None
    relative_return_5d: float | None = None    # asset return - sector return
    relative_return_20d: float | None = None
    relative_return_60d: float | None = None
    relative_strength: float = 0.0             # -1 to +1 composite
    status: str = "NO_DATA"                    # OUTPERFORMING / UNDERPERFORMING / INLINE / NO_DATA


# ─── Module Implementation ───────────────────────────────────────────────────

class SectorRelativeModule:
    """
    Computes sector-relative strength from OHLCV data.

    Implements the TechnicalModule protocol for composable registration.
    If sector data is not available, returns neutral score (5.0).
    """

    @property
    def name(self) -> str:
        return "sector_relative"

    @property
    def default_weight(self) -> float:
        return 0.10  # 10% weight when active

    def compute(
        self,
        price: float,
        indicators: dict,
        ohlcv: list[dict],
        ctx: AssetContext | None = None,
    ) -> SectorRelativeResult:
        """
        Compute relative performance vs sector.

        Uses OHLCV data and sector_ohlcv from indicators dict.
        indicators should contain:
          - 'sector_etf': str (sector ETF ticker)
          - 'sector_ohlcv': list[dict] (sector ETF OHLCV)
          - 'ticker': str (asset ticker)
          - 'sector_name': str (optional)
        """
        ticker = indicators.get("ticker", "")
        sector_name = indicators.get("sector_name", "")
        sector_etf = indicators.get("sector_etf") or get_sector_etf(ticker, sector_name)
        sector_ohlcv = indicators.get("sector_ohlcv", [])

        if not sector_etf or not sector_ohlcv or not ohlcv:
            return SectorRelativeResult(sector_etf=sector_etf)

        # Compute relative returns at different horizons
        def _return(data: list[dict], lookback: int) -> float | None:
            if len(data) < lookback + 1:
                return None
            end = data[-1].get("close", 0)
            start = data[-(lookback + 1)].get("close", 0)
            if start <= 0:
                return None
            return ((end - start) / start) * 100

        def _relative(asset_data, sector_data, lookback):
            ar = _return(asset_data, lookback)
            sr = _return(sector_data, lookback)
            if ar is not None and sr is not None:
                return round(ar - sr, 2)
            return None

        rel_5d = _relative(ohlcv, sector_ohlcv, 5)
        rel_20d = _relative(ohlcv, sector_ohlcv, 20)
        rel_60d = _relative(ohlcv, sector_ohlcv, 60)

        # Composite relative strength: weighted average of available horizons
        components = []
        weights_map = {5: 0.2, 20: 0.4, 60: 0.4}
        for val, period in [(rel_5d, 5), (rel_20d, 20), (rel_60d, 60)]:
            if val is not None:
                components.append((val, weights_map[period]))

        if components:
            total_w = sum(w for _, w in components)
            rs = sum(v * w for v, w in components) / total_w
        else:
            rs = 0.0

        # Normalize to -1..+1 range
        relative_strength = max(-1.0, min(1.0, rs / 10.0))  # 10% = max

        # Status
        if relative_strength > 0.15:
            status = "OUTPERFORMING"
        elif relative_strength < -0.15:
            status = "UNDERPERFORMING"
        else:
            status = "INLINE"

        return SectorRelativeResult(
            sector_etf=sector_etf,
            relative_return_5d=rel_5d,
            relative_return_20d=rel_20d,
            relative_return_60d=rel_60d,
            relative_strength=round(relative_strength, 3),
            status=status,
        )

    def score(
        self,
        result: SectorRelativeResult,
        regime: str = "TRANSITIONING",
        ctx: AssetContext | None = None,
    ) -> tuple[float, list[str]]:
        """Score sector-relative strength → 0–10."""
        evidence: list[str] = []

        if result.status == "NO_DATA":
            evidence.append("Sector data not available → neutral")
            return 5.0, evidence

        # Score based on relative strength (-1..+1 → 0..10)
        score = normalize_to_score(result.relative_strength, center=0.0, scale=0.3)

        # Evidence
        etf = result.sector_etf or "N/A"
        if result.relative_return_20d is not None:
            evidence.append(
                f"Relative return vs {etf} (20d): {result.relative_return_20d:+.1f}%"
            )
        if result.relative_return_60d is not None:
            evidence.append(
                f"Relative return vs {etf} (60d): {result.relative_return_60d:+.1f}%"
            )

        evidence.append(
            f"Sector-relative strength: {result.relative_strength:+.3f} → "
            f"status: {result.status} → score {score:.1f}"
        )

        return clamp(score), evidence

    def format_details(self, result: SectorRelativeResult) -> dict:
        return {
            "sector_etf": result.sector_etf,
            "relative_return_5d": result.relative_return_5d,
            "relative_return_20d": result.relative_return_20d,
            "relative_return_60d": result.relative_return_60d,
            "relative_strength": result.relative_strength,
            "status": result.status,
        }
