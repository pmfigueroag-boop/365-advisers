"""
src/engines/backtesting/universes.py
--------------------------------------------------------------------------
Predefined stock universes for backtesting.

Provides named presets ranging from 10-ticker test sets to the full S&P 500.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("365advisers.backtesting.universes")


# ---------------------------------------------------------------------------
# Test Universe (10 diversified tickers)
# ---------------------------------------------------------------------------
TEST_UNIVERSE = [
    "AAPL", "MSFT", "JPM", "JNJ", "XOM",
    "AMZN", "PG", "CAT", "NEE", "GOOGL",
]

# ---------------------------------------------------------------------------
# Mega Cap (Top 20 by market cap)
# ---------------------------------------------------------------------------
MEGA_CAP_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "BRK-B", "LLY", "TSM", "AVGO",
    "JPM", "UNH", "V", "TSLA", "WMT",
    "XOM", "MA", "PG", "JNJ", "HD",
]

# ---------------------------------------------------------------------------
# S&P 500 Top 100 (by market cap, as of early 2026)
# ---------------------------------------------------------------------------
SP500_100 = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "BRK-B", "LLY", "AVGO", "JPM",
    "UNH", "V", "TSLA", "WMT", "XOM", "MA", "PG", "JNJ", "HD", "COST",
    "ABBV", "MRK", "ORCL", "CRM", "BAC", "CVX", "NFLX", "KO", "AMD", "PEP",
    "ACN", "TMO", "LIN", "MCD", "ABT", "CSCO", "ADBE", "PM", "WFC", "IBM",
    "GE", "DHR", "ISRG", "NOW", "CAT", "INTU", "QCOM", "TXN", "VZ", "AMGN",
    "INTC", "AMAT", "BKNG", "PFE", "AXP", "NEE", "CMCSA", "LOW", "UNP", "HON",
    "SPGI", "COP", "T", "GS", "MS", "RTX", "BLK", "SYK", "UBER", "ELV",
    "SCHW", "DE", "MDLZ", "VRTX", "PGR", "BMY", "CB", "GILD", "C", "LRCX",
    "ADI", "TMUS", "MMC", "SO", "DUK", "REGN", "MO", "TJX", "CI", "ZTS",
    "AON", "ITW", "CME", "BSX", "SLB", "PLD", "ICE", "EMR", "NOC", "FDX",
]

# ---------------------------------------------------------------------------
# Full S&P 500 (as of early 2026 — survivorship bias caveat)
# ---------------------------------------------------------------------------
SP500_FULL = [
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "BRK-B", "LLY", "AVGO",
    "JPM", "UNH", "V", "TSLA", "WMT", "XOM", "MA", "PG", "JNJ", "HD",
    "COST", "ABBV", "MRK", "ORCL", "CRM", "BAC", "CVX", "NFLX", "KO", "AMD",
    "PEP", "ACN", "TMO", "LIN", "MCD", "ABT", "CSCO", "ADBE", "PM", "WFC",
    "IBM", "GE", "DHR", "ISRG", "NOW", "CAT", "INTU", "QCOM", "TXN", "VZ",
    "AMGN", "INTC", "AMAT", "BKNG", "PFE", "AXP", "NEE", "CMCSA", "LOW", "UNP",
    "HON", "SPGI", "COP", "T", "GS", "MS", "RTX", "BLK", "SYK", "UBER",
    "ELV", "SCHW", "DE", "MDLZ", "VRTX", "PGR", "BMY", "CB", "GILD", "C",
    "LRCX", "ADI", "TMUS", "MMC", "SO", "DUK", "REGN", "MO", "TJX", "CI",
    "ZTS", "AON", "ITW", "CME", "BSX", "SLB", "PLD", "ICE", "EMR", "NOC",
    "FDX", "FI", "NSC", "MCO", "EQIX", "GD", "PYPL", "SHW", "ADP", "ETN",
    "APH", "SNPS", "KLAC", "CDNS", "TT", "USB", "PNC", "CTAS", "ORLY", "MSI",
    "WELL", "CEG", "KDP", "MPC", "PSX", "HLT", "AZO", "MCK", "AJG", "WMB",
    "AFL", "NEM", "D", "TDG", "ROP", "SPG", "AEP", "OKE", "SRE", "TFC",
    "MAR", "AIG", "FIS", "ECL", "HCA", "O", "MNST", "KMB", "GIS", "BDX",
    "PCAR", "HUM", "EXC", "CCI", "PSA", "CHTR", "PCG", "MSCI", "EOG", "MET",
    "TRV", "PRU", "KMI", "A", "TEL", "DXCM", "JCI", "IQV", "LHX", "DOW",
    "PAYX", "GEV", "CL", "STZ", "RSG", "CARR", "ED", "CMG", "KHC", "EW",
    "WEC", "YUM", "FAST", "PEG", "VRSK", "XEL", "HSY", "AME", "BK", "AWK",
    "DD", "PPG", "KEYS", "SYY", "OXY", "GEHC", "OTIS", "AVB", "EQR", "DOV",
    "GLW", "HAL", "CSGP", "FANG", "WTW", "ON", "FICO", "ANSS", "IDXX", "VRSN",
    "WST", "MPWR", "ACGL", "RCL", "CTVA", "BRO", "DLR", "TTWO", "VMC", "MLM",
    "CDW", "IRM", "IR", "EPAM", "EFX", "SBAC", "HPQ", "NDAQ", "NUE", "RMD",
    "MTD", "TRGP", "FTV", "WAT", "LUV", "WDC", "TER", "TYL", "STT", "EXR",
    "BAX", "WY", "CFG", "NTRS", "ZBRA", "STE", "ARE", "BIIB", "MAA", "ES",
    "ALGN", "POOL", "PKI", "COO", "LNT", "TSN", "IP", "CNP", "EVRG", "AES",
    "PFG", "VTRS", "JBHT", "KEY", "CPB", "CF", "NRG", "DTE", "MS", "HOLX",
    "FE", "TRMB", "EXPD", "PHM", "HAS", "EMN", "CRL", "LW", "L", "MKC",
    "HII", "WRB", "KIM", "SNA", "LKQ", "CHRW", "UDR", "PEAK", "BWA", "RHI",
    "AIZ", "TAP", "JKHY", "CPT", "WYNN", "REG", "GL", "ALB", "CMI", "CINF",
    "DGX", "DVA", "ALLE", "AOS", "BEN", "FFIV", "HSIC", "NWS", "NWSA", "PNR",
    "SEE", "VTR", "DVN", "HRL", "RL", "WHR", "MOS", "FMC", "IVZ", "MTCH",
    "BBWI", "GNRC", "CZR", "MGM", "AAL", "UAL", "DAL", "NCLH", "CCL", "NI",
]

# Remove duplicates from full list
SP500_FULL = list(dict.fromkeys(SP500_FULL))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_UNIVERSES: dict[str, list[str]] = {
    "test": TEST_UNIVERSE,
    "mega_cap": MEGA_CAP_UNIVERSE,
    "sp500_100": SP500_100,
    "sp500": SP500_FULL,
}


def get_universe(name: str = "test", max_size: int | None = None) -> list[str]:
    """
    Get a named universe.

    Parameters
    ----------
    name : str
        One of: "test", "mega_cap", "sp500_100", "sp500"
    max_size : int | None
        Optional cap on the number of tickers returned.

    Returns
    -------
    list[str]
        Ticker symbols.
    """
    universe = _UNIVERSES.get(name.lower())
    if universe is None:
        available = ", ".join(_UNIVERSES.keys())
        raise ValueError(f"Unknown universe '{name}'. Available: {available}")

    if max_size is not None and max_size > 0:
        universe = universe[:max_size]

    logger.info(f"UNIVERSE: '{name}' -> {len(universe)} tickers")
    return universe


def list_universes() -> dict[str, int]:
    """Return available universe names and their sizes."""
    return {name: len(tickers) for name, tickers in _UNIVERSES.items()}
