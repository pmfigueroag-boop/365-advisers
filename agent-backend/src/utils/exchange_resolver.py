"""
src/utils/exchange_resolver.py
──────────────────────────────────────────────────────────────────────────────
Centralized exchange ↔ TradingView resolver.

Fixes the hardcoded screener="america" bug by mapping exchange codes
to the correct TradingView screener region.
"""

from __future__ import annotations


# ── Exchange code → TradingView exchange name ────────────────────────────────

_EXCHANGE_MAP: dict[str, str] = {
    # US (raw yfinance codes)
    "NYQ": "NYSE",
    "NMS": "NASDAQ",
    "NGM": "NASDAQ",
    "ASQ": "AMEX",
    "PCX": "NYSE",       # NYSE Arca
    "BTS": "NYSE",       # BATS
    # US (identity — already resolved TradingView names)
    "NYSE": "NYSE",
    "NASDAQ": "NASDAQ",
    "AMEX": "AMEX",
    # Europe
    "LSE": "LSE",
    "LON": "LSE",
    "FRA": "FWB",
    "GER": "FWB",
    "XETRA": "XETR",
    "BME": "BME",
    "MIL": "MIL",
    "AMS": "EURONEXT",
    "PAR": "EURONEXT",
    "BRU": "EURONEXT",
    "LIS": "EURONEXT",
    "STO": "STO",
    "HEL": "OMXHEX",
    "CPH": "OMXCOP",
    "OSL": "OSL",
    "IST": "BIST",
    "SWX": "SIX",
    # Asia-Pacific
    "TYO": "TSE",
    "JPX": "TSE",
    "HKG": "HKEX",
    "SHH": "SSE",
    "SHZ": "SZSE",
    "KRX": "KRX",
    "KSC": "KRX",
    "TAI": "TWSE",
    "BOM": "BSE",
    "NSE": "NSE",
    "ASX": "ASX",
    "NZE": "NZX",
    "SGX": "SGX",
    "SET": "SET",
    "KLSE": "MYX",
    "JKT": "IDX",
    # Latin America
    "SAO": "BMFBOVESPA",
    "BVMF": "BMFBOVESPA",
    "BMV": "BMV",
    "BVC": "BVC",
    "BCS": "BCS",
    "BYMA": "BCBA",
    # Middle East & Africa
    "TLV": "TASE",
    "SAU": "TADAWUL",
    "JSE": "JSE",
    # Canada
    "TOR": "TSX",
    "TSX": "TSX",
    "CVE": "TSXV",
}


# ── Exchange → TradingView screener region ───────────────────────────────────

_SCREENER_MAP: dict[str, str] = {
    # US
    "NYSE": "america",
    "NASDAQ": "america",
    "AMEX": "america",
    # Europe
    "LSE": "uk",
    "FWB": "germany",
    "XETR": "germany",
    "BME": "spain",
    "MIL": "italy",
    "EURONEXT": "france",
    "STO": "sweden",
    "OMXHEX": "finland",
    "OMXCOP": "denmark",
    "OSL": "norway",
    "BIST": "turkey",
    "SIX": "switzerland",
    # Asia-Pacific
    "TSE": "japan",
    "HKEX": "hongkong",
    "SSE": "china",
    "SZSE": "china",
    "KRX": "korea",
    "TWSE": "taiwan",
    "BSE": "india",
    "NSE": "india",
    "ASX": "australia",
    "NZX": "newzealand",
    "SGX": "singapore",
    "SET": "thailand",
    "MYX": "malaysia",
    "IDX": "indonesia",
    # Latin America
    "BMFBOVESPA": "brazil",
    "BMV": "mexico",
    "BVC": "colombia",
    "BCS": "chile",
    "BCBA": "argentina",
    # Middle East & Africa
    "TASE": "israel",
    "TADAWUL": "saudi_arabia",
    "JSE": "rsa",
    # Canada
    "TSX": "canada",
    "TSXV": "canada",
}


def resolve_exchange(exchange_code: str) -> str:
    """
    Map raw exchange codes (from yfinance) to TradingView exchange names.

    Args:
        exchange_code: Raw code like "NYQ", "NMS", "LON", "SAO", etc.

    Returns:
        TradingView exchange name (e.g. "NYSE", "LSE", "BMFBOVESPA").
        Falls back to "NASDAQ" for unknown codes.
    """
    return _EXCHANGE_MAP.get(exchange_code, "NASDAQ")


def resolve_screener(exchange: str) -> str:
    """
    Map a TradingView exchange name to its screener region.

    Args:
        exchange: TradingView exchange name (e.g. "NYSE", "LSE", "BMFBOVESPA").
                  Can also accept raw yfinance codes — will resolve first.

    Returns:
        TradingView screener region string (e.g. "america", "brazil", "uk").
        Falls back to "america" for unknown exchanges.
    """
    # If it's a raw yfinance code, resolve first
    resolved = _EXCHANGE_MAP.get(exchange, exchange)
    return _SCREENER_MAP.get(resolved, "america")
