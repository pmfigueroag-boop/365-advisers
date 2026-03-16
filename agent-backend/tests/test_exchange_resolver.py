"""
tests/test_exchange_resolver.py
──────────────────────────────────────────────────────────────────────────────
Tests for the centralized exchange resolver utility.
"""

import pytest

from src.utils.exchange_resolver import resolve_exchange, resolve_screener


# ═══════════════════════════════════════════════════════════════════════════════
# Section 1: resolve_exchange — yfinance code → TradingView exchange
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveExchange:
    """Test mapping from yfinance exchange codes to TradingView names."""

    def test_us_nyq(self):
        assert resolve_exchange("NYQ") == "NYSE"

    def test_us_nms(self):
        assert resolve_exchange("NMS") == "NASDAQ"

    def test_us_ngm(self):
        assert resolve_exchange("NGM") == "NASDAQ"

    def test_us_asq(self):
        assert resolve_exchange("ASQ") == "AMEX"

    def test_uk_lse(self):
        assert resolve_exchange("LSE") == "LSE"

    def test_uk_lon(self):
        assert resolve_exchange("LON") == "LSE"

    def test_germany_fra(self):
        assert resolve_exchange("FRA") == "FWB"

    def test_brazil_sao(self):
        assert resolve_exchange("SAO") == "BMFBOVESPA"

    def test_brazil_bvmf(self):
        assert resolve_exchange("BVMF") == "BMFBOVESPA"

    def test_japan_tyo(self):
        assert resolve_exchange("TYO") == "TSE"

    def test_india_nse(self):
        assert resolve_exchange("NSE") == "NSE"

    def test_canada_tor(self):
        assert resolve_exchange("TOR") == "TSX"

    def test_unknown_passthrough(self):
        """Unknown codes fall back to NASDAQ."""
        assert resolve_exchange("UNKNOWN_EXCHANGE") == "NASDAQ"

    def test_already_resolved(self):
        """Already-resolved names pass through correctly."""
        assert resolve_exchange("NYSE") == "NYSE"


# ═══════════════════════════════════════════════════════════════════════════════
# Section 2: resolve_screener — exchange → TradingView screener region
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolveScreener:
    """Test mapping from TradingView exchange to screener region."""

    # ── US Markets ────────────────────────────────────────────────────────

    def test_nyse_america(self):
        assert resolve_screener("NYSE") == "america"

    def test_nasdaq_america(self):
        assert resolve_screener("NASDAQ") == "america"

    def test_amex_america(self):
        assert resolve_screener("AMEX") == "america"

    # ── European Markets ──────────────────────────────────────────────────

    def test_lse_uk(self):
        assert resolve_screener("LSE") == "uk"

    def test_fwb_germany(self):
        assert resolve_screener("FWB") == "germany"

    def test_xetr_germany(self):
        assert resolve_screener("XETR") == "germany"

    def test_bme_spain(self):
        assert resolve_screener("BME") == "spain"

    def test_euronext_france(self):
        assert resolve_screener("EURONEXT") == "france"

    def test_mil_italy(self):
        assert resolve_screener("MIL") == "italy"

    def test_six_switzerland(self):
        assert resolve_screener("SIX") == "switzerland"

    # ── Asian Markets ─────────────────────────────────────────────────────

    def test_tse_japan(self):
        assert resolve_screener("TSE") == "japan"

    def test_hkex_hongkong(self):
        assert resolve_screener("HKEX") == "hongkong"

    def test_nse_india(self):
        assert resolve_screener("NSE") == "india"

    def test_asx_australia(self):
        assert resolve_screener("ASX") == "australia"

    # ── Latin America ─────────────────────────────────────────────────────

    def test_bmfbovespa_brazil(self):
        assert resolve_screener("BMFBOVESPA") == "brazil"

    def test_bmv_mexico(self):
        assert resolve_screener("BMV") == "mexico"

    def test_bcba_argentina(self):
        assert resolve_screener("BCBA") == "argentina"

    def test_bcs_chile(self):
        assert resolve_screener("BCS") == "chile"

    # ── Canada ────────────────────────────────────────────────────────────

    def test_tsx_canada(self):
        assert resolve_screener("TSX") == "canada"

    # ── Raw yfinance codes resolve correctly ──────────────────────────────

    def test_raw_nyq_resolves_to_america(self):
        """Passing a raw yfinance code should auto-resolve."""
        assert resolve_screener("NYQ") == "america"

    def test_raw_sao_resolves_to_brazil(self):
        assert resolve_screener("SAO") == "brazil"

    def test_raw_lon_resolves_to_uk(self):
        assert resolve_screener("LON") == "uk"

    def test_raw_fra_resolves_to_germany(self):
        assert resolve_screener("FRA") == "germany"

    # ── Fallback ──────────────────────────────────────────────────────────

    def test_unknown_falls_back_to_america(self):
        assert resolve_screener("UNKNOWN_EXCHANGE") == "america"
