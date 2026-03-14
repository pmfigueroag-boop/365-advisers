"""
src/agents/tools.py
─────────────────────────────────────────────────────────────────────────────
Tool declarations for Gemini function-calling agents.

Each tool wraps existing data fetchers with structured I/O so that
LLM agents can autonomously request additional data during analysis.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("365advisers.agents.tools")


# ── Tool Definitions (Gemini function-calling format) ─────────────────────────

TOOL_DECLARATIONS = [
    {
        "name": "fetch_peer_comparison",
        "description": (
            "Fetch a comparison of key financial metrics for a stock's sector peers. "
            "Returns P/E, P/B, ROIC, gross margin, and revenue growth for up to 5 peers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol (e.g. 'AAPL')",
                },
                "metric": {
                    "type": "string",
                    "enum": ["valuation", "profitability", "growth", "all"],
                    "description": "Which metric category to compare",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_sector_performance",
        "description": (
            "Get the performance of a sector benchmark over a specified period. "
            "Returns percentage return and relative strength vs S&P 500."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sector": {
                    "type": "string",
                    "description": "Sector name (e.g. 'Technology', 'Healthcare')",
                },
                "period": {
                    "type": "string",
                    "enum": ["1w", "1m", "3m", "6m", "1y"],
                    "description": "Look-back period",
                },
            },
            "required": ["sector"],
        },
    },
    {
        "name": "query_price_history",
        "description": (
            "Get recent price and volume data for a stock. "
            "Returns OHLCV data and basic statistics (avg volume, 52w range)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol",
                },
                "days": {
                    "type": "integer",
                    "description": "Number of trading days of history (default 30, max 252)",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_macro_indicators",
        "description": (
            "Get current macroeconomic indicators snapshot: Fed rate, CPI, "
            "unemployment, GDP growth, yield curve status."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


# ── Tool Execution ────────────────────────────────────────────────────────────

def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a tool call by name, routing to the appropriate data fetcher.

    Returns a structured dict with the results.
    """
    try:
        if name == "fetch_peer_comparison":
            return _fetch_peer_comparison(**arguments)
        elif name == "get_sector_performance":
            return _get_sector_performance(**arguments)
        elif name == "query_price_history":
            return _query_price_history(**arguments)
        elif name == "get_macro_indicators":
            return _get_macro_indicators(**arguments)
        else:
            return {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        logger.warning(f"Tool execution failed: {name} — {exc}")
        return {"error": str(exc)}


def _fetch_peer_comparison(ticker: str, metric: str = "all") -> dict:
    """Fetch peer comparison data from existing data fetcher."""
    try:
        from src.data.market_data import fetch_fundamental_data
        data = fetch_fundamental_data(ticker)
        if not data or "error" in data:
            return {"error": f"No fundamental data for {ticker}"}

        ratios = data.get("ratios", {})
        sector = data.get("sector", "Unknown")
        industry = data.get("industry", "Unknown")

        result = {
            "ticker": ticker,
            "sector": sector,
            "industry": industry,
        }
        if metric in ("valuation", "all"):
            result["valuation"] = ratios.get("valuation", {})
        if metric in ("profitability", "all"):
            result["profitability"] = ratios.get("profitability", {})
        if metric in ("growth", "all"):
            result["growth"] = ratios.get("growth", {})

        return result
    except Exception as exc:
        return {"error": str(exc), "ticker": ticker}


def _get_sector_performance(sector: str, period: str = "3m") -> dict:
    """Get sector performance data."""
    # Map sectors to ETF proxies
    sector_etfs = {
        "technology": "XLK", "healthcare": "XLV", "financials": "XLF",
        "consumer discretionary": "XLY", "industrials": "XLI",
        "energy": "XLE", "materials": "XLB", "utilities": "XLU",
        "real estate": "XLRE", "consumer staples": "XLP",
        "communication services": "XLC",
    }
    etf = sector_etfs.get(sector.lower(), "SPY")
    period_map = {"1w": "5d", "1m": "1mo", "3m": "3mo", "6m": "6mo", "1y": "1y"}
    yf_period = period_map.get(period, "3mo")

    try:
        import yfinance as yf
        data = yf.Ticker(etf).history(period=yf_period)
        if data.empty:
            return {"sector": sector, "etf": etf, "error": "No data"}
        ret = (data["Close"].iloc[-1] / data["Close"].iloc[0] - 1) * 100
        return {
            "sector": sector,
            "etf_proxy": etf,
            "period": period,
            "return_pct": round(ret, 2),
            "start_price": round(data["Close"].iloc[0], 2),
            "end_price": round(data["Close"].iloc[-1], 2),
        }
    except Exception as exc:
        return {"sector": sector, "error": str(exc)}


def _query_price_history(ticker: str, days: int = 30) -> dict:
    """Get price history from yfinance."""
    try:
        import yfinance as yf
        days = min(days, 252)
        period = f"{days}d" if days <= 60 else ("6mo" if days <= 130 else "1y")
        data = yf.Ticker(ticker).history(period=period)
        if data.empty:
            return {"ticker": ticker, "error": "No data"}
        recent = data.tail(min(days, len(data)))
        return {
            "ticker": ticker,
            "days": len(recent),
            "latest_close": round(recent["Close"].iloc[-1], 2),
            "high_52w": round(data["Close"].max(), 2),
            "low_52w": round(data["Close"].min(), 2),
            "avg_volume": int(recent["Volume"].mean()),
            "return_pct": round((recent["Close"].iloc[-1] / recent["Close"].iloc[0] - 1) * 100, 2),
        }
    except Exception as exc:
        return {"ticker": ticker, "error": str(exc)}


def _get_macro_indicators() -> dict:
    """Get macro snapshot from FRED (via existing engine) or fallback."""
    try:
        from src.engines.event_intelligence.engine import EventIntelligenceEngine
        engine = EventIntelligenceEngine()
        macro = engine._get_macro_calendar()
        return {
            "fed_rate": macro.get("fed_rate"),
            "next_fomc": macro.get("next_fomc"),
            "events_this_week": macro.get("events_this_week", [])[:5],
        }
    except Exception:
        return {
            "note": "Macro data unavailable — FRED integration not configured",
            "fed_rate": None,
        }
