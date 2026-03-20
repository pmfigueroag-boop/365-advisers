"""
src/engines/validation/universes.py
──────────────────────────────────────────────────────────────────────────────
P1.1 + P3.5: Backtest universe definitions.

Provides curated ticker lists for systematic backtesting across sectors
and asset classes.
"""

# ── Equity Universes ─────────────────────────────────────────────────────────

# Core tech (original universe)
TECH_UNIVERSE = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "TSLA"]

# Core non-tech (expanded universe)
NON_TECH_UNIVERSE = [
    "JNJ", "UNH", "JPM", "GS", "WMT", "KO", "XOM", "CVX", "CAT", "HON",
]

# P1.1: Full 50-ticker systematic backtest universe (diversified across GICS sectors)
SYSTEMATIC_50 = [
    # Technology (8)
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AVGO", "CRM", "ADBE",
    # Communication Services (3)
    "AMZN", "NFLX", "DIS",
    # Consumer Cyclical (4)
    "TSLA", "HD", "MCD", "NKE",
    # Healthcare (5)
    "JNJ", "UNH", "LLY", "PFE", "ABT",
    # Financial Services (5)
    "JPM", "GS", "V", "MA", "BRK-B",
    # Consumer Defensive (4)
    "WMT", "KO", "PG", "PEP",
    # Industrials (5)
    "CAT", "HON", "UPS", "GE", "RTX",
    # Energy (4)
    "XOM", "CVX", "COP", "SLB",
    # Utilities (3)
    "NEE", "DUK", "SO",
    # Real Estate (3)
    "AMT", "PLD", "SPG",
    # Basic Materials (3)
    "LIN", "APD", "FCX",
    # Semiconductors (3 — cross-check with tech)
    "AMD", "INTC", "QCOM",
]

# P3.5: Multi-asset universe (equities + ETFs for cross-asset robustness)
MULTI_ASSET = [
    # Equity benchmarks
    "SPY",    # S&P 500
    "QQQ",    # Nasdaq 100
    "IWM",    # Russell 2000
    # Fixed income
    "TLT",    # 20+ Year Treasury
    "HYG",    # High Yield Corporate
    "LQD",    # Investment Grade Corporate
    # Commodities
    "GLD",    # Gold
    "SLV",    # Silver
    "USO",    # Oil
    # Volatility
    "VXX",    # VIX Short-Term Futures (caution: decay)
    # International
    "EFA",    # EAFE (Developed ex-US)
    "EEM",    # Emerging Markets
    # Crypto proxy (if available)
    # "BITO",  # Bitcoin ETF
]

# ── Sector mapping (for quick classification) ────────────────────────────────
SECTOR_MAP = {
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology",
    "GOOGL": "Technology", "META": "Technology", "AVGO": "Technology",
    "CRM": "Technology", "ADBE": "Technology", "AMD": "Technology",
    "INTC": "Technology", "QCOM": "Technology",
    "AMZN": "Consumer Cyclical", "NFLX": "Communication Services",
    "DIS": "Communication Services",
    "TSLA": "Consumer Cyclical", "HD": "Consumer Cyclical",
    "MCD": "Consumer Cyclical", "NKE": "Consumer Cyclical",
    "JNJ": "Healthcare", "UNH": "Healthcare", "LLY": "Healthcare",
    "PFE": "Healthcare", "ABT": "Healthcare",
    "JPM": "Financial Services", "GS": "Financial Services",
    "V": "Financial Services", "MA": "Financial Services",
    "BRK-B": "Financial Services",
    "WMT": "Consumer Defensive", "KO": "Consumer Defensive",
    "PG": "Consumer Defensive", "PEP": "Consumer Defensive",
    "CAT": "Industrials", "HON": "Industrials", "UPS": "Industrials",
    "GE": "Industrials", "RTX": "Industrials",
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy",
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities",
    "AMT": "Real Estate", "PLD": "Real Estate", "SPG": "Real Estate",
    "LIN": "Basic Materials", "APD": "Basic Materials", "FCX": "Basic Materials",
}
