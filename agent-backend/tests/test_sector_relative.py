"""
tests/test_sector_relative.py
──────────────────────────────────────────────────────────────────────────────
Tests for the Sector-Relative Strength Module.
"""

from __future__ import annotations

import pytest

from src.engines.technical.sector_relative import (
    SectorRelativeModule,
    SectorRelativeResult,
    get_sector_etf,
    SECTOR_ETF_MAP,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_ohlcv_series(start_price: float, daily_return_pct: float, days: int) -> list[dict]:
    """Generate OHLCV with a consistent daily return."""
    data = []
    price = start_price
    for _ in range(days):
        close = price
        data.append({
            "open": close * 0.999,
            "high": close * 1.005,
            "low": close * 0.995,
            "close": close,
            "volume": 1_000_000,
        })
        price *= (1 + daily_return_pct / 100)
    return data


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestSectorETFMapping:

    def test_known_ticker(self):
        assert get_sector_etf("AAPL") == "XLK"
        assert get_sector_etf("JPM") == "XLF"
        assert get_sector_etf("XOM") == "XLE"

    def test_sector_name_fallback(self):
        assert get_sector_etf("UNKNOWN_TICKER", "Technology") == "XLK"
        assert get_sector_etf("UNKNOWN_TICKER", "Energy") == "XLE"

    def test_unknown_returns_none(self):
        assert get_sector_etf("UNKNOWN_TICKER_XYZ") is None

    def test_all_sector_etfs_mapped(self):
        assert len(SECTOR_ETF_MAP) >= 10


class TestSectorRelativeModule:

    def setup_method(self):
        self.module = SectorRelativeModule()

    def test_module_protocol_fields(self):
        assert self.module.name == "sector_relative"
        assert 0 < self.module.default_weight <= 1.0

    def test_no_data_returns_neutral(self):
        result = self.module.compute(150.0, {"ticker": "AAPL"}, [])
        score, evidence = self.module.score(result)
        assert score == 5.0
        assert result.status == "NO_DATA"

    def test_outperforming_sector(self):
        """Asset up 1%/day, sector up 0.3%/day → outperforming."""
        asset_ohlcv = _make_ohlcv_series(100, 1.0, 65)
        sector_ohlcv = _make_ohlcv_series(100, 0.3, 65)

        result = self.module.compute(
            asset_ohlcv[-1]["close"],
            {"ticker": "AAPL", "sector_etf": "XLK", "sector_ohlcv": sector_ohlcv},
            asset_ohlcv,
        )

        assert result.status == "OUTPERFORMING"
        assert result.relative_return_20d is not None
        assert result.relative_return_20d > 0

        score, evidence = self.module.score(result)
        assert score > 5.0

    def test_underperforming_sector(self):
        """Asset down 0.5%/day, sector up 0.5%/day → underperforming."""
        asset_ohlcv = _make_ohlcv_series(100, -0.5, 65)
        sector_ohlcv = _make_ohlcv_series(100, 0.5, 65)

        result = self.module.compute(
            asset_ohlcv[-1]["close"],
            {"ticker": "AAPL", "sector_etf": "XLK", "sector_ohlcv": sector_ohlcv},
            asset_ohlcv,
        )

        assert result.status == "UNDERPERFORMING"
        score, _ = self.module.score(result)
        assert score < 5.0

    def test_inline_performance(self):
        """Both same return → inline."""
        asset_ohlcv = _make_ohlcv_series(100, 0.5, 65)
        sector_ohlcv = _make_ohlcv_series(100, 0.5, 65)

        result = self.module.compute(
            asset_ohlcv[-1]["close"],
            {"ticker": "AAPL", "sector_etf": "XLK", "sector_ohlcv": sector_ohlcv},
            asset_ohlcv,
        )

        assert result.status == "INLINE"

    def test_format_details(self):
        result = SectorRelativeResult(
            sector_etf="XLK", relative_return_20d=2.5,
            relative_strength=0.25, status="OUTPERFORMING",
        )
        details = self.module.format_details(result)
        assert details["sector_etf"] == "XLK"
        assert details["status"] == "OUTPERFORMING"
